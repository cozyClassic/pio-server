import re
from django.http import HttpResponse, HttpRequest
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet
from rest_framework.response import Response
from .serializers import *
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins
from django.db.models import Prefetch
import bcrypt


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
    queryset = Product.objects.all().filter(deleted_at__isnull=True)

    def get_queryset(self):
        return self.queryset

    def list(self, request, *args, **kwargs):
        """
        Override the list method to return products with their best price options.
        """
        queryset = self.get_queryset().select_related(
            "best_price_option",
            "best_price_option__plan",
            "best_price_option__device_variant",
        )
        serializer = ProductListSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = (
            self.queryset.filter(id=kwargs.get("pk"))
            .select_related(
                "device",
            )
            .prefetch_related(
                "options",
                "options__plan",
                "device__variants",
                "device__colors",
                "device__colors__images",
                "images",
                Prefetch(
                    "reviews",
                    queryset=Review.objects.filter(deleted_at__isnull=True)
                    .prefetch_related("images")
                    .order_by("-created_at")[:10],
                    to_attr="limited_reviews",
                ),
            )
        ).first()

        serializer = ProductDetailSerializer(instance)
        return Response(serializer.data)


class OrderViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    """
    Viewset for managing orders.
    """

    serializer_class = OrderSerializer

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
                "password",
                openapi.IN_QUERY,
                description="고객 비밀번호(필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        get phone_num and password from request query param
        and if both are provided, filter the orders by these credentials.
        """

        phone = request.query_params.get("phone", None)
        password = request.query_params.get("password", None)
        if not phone or not password:
            return Response({"error": "phone and password are required"}, status=400)
        phone = clean_phone_num(phone)
        orders = self.get_queryset().filter(customer_phone=phone).all()
        verified_orders = []

        for order in orders:
            if bcrypt.checkpw(password.encode("utf-8"), order.password.encode("utf-8")):
                verified_orders.append(order)

        serializer = self.serializer_class(verified_orders, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        body = request.data
        customer_phone = clean_phone_num(body.get("customer_phone"))
        customer_phone2 = clean_phone_num(body.get("customer_phone2"))

        new_order = Order.objects.create(
            customer_name=body.get("customer_name"),
            customer_phone=customer_phone,
            customer_phone2=customer_phone2,
            customer_email=body.get("customer_email"),
            product_id=body.get("product_id"),
            plan_id=body.get("plan_id"),
            contract_type=body.get("contract_type"),
            device_price=body.get("device_price"),
            plan_monthly_fee=body.get("plan_monthly_fee"),
            subsidy_amount=body.get("subsidy_amount"),
            subsidy_amount_mnp=body.get("subsidy_amount_mnp"),
            final_price=body.get("final_price"),
            discount_type=body.get("discount_type"),
            monthly_discount=body.get("monthly_discount"),
            additional_discount=body.get("additional_discount"),
            password=(
                bcrypt.hashpw(body.get("password").encode("utf-8"), bcrypt.gensalt())
            ).decode("utf-8"),
            storage_capacity=body.get("storage_capacity"),
            color=body.get("color"),
            customer_memo=body.get("customer_memo"),
        )
        new_order.save()
        return Response({"id": new_order.id}, status=201)


class FAQViewSet(ReadOnlyModelViewSet):
    queryset = FAQ.objects.all().filter(deleted_at__isnull=True).order_by("sort_order")
    serializer_class = FAQSerializer


class NoticeViewSet(ReadOnlyModelViewSet):
    serializer_class = NoticeSerializer
    queryset = (
        Notice.objects.all().filter(deleted_at__isnull=True).order_by("-created_at")
    )


class BannerViewSet(ReadOnlyModelViewSet):
    serializer_class = BannerSerializer
    queryset = (
        Banner.objects.all().filter(deleted_at__isnull=True).order_by("-created_at")
    )


class ReviewImageCreateView(mixins.CreateModelMixin, GenericViewSet):
    serializer_class = ReviewImageSerializer
    queryset = ReviewImage.objects.all().filter(deleted_at__isnull=True)
    parser_classes = [MultiPartParser, FormParser]


class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    serializer_class = ReviewSerializer
    queryset = (
        Review.objects.all()
        .prefetch_related("images")
        .filter(deleted_at__isnull=True)
        .order_by("-created_at")
    )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)
