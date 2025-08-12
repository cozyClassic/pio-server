from django.urls import path
from rest_framework import routers

from .views import (
    OrderViewSet,
    ProductViewSet,
    ping,
    FAQViewSet,
    NoticeViewSet,
    BannerViewSet,
    ReviewImageCreateView,
    ReviewViewSet,
)


router = routers.DefaultRouter()

urlpatterns = [
    path("products/", ProductViewSet.as_view({"get": "list"})),
    path("products/<int:pk>/", ProductViewSet.as_view({"get": "retrieve"})),
    path("orders/", OrderViewSet.as_view({"get": "list", "post": "create"})),
    path("faqs/", FAQViewSet.as_view({"get": "list"})),
    path("notices/", NoticeViewSet.as_view({"get": "list"})),
    path("banners/", BannerViewSet.as_view({"get": "list"})),
    path("ping/", ping, name="ping"),
    path("review_images/", ReviewImageCreateView.as_view({"post": "create"})),
    path("reviews/", ReviewViewSet.as_view({"get": "list", "post": "create"})),
]
