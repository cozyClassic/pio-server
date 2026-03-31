from rest_framework.viewsets import GenericViewSet
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import mixins, status
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from phone.serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
)
from phone.models import Order, CreditCheckAgreement
from phone.external_services.channel_talk import (
    send_credit_check_alert,
    send_order_alert,
)

from .helpers import clean_phone_num


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    """
    Viewset for managing orders.
    """

    serializer_class = OrderSerializer
    permission_classes = [AllowAny]
    queryset = Order.objects.all()

    def get_queryset(self):
        return self.queryset

    @swagger_auto_schema(
        operation_summary="주문 목록 조회",
        operation_description="고객 전화번호+이름으로 주문 목록을 조회합니다.",
        manual_parameters=[
            openapi.Parameter(
                "phone",
                openapi.IN_QUERY,
                description="고객 전화번호 (필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "customer_name",
                openapi.IN_QUERY,
                description="고객 이름 (필수)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
            openapi.Parameter(
                "order_id",
                openapi.IN_QUERY,
                description="특정 주문 ID 필터",
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={
            200: OrderSerializer(many=True),
            400: "phone 또는 customer_name 누락",
            404: "주문 없음",
        },
        tags=["주문"],
    )
    def list(self, request, *args, **kwargs):
        phone = request.query_params.get("phone", None)
        if not phone:
            return Response({"error": "param phone required"}, status=400)
        customer_name = request.query_params.get("customer_name", None)
        if not customer_name:
            return Response({"error": "param customer_name required"}, status=400)
        where_text = f"o.deleted_at IS NULL AND o.status != '취소완료' AND o.customer_name='{customer_name}' AND o.customer_phone='{phone}'"

        order_id = request.query_params.get("order_id", None)
        if order_id:
            where_text += f" AND o.id={order_id}"
        phone = clean_phone_num(phone)
        orders = Order.objects.raw(f"""
SELECT DISTINCT ON (o.id) ci.image, c.color_code, o.*
FROM phone_order o
JOIN phone_product p
    ON p.id = o.product_id
JOIN phone_devicecolor c
    ON c.device_id = p.device_id
    AND o.color = c.color
    AND c.deleted_at IS NULL
JOIN phone_devicescolorimage ci
    ON ci.device_color_id = c.id
    AND ci.deleted_at IS NULL
WHERE
    {where_text}
ORDER BY o.id, ci.id;
""")

        if len(orders) == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(orders, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_summary="주문 생성",
        operation_description="새 주문을 생성합니다. 생성 시 Channel Talk 알림 발송.",
        request_body=OrderCreateSerializer,
        responses={
            201: openapi.Response(
                description="주문 생성 성공", examples={"application/json": {"id": 123}}
            )
        },
        tags=["주문"],
    )
    def create(self, request, *args, **kwargs):
        body = request.data
        customer_phone = clean_phone_num(body.get("customer_phone"))
        customer_phone2 = clean_phone_num(body.get("customer_phone2"))

        new_order = Order.objects.create(
            customer_name=body.get("customer_name"),
            customer_phone=customer_phone,
            customer_phone2=customer_phone2,
            customer_email=body.get("customer_email"),
            customer_birth=body.get("customer_birth"),
            product_id=body.get("product_id"),
            plan_id=body.get("plan_id"),
            contract_type=body.get("contract_type"),
            device_price=body.get("device_price"),
            plan_monthly_fee=body.get("plan_monthly_fee"),
            subsidy_standard=body.get("subsidy_standard"),
            subsidy_mnp=body.get("subsidy_mnp"),
            payment_period=body.get("payment_period"),
            final_price=body.get("final_price"),
            discount_type=body.get("discount_type"),
            monthly_discount=body.get("monthly_discount"),
            additional_discount=body.get("additional_discount"),
            storage_capacity=body.get("storage_capacity"),
            color=body.get("color"),
            customer_memo=body.get("customer_memo"),
            shipping_address=body.get("shipping_address"),
            shipping_address_detail=body.get("shipping_address_detail"),
            zipcode=body.get("zipcode"),
            ga4_id=body.get("ga4_id", ""),
            prev_carrier=body.get("prev_carrier", ""),
            channeltalk_user_id=body.get("channeltalk_user_id", ""),
        )
        new_order.save()
        send_order_alert(
            order_id=new_order.id,
            customer_name=new_order.customer_name,
            customer_phone=new_order.customer_phone,
        )
        return Response({"id": new_order.id}, status=201)

    @swagger_auto_schema(
        operation_summary="주문 상세 조회",
        responses={200: OrderDetailSerializer, 404: "주문을 찾을 수 없음"},
        tags=["주문"],
    )
    def retrieve(self, request, *args, **kwargs):
        queryset = Order.objects.raw(
            """
            SELECT DISTINCT ON (o.id) ci.image, c.color_code, o.*
            FROM phone_order o
            JOIN phone_product p
                ON p.id = o.product_id
            JOIN phone_devicecolor c
                ON c.device_id = p.device_id
                AND o.color = c.color
                AND c.deleted_at IS NULL
            JOIN phone_devicescolorimage ci
                ON ci.device_color_id = c.id
                AND ci.deleted_at IS NULL
            LEFT JOIN phone_creditcheckagreement cca
                ON cca.order_id = o.id
                AND cca.deleted_at IS NULL
            WHERE
                o.deleted_at IS NULL
                AND o.id = %s
            ORDER BY o.id, ci.id;
            """,
            [kwargs.get("pk")],
        )

        if len(queryset) == 0:
            return Response(data="order not found", status=status.HTTP_404_NOT_FOUND)

        serializer = OrderDetailSerializer(queryset[0])
        return Response(serializer.data)


class OrderCreditCheckView(APIView):
    """신용조회 동의서 이미지 업로드 API"""

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="신용조회 동의서 업로드",
        manual_parameters=[
            openapi.Parameter(
                "credit_check_agreement",
                openapi.IN_FORM,
                description="신용조회 동의서 이미지 파일",
                type=openapi.TYPE_FILE,
                required=True,
            ),
        ],
        responses={200: "업로드 성공", 400: "이미지 파일 필요", 404: "주문 없음"},
        consumes=["multipart/form-data"],
        tags=["주문"],
    )
    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {"error": "주문을 찾을 수 없습니다."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if len(request.FILES) == 0:
            return Response(
                {"error": "credit_check_agreement 이미지 파일이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_agreements = []
        for index, image_file in enumerate(request.FILES.values()):
            image_file.name = (
                f"order_{pk}_{order.customer_phone}_credit_check_{index + 1}.png"
            )
            agreement = CreditCheckAgreement.objects.create(
                order=order,
                image=image_file,
            )
            created_agreements.append(agreement.image.url)
        send_credit_check_alert(pk, order.customer_name, order.customer_phone)

        return Response(
            {
                "message": f"신용조회 동의서 {len(created_agreements)}장이 업로드되었습니다.",
                "credit_check_agreements": created_agreements,
            },
            status=status.HTTP_200_OK,
        )
