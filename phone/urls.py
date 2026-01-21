from django.urls import path
from rest_framework import routers

from .views import *


router = routers.DefaultRouter()

urlpatterns = [
    path("products", ProductViewSet.as_view({"get": "list"})),
    path("products/<int:pk>", ProductViewSet.as_view({"get": "retrieve"})),
    path("product-series", ProductSeriesViewSet.as_view({"get": "list"})),
    path("orders", OrderViewSet.as_view({"get": "list", "post": "create"})),
    path("orders/<int:pk>", OrderViewSet.as_view({"get": "retrieve"})),
    path("orders/<int:pk>/credit-check", OrderCreditCheckView.as_view()),
    path("faqs", FAQViewSet.as_view({"get": "list"})),
    path("notices", NoticeViewSet.as_view({"get": "list"})),
    path("notices/<int:pk>", NoticeViewSet.as_view({"get": "retrieve"})),
    path("banners", BannerViewSet.as_view({"get": "list"})),
    path("ping", ping, name="ping"),
    path("reviews", ReviewViewSet.as_view({"get": "list", "post": "create"})),
    path("policies", PolicyDocumentViewSet.as_view({"get": "list"})),
    path("policies/<int:pk>", PolicyDocumentViewSet.as_view({"get": "retrieve"})),
    path("events", EventViewSet.as_view({"get": "list"})),
    path("events/<int:pk>", EventViewSet.as_view({"get": "retrieve"})),
    path("partner-cards", PartnerCardViewSet.as_view({"get": "list"})),
    path("tinymce/upload/", tinymce_upload, name="tinymce-upload"),
    path("devices", DeviceViewSet.as_view({"get": "list"})),
    path("plans", PhonePlanViewSet.as_view({"get": "list"})),
    path("product-options", ProductOptionViewSet.as_view({"get": "list"})),
    path(
        "price-notification-requests/<int:pk>",
        PriceNotificationRequestViewSet.as_view({"delete": "destroy"}),
    ),
    path(
        "price-notification-requests",
        PriceNotificationRequestViewSet.as_view({"get": "list", "post": "create"}),
    ),
    path(
        "price-history-chart",
        PriceHistoryChartViewSet.as_view({"get": "list"}),
    ),
]
