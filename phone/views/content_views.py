from rest_framework.viewsets import ReadOnlyModelViewSet, GenericViewSet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.filters import OrderingFilter
from rest_framework import mixins, status
from django.db.models import Prefetch, QuerySet
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from phone.serializers import (
    FAQSerializer,
    NoticeSerializer,
    BannerSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
    PolicyDocumentSerializer,
    PartnerCardSerializer,
    EventSimpleSerializer,
    EventSerializer,
)
from phone.models import (
    FAQ,
    Notice,
    Banner,
    Review,
    PolicyDocument,
    PartnerCard,
    CardBenefit,
    Event,
)


class FAQViewSet(ReadOnlyModelViewSet):
    """FAQ 목록 조회 API"""

    queryset = FAQ.objects.all().order_by("sort_order")
    serializer_class = FAQSerializer

    @swagger_auto_schema(
        operation_summary="FAQ 목록 조회",
        responses={200: FAQSerializer(many=True)},
        tags=["FAQ"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class NoticeViewSet(ReadOnlyModelViewSet):
    serializer_class = NoticeSerializer
    queryset = Notice.objects.all().order_by("-created_at")

    @swagger_auto_schema(
        operation_summary="공지사항 목록 조회",
        manual_parameters=[
            openapi.Parameter(
                "type",
                openapi.IN_QUERY,
                description="공지사항 유형(필수)",
                type=openapi.TYPE_STRING,
                required=True,
                enum=["caution", "event", "general"],
            ),
        ],
        responses={200: NoticeSerializer(many=True)},
        tags=["공지사항"],
    )
    def list(self, request: Request, *args, **kwargs):
        queryset: QuerySet[Notice] = self.filter_queryset(self.get_queryset())
        notice_type = request.query_params.get("type", None)
        if notice_type:
            queryset = queryset.filter(type=notice_type)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="공지사항 상세 조회",
        responses={200: NoticeSerializer, 404: "공지사항을 찾을 수 없음"},
        tags=["공지사항"],
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class BannerViewSet(ReadOnlyModelViewSet):
    """배너 목록 API"""

    serializer_class = BannerSerializer
    queryset = Banner.objects.all().filter(is_active=True).order_by("-sort_order")
    filter_backends = [OrderingFilter]
    ordering_fields = ["sort_order", "sort_order_test"]

    @swagger_auto_schema(
        operation_summary="활성 배너 목록 조회",
        responses={200: BannerSerializer(many=True)},
        tags=["배너"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    """상품 리뷰 API"""

    serializer_class = ReviewSerializer
    queryset = (
        Review.objects.all()
        .filter(is_public=True)
        .select_related("product")
        .prefetch_related("product__images")
        .order_by("-created_at")
    )
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="리뷰 목록 조회",
        responses={200: ReviewSerializer(many=True)},
        tags=["리뷰"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="리뷰 생성",
        request_body=ReviewCreateSerializer,
        responses={201: "리뷰 생성 성공", 400: "잘못된 요청 데이터"},
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                "product_id",
                openapi.IN_FORM,
                description="상품id",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                "customer_name",
                openapi.IN_FORM,
                description="고객명",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "rating",
                openapi.IN_FORM,
                description="평점 (1-5)",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                "comment",
                openapi.IN_FORM,
                description="리뷰 내용",
                type=openapi.TYPE_STRING,
                required=False,
            ),
            openapi.Parameter(
                "image",
                openapi.IN_FORM,
                description="리뷰 이미지 파일",
                type=openapi.TYPE_FILE,
                required=False,
            ),
        ],
        tags=["리뷰"],
    )
    def create(self, request, *args, **kwargs):
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PolicyDocumentViewSet(ReadOnlyModelViewSet):
    """약관/개인정보처리방침 API"""

    serializer_class = PolicyDocumentSerializer
    queryset = PolicyDocument.objects.all().order_by("-created_at")

    @swagger_auto_schema(
        operation_summary="약관/개인정보처리방침 목록",
        responses={200: PolicyDocumentSerializer(many=True)},
        tags=["약관"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="약관 상세 조회",
        responses={200: PolicyDocumentSerializer, 404: "문서를 찾을 수 없음"},
        tags=["약관"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class PartnerCardViewSet(ReadOnlyModelViewSet):
    """제휴 카드 API"""

    serializer_class = PartnerCardSerializer
    queryset = (
        PartnerCard.objects.all().filter(is_active=True).order_by("sort_order")
    ).prefetch_related(
        Prefetch(
            "card_benefits",
            queryset=CardBenefit.objects.filter(is_optional=False),
        )
    )

    @swagger_auto_schema(
        operation_summary="제휴 카드 목록 조회",
        responses={200: PartnerCardSerializer(many=True)},
        tags=["제휴카드"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class EventViewSet(ReadOnlyModelViewSet):
    """이벤트 API"""

    serializer_class = EventSimpleSerializer
    queryset = Event.objects.all().filter(is_active=True)

    @swagger_auto_schema(
        operation_summary="이벤트 목록 조회",
        responses={200: EventSimpleSerializer(many=True)},
        tags=["이벤트"],
    )
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset().order_by("-start_date"))
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="이벤트 상세 조회",
        responses={200: EventSerializer, 404: "이벤트를 찾을 수 없음"},
        tags=["이벤트"],
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = EventSerializer(instance)
        return Response(serializer.data)
