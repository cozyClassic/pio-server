from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from phone.serializers import (
    PriceNotificationRequestSerializer,
    PriceNotificationRequestCreateSerializer,
)
from phone.models import (
    PriceNotificationRequest,
    PriceHistory,
    Product,
    DeviceVariant,
)
from phone.constants import CarrierChoices


class PriceNotificationRequestViewSet(ModelViewSet):
    serializer_class = PriceNotificationRequestSerializer
    queryset = PriceNotificationRequest.objects.all()
    permission_classes = [AllowAny]

    def _check_duplicate_notification(self, customer_phone, product_id):
        if not customer_phone or not product_id:
            return False
        return PriceNotificationRequest.objects.filter(
            customer_phone=customer_phone,
            product_id=product_id,
            notified_at__isnull=True,
        ).exists()

    @swagger_auto_schema(
        operation_summary="가격 알림 신청",
        request_body=PriceNotificationRequestCreateSerializer,
        responses={
            201: PriceNotificationRequestSerializer,
            400: "유효성 검증 실패",
            401: "중복 알림 신청",
        },
        tags=["가격알림"],
    )
    def create(self, request, *args, **kwargs):
        if self._check_duplicate_notification(
            request.data.get("customer_phone"),
            request.data.get("product_id"),
        ):
            return Response(
                {"error": "이미 해당 상품에 대한 알림 신청이 존재합니다."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = PriceNotificationRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_summary="가격 알림 신청 목록 조회",
        manual_parameters=[
            openapi.Parameter(
                "customer_phone",
                openapi.IN_QUERY,
                description="고객 전화번호 (필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: PriceNotificationRequestSerializer(many=True),
            400: "customer_phone 누락",
        },
        tags=["가격알림"],
    )
    def list(self, request: Request, *args, **kwargs):
        if customer_phone := request.query_params.get("customer_phone", None):
            self.queryset = self.queryset.filter(customer_phone=customer_phone)
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        return Response(
            {"error": "param customer_phone required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @swagger_auto_schema(
        operation_summary="가격 알림 삭제",
        responses={204: "삭제 성공", 404: "알림 없음"},
        tags=["가격알림"],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class PriceHistoryChartViewSet(GenericViewSet):
    """가격 변동 차트 데이터를 제공하는 ViewSet"""

    permission_classes = [AllowAny]

    PERIOD_DAYS = {
        "1week": 7,
        "1month": 30,
        "3months": 90,
        "6months": 180,
        "1year": 365,
    }

    @swagger_auto_schema(
        operation_summary="가격 변동 차트 데이터 조회",
        manual_parameters=[
            openapi.Parameter(
                "product_id",
                openapi.IN_QUERY,
                description="상품 ID (필수)",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                "period",
                openapi.IN_QUERY,
                description="조회 기간",
                type=openapi.TYPE_STRING,
                required=False,
                default="1month",
                enum=["1week", "1month", "3months", "6months", "1year"],
            ),
        ],
        responses={200: "성공", 400: "파라미터 오류", 404: "상품 없음"},
        tags=["가격차트"],
    )
    def list(self, request, *args, **kwargs):
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id 파라미터가 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except ValueError:
            return Response(
                {"error": "product_id는 정수여야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = request.query_params.get("period", "1month")
        if period not in self.PERIOD_DAYS:
            return Response(
                {
                    "error": f"유효하지 않은 period입니다. 가능한 값: {list(self.PERIOD_DAYS.keys())}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.select_related("device").get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "상품을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        smallest_variant = (
            DeviceVariant.objects.filter(device=product.device)
            .order_by("device_price")
            .first()
        )

        storage = smallest_variant.storage_capacity if smallest_variant else "N/A"

        days = self.PERIOD_DAYS[period]
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        carriers = [CarrierChoices.SK, CarrierChoices.KT, CarrierChoices.LG]
        last_known_prices = {}
        last_known_plans = {}

        for carrier in carriers:
            initial_price = (
                PriceHistory.objects.filter(
                    product=product,
                    carrier=carrier,
                    price_at__lt=start_date,
                )
                .select_related("plan")
                .order_by("-price_at")
                .first()
            )
            if initial_price:
                last_known_prices[carrier] = initial_price.final_price
                last_known_plans[carrier] = initial_price.plan
            else:
                last_known_prices[carrier] = None
                last_known_plans[carrier] = None

        price_histories = (
            PriceHistory.objects.filter(
                product=product,
                price_at__gte=start_date,
                price_at__lte=end_date,
            )
            .select_related("plan")
            .order_by("price_at")
        )

        price_changes = {}
        for ph in price_histories:
            date_str = ph.price_at.strftime("%Y-%m-%d")
            if date_str not in price_changes:
                price_changes[date_str] = {}
            price_changes[date_str][ph.carrier] = {
                "price": ph.final_price,
                "plan": ph.plan,
            }

        chart_data = []
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            if date_str in price_changes:
                for carrier, data in price_changes[date_str].items():
                    last_known_prices[carrier] = data["price"]
                    last_known_plans[carrier] = data["plan"]

            chart_data.append(
                {
                    "date": date_str,
                    "SK": last_known_prices.get(CarrierChoices.SK),
                    "KT": last_known_prices.get(CarrierChoices.KT),
                    "LG": last_known_prices.get(CarrierChoices.LG),
                }
            )

            current_date += timedelta(days=1)

        latest_prices = {}
        for carrier in carriers:
            if last_known_prices.get(carrier) is not None and last_known_plans.get(
                carrier
            ):
                latest_prices[carrier] = {
                    "price": last_known_prices[carrier],
                    "plan_name": last_known_plans[carrier].name,
                    "plan_price": last_known_plans[carrier].price,
                }
            else:
                latest_prices[carrier] = None

        return Response(
            {
                "product_name": product.name,
                "storage": storage,
                "period": period,
                "chart_data": chart_data,
                "latest_prices": latest_prices,
            }
        )
