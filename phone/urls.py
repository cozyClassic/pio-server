from django.urls import include, path
from rest_framework import routers

from .views import OrderViewSet, ProductViewSet, ping, OrderViewSet


router = routers.DefaultRouter()
router.register(r"products", ProductViewSet, basename="products")
router.register(r"orders", OrderViewSet, basename="orders")

urlpatterns = [
    path("", include(router.urls)),
    path("ping/", ping, name="ping"),
]
