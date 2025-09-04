import re
from django.http import HttpResponse, HttpRequest
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .serializers import *
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status
from django.db.models import Prefetch


# Create your views here.
from .models import *


def clean_phone_num(phone_num: str) -> str:
    return re.sub(r"[^0-9]", "", phone_num)


def ping(request: HttpRequest) -> HttpResponse:
    """
    Ping view to check server status.
    """
    return HttpResponse("pong")


class ProductViewSet(ReadOnlyModelViewSet):
    """
    Viewset for listing products with their best price options.
    """

    serializer_class = ProductListSerializer
    queryset = Product.objects.filter(deleted_at__isnull=True, is_active=True).all()

    def get_queryset(self):
        return self.queryset

    @swagger_auto_schema(
        operation_description="상품 목록 조회",
        manual_parameters=[
            openapi.Parameter(
                "brand",
                openapi.IN_QUERY,
                description="제조사(삼성/애플)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        Override the list method to return products with their best price options.
        """
        base_queryset = self.get_queryset().filter(best_price_option_id__isnull=False)
        if brand_query := self.request.query_params.get("brand", None):
            base_queryset = base_queryset.filter(device__brand=brand_query)

        if not base_queryset.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        queryset = base_queryset.select_related(
            "device",
            "best_price_option",
            "best_price_option__plan",
            "best_price_option__device_variant",
        ).order_by("-sort_order")

        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):

        base_queryset = self.get_queryset().filter(id=kwargs.get("pk"))

        if not base_queryset.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        instance = (
            base_queryset.select_related(
                "device",
            ).prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "options__plan",
                    queryset=Plan.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "device__variants",
                    queryset=DeviceVariant.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "device__colors",
                    queryset=DeviceColor.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "device__colors__images",
                    queryset=DevicesColorImage.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "images",
                    queryset=ProductDetailImage.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "reviews",
                    queryset=Review.objects.filter(
                        deleted_at__isnull=True, is_public=True
                    ).order_by("-created_at")[:10],
                    to_attr="limited_reviews",
                ),
            )
        ).first()

        serializer = ProductDetailSerializer(instance)
        return Response(serializer.data)


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    Viewset for managing orders.
    """

    serializer_class = OrderSerializer
    permission_classes = [AllowAny]

    queryset = Order.objects.all().filter(deleted_at__isnull=True)

    def get_queryset(self):
        return self.queryset

    @swagger_auto_schema(
        operation_description="주문 목록 조회",
        manual_parameters=[
            openapi.Parameter(
                "phone",
                openapi.IN_QUERY,
                description="고객 전화번호(필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "customer_name",
                openapi.IN_QUERY,
                description="고객 이름(필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        get phone_num from request query param
        """

        phone = request.query_params.get("phone", None)
        if not phone:
            return Response({"error": "param phone required"}, status=400)
        customer_name = request.query_params.get("customer_name", None)
        if not customer_name:
            return Response({"error": "param customer_name required"}, status=400)

        phone = clean_phone_num(phone)
        orders = Order.objects.raw(
            f"""
SELECT DISTINCT ON (o.id) ci.image, c.color_code, o.*
FROM phone_order o
JOIN phone_product p
    ON p.id = o.product_id
JOIN phone_devicecolor c
    ON c.device_id = p.device_id
    AND o.color = c.color
    AND c.deleted_at IS NULL
JOIN phone_devicescolorimage ci
    ON ci.device_color_id = c.id
    AND ci.deleted_at IS NULL
WHERE 
    o.deleted_at IS NULL
    AND o.customer_name='{customer_name}'
    AND o.customer_phone='{phone}'
ORDER BY o.id, ci.id;
"""
        )

        if len(orders) == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(orders, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        request_body=OrderCreateSerializer,
    )
    def create(self, request, *args, **kwargs):
        body = request.data
        customer_phone = clean_phone_num(body.get("customer_phone"))
        customer_phone2 = clean_phone_num(body.get("customer_phone2"))

        new_order = Order.objects.create(
            customer_name=body.get("customer_name"),
            customer_phone=customer_phone,
            customer_phone2=customer_phone2,
            customer_email=body.get("customer_email"),
            customer_birth=body.get("customer_birth"),
            product_id=body.get("product_id"),
            plan_id=body.get("plan_id"),
            contract_type=body.get("contract_type"),
            device_price=body.get("device_price"),
            plan_monthly_fee=body.get("plan_monthly_fee"),
            subsidy_standard=body.get("subsidy_standard"),
            subsidy_mnp=body.get("subsidy_mnp"),
            payment_period=body.get("payment_period"),
            final_price=body.get("final_price"),
            discount_type=body.get("discount_type"),
            monthly_discount=body.get("monthly_discount"),
            additional_discount=body.get("additional_discount"),
            storage_capacity=body.get("storage_capacity"),
            color=body.get("color"),
            customer_memo=body.get("customer_memo"),
            shipping_address=body.get("shipping_address"),
            shipping_address_detail=body.get("shipping_address_detail"),
            zipcode=body.get("zipcode"),
            ga4_id=body.get("ga4_id", ""),
        )
        new_order.save()
        return Response({"id": new_order.id}, status=201)

    def retrieve(self, request, *args, **kwargs):
        queryset = Order.objects.raw(
            """
            SELECT DISTINCT ON (o.id) ci.image, c.color_code, o.*
            FROM phone_order o
            JOIN phone_product p
                ON p.id = o.product_id
            JOIN phone_devicecolor c
                ON c.device_id = p.device_id
                AND o.color = c.color
                AND c.deleted_at IS NULL
            JOIN phone_devicescolorimage ci
                ON ci.device_color_id = c.id
                AND ci.deleted_at IS NULL
            WHERE 
                o.deleted_at IS NULL
                AND o.id = %s
            ORDER BY o.id, ci.id;
            """,
            [kwargs.get("pk")],  # SQL 인젝션 방지를 위해 파라미터 사용
        )

        if len(queryset) == 0:
            return HttpResponse("Order not found", status=404)

        serializer = OrderDetailSerializer(queryset[0])
        return Response(serializer.data)


class FAQViewSet(ReadOnlyModelViewSet):
    queryset = FAQ.objects.all().filter(deleted_at__isnull=True).order_by("sort_order")
    serializer_class = FAQSerializer


class NoticeViewSet(ReadOnlyModelViewSet):
    serializer_class = NoticeSerializer
    queryset = (
        Notice.objects.all().filter(deleted_at__isnull=True).order_by("-created_at")
    )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class BannerViewSet(ReadOnlyModelViewSet):
    serializer_class = BannerSerializer
    queryset = (
        Banner.objects.all().filter(deleted_at__isnull=True).order_by("-created_at")
    )


class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    serializer_class = ReviewSerializer
    queryset = (
        Review.objects.all()
        .filter(deleted_at__isnull=True, is_public=True)
        .select_related("product")
        .order_by("-created_at")
    )
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="리뷰 생성",
        operation_description="새로운 제품 리뷰를 생성합니다. 이미지 파일 업로드를 포함할 수 있습니다.",
        request_body=ReviewCreateSerializer,
        responses={
            201: openapi.Response(
                description="리뷰가 성공적으로 생성되었습니다.",
            ),
            400: openapi.Response(
                description="잘못된 요청 데이터",
                examples={
                    "application/json": {
                        "rating": ["Rating must be between 1 and 5."],
                    }
                },
            ),
        },
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                "product_id",
                openapi.IN_FORM,
                description="상품id",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                "customer_name",
                openapi.IN_FORM,
                description="고객명",
                type=openapi.TYPE_STRING,
                required=True,
                max_length=100,
            ),
            openapi.Parameter(
                "rating",
                openapi.IN_FORM,
                description="평점 (1-5)",
                type=openapi.TYPE_INTEGER,
                required=True,
                minimum=1,
                maximum=5,
            ),
            openapi.Parameter(
                "comment",
                openapi.IN_FORM,
                description="리뷰 내용",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "image",
                openapi.IN_FORM,
                description="리뷰 이미지 파일 (선택사항)",
                type=openapi.TYPE_FILE,
                required=False,
            ),
        ],
        tags=["Reviews"],
    )
    def create(self, request, *args, **kwargs):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PolicyDocumentViewSet(ReadOnlyModelViewSet):
    serializer_class = PolicyDocumentSerializer
    queryset = (
        PolicyDocument.objects.all()
        .filter(deleted_at__isnull=True)
        .order_by("-created_at")
    )
