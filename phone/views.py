from django.http import HttpResponse, HttpRequest
from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.response import Response
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    OrderSerializer,
    NoticeSerializer,
    FAQSerializer,
    BannerSerializer,
)
from django.db.models import Prefetch

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


class OrderViewSet(ListModelMixin, CreateModelMixin, GenericViewSet):
    """
    Viewset for managing orders.
    """

    serializer_class = OrderSerializer

    queryset = Order.objects.all().filter(deleted_at__isnull=True)

    def get_queryset(self):
        return self.queryset

    def list(self, request, *args, **kwargs):
        """
        Override the list method to return orders.
        """
        phone = request.query_params.get("phone", None)
        password = request.query_params.get("password", None)

        queryset = (
            self.get_queryset()
            .select_related("plan", "device_variant", "device_color", "product__device")
            .filter(customer_phone=phone, password=password)
        )

        serializer = OrderSerializer(queryset, many=True)

        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        Override the create method to handle order creation.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)


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
