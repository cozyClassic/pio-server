from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from django.db.models import Prefetch, Subquery, OuterRef
from drf_yasg.utils import swagger_auto_schema
from datetime import timedelta
from django.utils import timezone
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import AllowAny
from rest_framework import status

from phone.serializers import (
    DeviceSerializer,
    DeviceVairantSimpleSerializer,
    PlanSerializer,
)
from phone.models import (
    Device,
    DeviceVariant,
    DevicesColorImage,
    Plan,
)


class DeviceViewSet(ReadOnlyModelViewSet):
    """단말기 목록 API"""

    serializer_class = DeviceSerializer

    @swagger_auto_schema(
        operation_summary="단말기 목록 조회",
        responses={200: DeviceSerializer(many=True)},
        tags=["단말기"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    queryset = (
        Device.objects.all()
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=DeviceVariant.objects.all(),
            ),
        )
        .annotate(
            first_image_url=Subquery(
                DevicesColorImage.objects.filter(
                    device_color__device=OuterRef("pk"),
                )
                .order_by("device_color__id", "id")
                .values("image")[:1]
            )
        )
    )


class PhonePlanViewSet(ReadOnlyModelViewSet):
    """요금제 목록 API"""

    serializer_class = PlanSerializer
    queryset = Plan.objects.all()

    @swagger_auto_schema(
        operation_summary="요금제 목록 조회",
        responses={200: PlanSerializer(many=True)},
        tags=["요금제"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
