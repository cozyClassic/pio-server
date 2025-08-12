from django.urls import path
from rest_framework import routers

from .views import (
    OrderListViewSet,
    ProductViewSet,
    ping,
    FAQViewSet,
    NoticeViewSet,
    BannerViewSet,
)


router = routers.DefaultRouter()

urlpatterns = [
    path("products/", ProductViewSet.as_view({"get": "list"})),
    path("products/<int:pk>", ProductViewSet.as_view({"get": "retrieve"})),
    path("orders/", OrderListViewSet.as_view({"get": "list"})),
    path("faqs/", FAQViewSet.as_view({"get": "list"})),
    path("notices/", NoticeViewSet.as_view({"get": "list"})),
    path("banners/", BannerViewSet.as_view({"get": "list"})),
    path("ping/", ping, name="ping"),
]
