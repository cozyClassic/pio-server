# Create your views here.

from rest_framework.viewsets import ReadOnlyModelViewSet, ModelViewSet
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Prefetch
from .models import InternetCarrier, InternetPlan
from .serializers import *


class InternetCarrierViewSet(ReadOnlyModelViewSet):
    queryset = InternetCarrier.objects.all()
    serializer_class = InternetCarrierSerializer


class InternetPlanView(APIView):
    queryset = InternetPlan.objects.all().order_by("internet_price_per_month")

    def get(self, request, format=None):
        queryset = self.queryset.prefetch_related(
            Prefetch(
                "bundle_conditions",
                queryset=BundleCondition.objects.prefetch_related(
                    "bundle_discounts", "bundle_promotions"
                ).select_related("tv_plan"),
            )
        ).select_related("carrier")

        serializer = InternetPlanSerializer(
            queryset,
        )
        return Response(serializer.data)


class InquiryCreateView(ModelViewSet):
    queryset = Inquiry.objects.all()
    serializer_class = InquiryCreateSerializer
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        serializer = InquiryCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Inquiry created successfully."}, status=201)
        return Response(serializer.errors, status=400)
