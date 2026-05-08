import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import mixins, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from phone.external_services.channel_talk import send_calculator_lead_alert
from phone.models import CalculatorSession
from phone.serializers import (
    CalculatorSessionCreateSerializer,
    CalculatorSessionDetailSerializer,
    CalculatorSessionPatchSerializer,
    CustomerIdentityCreateSerializer,
)

logger = logging.getLogger("phone")


PATCH_ALLOWED_FIELDS = {
    "contact_channel",
    "submitted_name",
    "submitted_contact",
    "copy_variant_v3",
    "name_field_omitted",
}


class CalculatorSessionViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """Calculator 세션 CRUD (POST 생성, PATCH lead 업데이트, GET 조회)."""

    queryset = CalculatorSession.objects.all()
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "create":
            return CalculatorSessionCreateSerializer
        if self.action in ("partial_update", "update"):
            return CalculatorSessionPatchSerializer
        return CalculatorSessionDetailSerializer

    @swagger_auto_schema(
        operation_summary="Calculator 세션 생성 (result_view 시점)",
        tags=["Calculator"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if settings.DEBUG:
            return Response(
                {"id": None, "debug_skipped": True},
                status=status.HTTP_200_OK,
            )
        instance = serializer.save()
        return Response({"id": str(instance.id)}, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="Lead 정보 PATCH (submit / 카톡 클릭)",
        tags=["Calculator"],
    )
    def partial_update(self, request, *args, **kwargs):
        pk = kwargs[self.lookup_field]
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if settings.DEBUG:
            return Response(
                {"id": str(pk), "debug_skipped": True},
                status=status.HTTP_200_OK,
            )

        # PII 빈문자열 정규화는 serializer 가 처리:
        #   - phone 분기: '' → ValidationError (rejected before reaching view)
        #   - kakao 분기: submitted_* attrs.pop() (validated_data 에서 제거)
        fields = {
            key: value
            for key, value in serializer.validated_data.items()
            if key in PATCH_ALLOWED_FIELDS
        }
        fields["updated_at"] = timezone.now()

        affected = CalculatorSession.objects.filter(
            id=pk,
            contact_channel__isnull=True,
            deleted_at__isnull=True,
        ).update(**fields)

        instance = get_object_or_404(CalculatorSession, id=pk)
        applied = affected == 1
        if not applied:
            logger.warning(
                "first_write_wins.ignored session_id=%s attempted=%s",
                pk,
                fields.get("contact_channel"),
            )
        else:
            # 첫 lead 결정 시에만 운영팀 채널 알림. 실패해도 응답은 정상.
            try:
                send_calculator_lead_alert(
                    session_id=str(instance.id),
                    contact_channel=instance.contact_channel,
                    customer_name=instance.submitted_name,
                    customer_phone=instance.submitted_contact,
                    device_name=instance.device_name,
                    pio_total=instance.pio_total,
                    total_saving=instance.total_saving,
                    funnel_variant=instance.funnel_variant,
                )
            except Exception:
                logger.exception(
                    "calculator_lead_alert.failed session_id=%s", instance.id
                )

        data = CalculatorSessionDetailSerializer(
            instance, context={"applied": applied}
        ).data
        response = Response(data, status=status.HTTP_200_OK)
        response["ETag"] = f'W/"{instance.updated_at.isoformat()}"'
        return response


class CustomerIdentityCreateView(APIView):
    """V1 placeholder. POST /calculator-sessions/<id>/identity"""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @swagger_auto_schema(
        operation_summary="V1 사전 식별 (placeholder)",
        tags=["Calculator"],
    )
    def post(self, request, id):
        if settings.DEBUG:
            serializer = CustomerIdentityCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            return Response(
                {**serializer.validated_data, "debug_skipped": True},
                status=status.HTTP_200_OK,
            )
        session = get_object_or_404(CalculatorSession, id=id)
        if hasattr(session, "identity"):
            return Response(
                {"detail": "identity already exists"},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = CustomerIdentityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(session=session, identified_at=timezone.now())
        return Response(serializer.data, status=status.HTTP_201_CREATED)
