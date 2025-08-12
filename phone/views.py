from django.http import HttpResponse, HttpRequest
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    OrderListSerializer,
    NoticeSerializer,
    FAQSerializer,
    BannerSerializer,
    OrderCreateSerializer,
)
from django.db.models import Prefetch
import bcrypt


# Create your views here.
from .models import *

"""TODO
3. 리뷰 조회
4. 리뷰 작성
5. 주문 작성
6. 주문 조회
"""


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


class OrderListViewSet(ReadOnlyModelViewSet):
    """
    Viewset for managing orders.
    """

    serializer_class = OrderListSerializer

    queryset = Order.objects.all().filter(deleted_at__isnull=True)

    def get_queryset(self):
        return self.queryset

    def list(self, request, *args, **kwargs):
        """
        get phone_num and password from request query param
        and if both are provided, filter the orders by these credentials.
        """

        phone = request.query_params.get("phone", None)
        password = request.query_params.get("password", None)
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        queryset = (
            self.get_queryset()
            .select_related("plan", "device_variant", "device_color", "product__device")
            .filter(customer_phone=phone, password=password_hash)
        )

        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


class OrderCreateViewSet(CreateAPIView):
    queryset = Order.objects.all().filter(deleted_at__isnull=True)
    serializer_class = OrderCreateSerializer

    def create(self, request, *args, **kwargs):
        body = request.data
        new_order = Order.objects.create(
            customer_name=body.get("customer_name"),
            customer_phone=body.get("customer_phone"),
            customer_phone2=body.get("customer_phone2"),
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
