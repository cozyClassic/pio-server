from django.urls import path
from rest_framework import routers

from .views import *


router = routers.DefaultRouter()

urlpatterns = [
    path("carriers", InternetCarrierViewSet.as_view({"get": "list"})),
    path("plans", InternetPlanView.as_view()),
    path("inquiries", InquiryCreateView.as_view({"post": "create"})),
]
