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
]
