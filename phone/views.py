import re
from django.http import HttpResponse, HttpRequest, JsonResponse
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet, ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter
from .serializers import *
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status
from django.db.models import Prefetch, Q, F, Subquery, OuterRef
from .external_services.channel_talk import send_order_alert
from .constants import CarrierChoices
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt


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
            openapi.Parameter(
                "series",
                openapi.IN_QUERY,
                description="시리즈(갤럭시S/아이폰)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "carrier",
                openapi.IN_QUERY,
                description="이전 통신사(SK/KT/LG)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "is_featured",
                openapi.IN_QUERY,
                description="추천 상품 여부 (true/false)",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        Override the list method to return products with their best price options.
        """
        base_queryset = (
            self.get_queryset()
            .filter(best_price_option_id__isnull=False)
            .select_related(
                "product_series",
            )
            .prefetch_related(
                "tags",
            )
        )
        if brand_query := self.request.query_params.get("brand", None):
            base_queryset = base_queryset.filter(device__brand=brand_query)
        if series_query := self.request.query_params.get("series", None):
            base_queryset = base_queryset.filter(product_series__name=series_query)
        if (
            prev_carrier := self.request.query_params.get("carrier", None)
        ) in CarrierChoices.VALUES:
            pass  # handled later
        if is_featured := self.request.query_params.get("is_featured", None):
            if is_featured.lower() == "true":
                base_queryset = base_queryset.filter(is_featured=True)
            elif is_featured.lower() == "false":
                base_queryset = base_queryset.filter(is_featured=False)

        if not base_queryset.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        queryset = (
            base_queryset.select_related(
                "device",
            )
            .prefetch_related("images")
            .order_by("-sort_order")
        )

        if prev_carrier in CarrierChoices.VALUES:
            # 1. productOption 에서 contract_type이 '기기변경' + plan.carrier = prev_carrier
            # 또는 2. contract_type이 '번호이동' + plan.carrier != prev_carrier
            queryset = queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.filter(deleted_at__isnull=True)
                    .select_related("plan", "device_variant")
                    .filter(
                        Q(Q(contract_type="기기변경") & Q(plan__carrier=prev_carrier))
                        | Q(
                            Q(contract_type="번호이동") & ~Q(plan__carrier=prev_carrier)
                        )
                    ),
                )
            )
        else:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.filter(
                        deleted_at__isnull=True
                    ).select_related("plan", "device_variant"),
                )
            )

        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="상품 상세 조회",
        manual_parameters=[
            openapi.Parameter(
                "carrier",
                openapi.IN_QUERY,
                description="이전 통신사(SK/KT/LG)",
                type=openapi.TYPE_STRING,
                required=False,
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        base_queryset = self.get_queryset().filter(id=kwargs.get("pk"))

        if not base_queryset.exists():
            return Response(status=status.HTTP_404_NOT_FOUND)

        base_queryset.update(views=F("views") + 1)

        prev_carrier = self.request.query_params.get("carrier", None)
        if prev_carrier in CarrierChoices.VALUES:
            base_queryset = base_queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.filter(deleted_at__isnull=True)
                    # .exclude(additional_discount=0)
                    .select_related("plan", "device_variant").filter(
                        Q(Q(contract_type="기기변경") & Q(plan__carrier=prev_carrier))
                        | Q(
                            Q(contract_type="번호이동") & ~Q(plan__carrier=prev_carrier)
                        )
                    ),
                )
            )
        else:
            base_queryset = base_queryset.prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.filter(deleted_at__isnull=True)
                    .exclude(additional_discount=0)
                    .select_related("plan", "device_variant", "official_contract_link"),
                )
            )

        instance = (
            base_queryset.select_related(
                "device",
            ).prefetch_related(
                Prefetch(
                    "device__variants",
                    queryset=DeviceVariant.objects.filter(deleted_at__isnull=True),
                ),
                Prefetch(
                    "device__colors",
                    queryset=DeviceColor.objects.filter(
                        deleted_at__isnull=True
                    ).order_by("sort_order"),
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

        # 재고 정보 조회 (prefetch된 데이터 사용)
        variant_ids = [v.id for v in instance.device.variants.all()]
        color_ids = [c.id for c in instance.device.colors.all()]
        inventories = Inventory.objects.filter(
            device_variant_id__in=variant_ids,
            device_color_id__in=color_ids,
            deleted_at__isnull=True,
        ).select_related("dealership", "device_variant", "device_color")

        serializer = ProductDetailSerializer(
            instance, context={"inventories": inventories}
        )
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
            prev_carrier=body.get("prev_carrier", ""),
        )
        new_order.save()
        send_order_alert(
            order_id=new_order.id,
            customer_name=new_order.customer_name,
            customer_phone=new_order.customer_phone,
        )
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

    @swagger_auto_schema(
        operation_description="공지사항 조회",
        manual_parameters=[
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                description="공지사항 유형(필수)",
                type=openapi.TYPE_STRING,
                required=True,
                enum=["caution", "event", "general"],
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        notice_type = request.query_params.get("type", None)
        if notice_type:
            queryset = queryset.filter(type=notice_type)

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


class ProductSeriesViewSet(ReadOnlyModelViewSet):
    queryset = ProductSeries.objects.prefetch_related(
        "productseries", "productseries__device", "productseries__images"
    ).all()

    serializer_class = ProductSeriesSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().order_by("name")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class BannerViewSet(ReadOnlyModelViewSet):

    serializer_class = BannerSerializer
    queryset = (
        Banner.objects.all()
        .filter(deleted_at__isnull=True, is_active=True)
        .order_by("-sort_order")
    )
    filter_backends = [OrderingFilter]
    ordering_fields = ["sort_order", "sort_order_test"]


class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    serializer_class = ReviewSerializer
    queryset = (
        Review.objects.all()
        .filter(deleted_at__isnull=True, is_public=True)
        .select_related("product")
        .prefetch_related("product__images")
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


class PartnerCardViewSet(ReadOnlyModelViewSet):
    serializer_class = PartnerCardSerializer
    queryset = (
        PartnerCard.objects.all()
        .filter(deleted_at__isnull=True, is_active=True)
        .order_by("sort_order")
    ).prefetch_related(
        Prefetch(
            "card_benefits",
            queryset=CardBenefit.objects.filter(
                deleted_at__isnull=True, is_optional=False
            ),
        )
    )


class EventViewSet(ReadOnlyModelViewSet):
    serializer_class = EventSimpleSerializer
    queryset = Event.objects.all().filter(deleted_at__isnull=True, is_active=True)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().order_by("-start_date"))

        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = EventSerializer(instance)
        return Response(serializer.data)


class DeviceViewSet(ReadOnlyModelViewSet):
    serializer_class = DeviceSerializer
    queryset = (
        Device.objects.all()
        .filter(deleted_at__isnull=True)
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=DeviceVariant.objects.filter(deleted_at__isnull=True),
            ),
        )
        .annotate(
            first_image_url=Subquery(
                DevicesColorImage.objects.filter(
                    device_color__device=OuterRef(
                        "pk"
                    ),  # OuterRef는 메인 쿼리(Device)의 PK를 참조
                    # SoftDeleteModel을 쓰신다고 했으므로 삭제 안 된 것만 필터링 (필요 시)
                    # deleted_at__isnull=True
                )
                .order_by(
                    "device_color__id",  # 1순위 정렬: 컬러가 먼저 생성된 순서 (colors[0] 효과)
                    "id",  # 2순위 정렬: 이미지 ID 순서 (images[0] 효과)
                )
                .values("image")[:1]  # 이미지 경로 필드(image)만 선택해서 1개 가져옴
            )
        )
    )


class PhonePlanViewSet(ReadOnlyModelViewSet):
    serializer_class = PlanSerializer
    queryset = Plan.objects.all().filter(deleted_at__isnull=True)


class ProductOptionViewSet(ReadOnlyModelViewSet):
    serializer_class = ProductOptionSerializer
    queryset = ProductOption.objects.all().filter(deleted_at__isnull=True)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if dv_id := request.query_params.get("dv_id", None):
            queryset = queryset.filter(device_variant_id=dv_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@csrf_exempt
def tinymce_upload(request):
    if request.method != "POST" or not request.FILES.get("file"):
        return JsonResponse({"error": "Invalid request"}, status=400)

    file_instance = CustomImage.objects.create(
        image=request.FILES["file"], name=request.FILES["file"].name
    )
    return JsonResponse({"location": file_instance.image.url})


class PriceNotificationRequestViewSet(ModelViewSet):
    serializer_class = PriceNotificationRequestSerializer
    queryset = PriceNotificationRequest.objects.all().filter(deleted_at__isnull=True)
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="가격 알림 신청",
        operation_description="특정 상품이 목표 가격 이하로 내려갔을 때 알림을 받기 위한 신청",
        request_body=PriceNotificationRequestCreateSerializer,
        responses={
            201: PriceNotificationRequestSerializer,
            400: "유효성 검증 실패 (전화번호 형식, 중복 신청 등)",
        },
    )
    def _check_duplicate_notification(self, customer_phone, product_id):
        """중복 알림 신청 체크. 중복이면 True 반환"""
        if not customer_phone or not product_id:
            return False
        return PriceNotificationRequest.objects.filter(
            customer_phone=customer_phone,
            product_id=product_id,
            deleted_at__isnull=True,
            notified_at__isnull=True,
        ).exists()

    def create(self, request, *args, **kwargs):
        if self._check_duplicate_notification(
            request.data.get("customer_phone"),
            request.data.get("product_id"),
        ):
            return Response(
                {"error": "이미 해당 상품에 대한 알림 신청이 존재합니다."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = PriceNotificationRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="가격 알림 신청 목록 조회",
        operation_description="특정 고객의 가격 알림 신청 목록을 조회합니다.",
        manual_parameters=[
            openapi.Parameter(
                "customer_phone",
                openapi.IN_QUERY,
                description="고객 전화번호 (필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: PriceNotificationRequestSerializer(many=True),
            400: "customer_phone 파라미터 누락",
        },
    )
    def list(self, request, *args, **kwargs):
        if customer_phone := self.request.query_params.get("customer_phone", None):
            self.queryset = self.queryset.filter(customer_phone=customer_phone)
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        return Response(
            {"error": "param customer_phone required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class PriceHistoryChartViewSet(GenericViewSet):
    """
    가격 변동 차트 데이터를 제공하는 ViewSet
    """

    permission_classes = [AllowAny]

    PERIOD_DAYS = {
        "1week": 7,
        "1month": 30,
        "3months": 90,
        "6months": 180,
        "1year": 365,
    }

    @swagger_auto_schema(
        operation_summary="가격 변동 차트 데이터 조회",
        operation_description="특정 상품의 통신사별 가격 변동 추이를 조회합니다.",
        manual_parameters=[
            openapi.Parameter(
                "product_id",
                openapi.IN_QUERY,
                description="상품 ID (필수)",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                "period",
                openapi.IN_QUERY,
                description="조회 기간 (1week, 1month, 3months, 6months, 1year)",
                type=openapi.TYPE_STRING,
                required=False,
                default="1month",
                enum=["1week", "1month", "3months", "6months", "1year"],
            ),
        ],
        responses={
            200: openapi.Response(
                description="성공",
                examples={
                    "application/json": {
                        "product_name": "갤럭시 S25",
                        "storage": "256GB",
                        "period": "1month",
                        "chart_data": [
                            {
                                "date": "2024-12-01",
                                "SK": 850000,
                                "KT": 780000,
                                "LG": 720000,
                            }
                        ],
                        "latest_prices": {
                            "SK": {
                                "price": 850000,
                                "plan_name": "5G 프리미어 플러스",
                                "plan_price": 105000,
                            },
                            "KT": {
                                "price": 780000,
                                "plan_name": "슈퍼플랜 베이직",
                                "plan_price": 89000,
                            },
                            "LG": {
                                "price": 720000,
                                "plan_name": "5G 시그니처",
                                "plan_price": 95000,
                            },
                        },
                    }
                },
            ),
            400: "파라미터 오류",
            404: "상품을 찾을 수 없음",
        },
    )
    def list(self, request, *args, **kwargs):
        # 파라미터 검증
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id 파라미터가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except ValueError:
            return Response(
                {"error": "product_id는 정수여야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = request.query_params.get("period", "1month")
        if period not in self.PERIOD_DAYS:
            return Response(
                {
                    "error": f"유효하지 않은 period입니다. 가능한 값: {list(self.PERIOD_DAYS.keys())}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 상품 조회
        try:
            product = Product.objects.select_related("device").get(
                id=product_id, deleted_at__isnull=True
            )
        except Product.DoesNotExist:
            return Response(
                {"error": "상품을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 가장 작은 용량의 variant 조회
        smallest_variant = (
            DeviceVariant.objects.filter(device=product.device, deleted_at__isnull=True)
            .order_by("device_price")
            .first()
        )

        storage = smallest_variant.storage_capacity if smallest_variant else "N/A"

        # 기간 계산
        days = self.PERIOD_DAYS[period]
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # 시작일 이전의 가장 최근 가격을 각 통신사별로 조회 (초기값으로 사용)
        carriers = [CarrierChoices.SK, CarrierChoices.KT, CarrierChoices.LG]
        last_known_prices = {}
        last_known_plans = {}

        for carrier in carriers:
            initial_price = (
                PriceHistory.objects.filter(
                    product=product,
                    carrier=carrier,
                    price_at__lt=start_date,
                    deleted_at__isnull=True,
                )
                .select_related("plan")
                .order_by("-price_at")
                .first()
            )
            if initial_price:
                last_known_prices[carrier] = initial_price.final_price
                last_known_plans[carrier] = initial_price.plan
            else:
                last_known_prices[carrier] = None
                last_known_plans[carrier] = None

        # 기간 내 PriceHistory 조회
        price_histories = (
            PriceHistory.objects.filter(
                product=product,
                price_at__gte=start_date,
                price_at__lte=end_date,
                deleted_at__isnull=True,
            )
            .select_related("plan")
            .order_by("price_at")
        )

        # 날짜별 가격 변동 데이터를 dict로 변환
        price_changes = {}
        for ph in price_histories:
            date_str = ph.price_at.strftime("%Y-%m-%d")
            if date_str not in price_changes:
                price_changes[date_str] = {}
            price_changes[date_str][ph.carrier] = {
                "price": ph.final_price,
                "plan": ph.plan,
            }

        # 모든 날짜에 대해 chart_data 생성 (빈 날짜는 직전 가격으로 채움)
        chart_data = []
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            # 해당 날짜에 가격 변동이 있으면 업데이트
            if date_str in price_changes:
                for carrier, data in price_changes[date_str].items():
                    last_known_prices[carrier] = data["price"]
                    last_known_plans[carrier] = data["plan"]

            chart_data.append(
                {
                    "date": date_str,
                    "SK": last_known_prices.get(CarrierChoices.SK),
                    "KT": last_known_prices.get(CarrierChoices.KT),
                    "LG": last_known_prices.get(CarrierChoices.LG),
                }
            )

            current_date += timedelta(days=1)

        # latest_prices 생성 (마지막으로 알려진 가격)
        latest_prices = {}
        for carrier in carriers:
            if last_known_prices.get(carrier) is not None and last_known_plans.get(
                carrier
            ):
                latest_prices[carrier] = {
                    "price": last_known_prices[carrier],
                    "plan_name": last_known_plans[carrier].name,
                    "plan_price": last_known_plans[carrier].price,
                }
            else:
                latest_prices[carrier] = None

        return Response(
            {
                "product_name": product.name,
                "storage": storage,
                "period": period,
                "chart_data": chart_data,
                "latest_prices": latest_prices,
            }
        )
