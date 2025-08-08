from django.http import HttpResponse, HttpRequest
from rest_framework import viewsets
from rest_framework.response import Response
from .serializers import ProductListSerializer, ProductDetailSerializer
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


class ProductViewSet(viewsets.ModelViewSet):
    """
    Viewset for listing products with their best price options.
    """

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
