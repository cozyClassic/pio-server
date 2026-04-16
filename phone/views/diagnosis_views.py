from rest_framework.viewsets import GenericViewSet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import mixins, status
from drf_yasg.utils import swagger_auto_schema

from phone.serializers import DiagnosisLogSerializer, DiagnosisInquirySerializer
from phone.external_services.channel_talk import send_inquiry_alert


class DiagnosisLogViewSet(mixins.CreateModelMixin, GenericViewSet):
    """단말기 진단 로그 API"""

    serializer_class = DiagnosisLogSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="진단 로그 생성",
        request_body=DiagnosisLogSerializer,
        responses={201: "생성 성공"},
        tags=["진단"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED)


class DiagnosisInquiryViewSet(mixins.CreateModelMixin, GenericViewSet):
    """단말기 진단 문의 API"""

    serializer_class = DiagnosisInquirySerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="진단 문의 생성",
        request_body=DiagnosisInquirySerializer,
        responses={201: DiagnosisInquirySerializer, 400: "잘못된 데이터 형식"},
        tags=["진단"],
    )
    def create(self, request: Request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        body = request.data

        if not isinstance(body, dict):
            return Response(
                {"error": "Invalid data format"}, status=status.HTTP_400_BAD_REQUEST
            )

        send_inquiry_alert(
            customer_name=body.get("name", ""),
            customer_phone=body.get("contact", ""),
            device_name=body.get("device_name", ""),
            internet_new=body.get("internet_new", "true") == "true",
            card=body.get("card", "true") == "true",
            gift=body.get("gift", "true") == "true",
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
