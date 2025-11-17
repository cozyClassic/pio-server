from django.shortcuts import render

# Create your views here.

from rest_framework.viewsets import ReadOnlyModelViewSet
from django.db.models import Prefetch
from .models import InternetCarrier, InternetPlan
from .serializers import *


class InternetCarrierViewSet(ReadOnlyModelViewSet):
    queryset = InternetCarrier.objects.all()
    serializer_class = InternetCarrierSerializer


class InternetPlanViewSet(ReadOnlyModelViewSet):
    queryset = InternetPlan.objects.prefetch_related(
        Prefetch(
            "bundle_coditions",
            queryset=BundleCondition.objects.prefetch_related(
                "bundle_discounts", "bundle_promotions"
            ),
        )
    ).all()

    serializer_class = InternetPlanSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
