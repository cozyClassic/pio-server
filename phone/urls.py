from django.urls import include, path
from rest_framework import routers

from .views import ProductViewSet, ping


router = routers.DefaultRouter()
router.register(r"products", ProductViewSet, basename="products")

urlpatterns = [
    path("", include(router.urls)),
    path("ping/", ping, name="ping"),
]
