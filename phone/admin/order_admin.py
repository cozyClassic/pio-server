# pyright: reportAttributeAccessIssue=false
from datetime import timedelta
from django.contrib import admin, messages
from django.urls import path
from django.http import HttpResponseRedirect
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Subquery, OuterRef

import nested_admin
from simple_history.admin import SimpleHistoryAdmin

from phone.models import *
from phone.external_services.channel_talk import send_shipping_noti_to_customer
from .base import commonAdmin, format_price


class CreditCheckAgreeNestedInline(nested_admin.NestedStackedInline):
    model = CreditCheckAgreement
    exclude = ("deleted_at",)
    extra = 0


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = (
        "customer_name",
        "product",
        "status",
        "created_at",
        "customer_phone",
        "plan__carrier",
    )
    search_fields = ("user__username", "product__name")
    list_filter = ("status", "created_at")
    readonly_fields = (
        "created_at",
        "updated_at",
        "deleted_at",
        "ga4_id",
        "channeltalk_user_id",
    )
    inlines = [CreditCheckAgreeNestedInline]
    change_form_template = "admin/order_change_form.html"

    history_list_display = [
        "status",
        "admin_memo",
    ]

    history_list_per_page = 100

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/change/generate-format/",
                self.admin_site.admin_view(self.generate_format_view),
                name="order_generate_format",
            ),
            path(
                "<path:object_id>/change/send-shipping-notification/",
                self.admin_site.admin_view(self.send_shipping_notification),
                name="order_send_shipping_notification",
            ),
        ]
        return custom_urls + urls

    def send_shipping_notification(self, request, object_id):
        order = (
            Order.objects.filter(pk=object_id, deleted_at__isnull=True)
            .select_related(
                "product__device",
            )
            .first()
        )
        if not order:
            messages.error(request, "주문을 찾을 수 없습니다.")
            return HttpResponseRedirect(f"/admin/phone/order/")

        api_infos = {
            "customer_name": order.customer_name,
            "channeltalk_user_id": order.channeltalk_user_id,
            "customer_phone": order.customer_phone,
            "device_name": order.product.device.model_name,
            "shipping_number": order.shipping_number,
            "shipping_method": order.shipping_method,
        }

        if None in api_infos.values():
            none_objects = [key for key, value in api_infos.items() if value is None]
            messages.error(request, "배송 알림에 필요한 정보가 부족합니다.")
            messages.error(
                request,
                f"누락된 정보: {', '.join(none_objects)}",
            )
            return HttpResponseRedirect(f"/admin/phone/order/{object_id}/change/")

        send_shipping_noti_to_customer(**api_infos)

        return HttpResponseRedirect(f"/admin/phone/order/{object_id}/change/")

    def generate_format_view(self, request, object_id):
        """주문 데이터를 Dealer 양식에 맞게 생성"""
        from django.http import JsonResponse

        format_type = request.GET.get("type", "credit_check")

        try:
            order = Order.objects.select_related("product__device", "plan").get(
                pk=object_id, deleted_at__isnull=True
            )
        except Order.DoesNotExist:
            return JsonResponse({"error": "주문을 찾을 수 없습니다."}, status=404)

        # DeviceVariant 찾기
        device_variant = DeviceVariant.objects.filter(
            device=order.product.device,
            storage_capacity=str(order.storage_capacity),
            deleted_at__isnull=True,
        ).first()

        if not device_variant:
            return JsonResponse(
                {
                    "error": f"단말기 옵션을 찾을 수 없습니다. (용량: {order.storage_capacity})"
                }
            )

        # ProductOption에서 Dealer 찾기
        product_option = (
            ProductOption.objects.filter(
                product=order.product,
                device_variant=device_variant,
                plan=order.plan,
                contract_type=order.contract_type,
                discount_type=order.discount_type,
                deleted_at__isnull=True,
            )
            .select_related("dealer")
            .first()
        )

        if not product_option:
            return JsonResponse(
                {"error": "해당 주문에 맞는 상품 옵션을 찾을 수 없습니다."}
            )

        if not product_option.dealer:
            return JsonResponse(
                {"error": "해당 상품 옵션에 대리점이 지정되지 않았습니다."}
            )

        dealer = product_option.dealer

        # 포맷 템플릿 선택
        if format_type == "credit_check":
            format_template = dealer.credit_check_agree_format
            if not format_template:
                return JsonResponse(
                    {
                        "error": f"'{dealer.name}' 대리점에 신용조회 양식이 설정되지 않았습니다."
                    }
                )
        else:
            format_template = dealer.opening_request_format
            if not format_template:
                return JsonResponse(
                    {
                        "error": f"'{dealer.name}' 대리점에 개통요청 양식이 설정되지 않았습니다."
                    }
                )

        # 치환용 데이터 준비
        format_data = {
            # 고객 정보
            "customer_name": order.customer_name or "",
            "customer_phone": order.customer_phone or "",
            "customer_phone2": order.customer_phone2 or "",
            "customer_email": order.customer_email or "",
            "customer_birth": (
                order.customer_birth.strftime("%Y%m%d")[2:]
                if order.customer_birth
                else ""
            ),
            # 상품 정보
            "product_name": order.product.name or "",
            "device_name": order.product.device.model_name or "",
            "plan_name": order.plan.name or "",
            "plan_carrier": order.plan.carrier or "",
            "plan_price": format_price(order.plan.price),
            "storage_capacity": str(order.storage_capacity) or "",
            "color": order.color or "",
            # 계약 정보
            "contract_type": order.contract_type or "",
            "discount_type": order.discount_type or "",
            "payment_period": order.payment_period or "",
            "prev_carrier": order.prev_carrier or "",
            # 가격 정보
            "device_price": format_price(order.device_price),
            "final_price": format_price(order.final_price),
            "subsidy_standard": format_price(order.subsidy_standard),
            "subsidy_mnp": format_price(order.subsidy_mnp),
            "additional_discount": format_price(order.additional_discount),
            "plan_monthly_fee": format_price(order.plan_monthly_fee),
            "monthly_discount": format_price(order.monthly_discount),
            # 배송 정보
            "shipping_address": order.shipping_address or "",
            "shipping_address_detail": order.shipping_address_detail or "",
            "zipcode": order.zipcode or "",
            # 기타
            "customer_memo": order.customer_memo or "",
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "order_id": str(order.id),
            # 대리점 정보
            "dealer_name": dealer.name or "",
            "dealer_contact": dealer.contact_number or "",
            "dealer_manager": dealer.manager or "",
        }

        try:
            formatted_text = format_template.format(**format_data)
        except KeyError as e:
            return JsonResponse({"error": f"양식에 알 수 없는 변수가 있습니다: {e}"})

        return JsonResponse({"formatted_text": formatted_text})

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(deleted_at__isnull=True)
            .select_related("plan", "product")
            .prefetch_related("credit_check_agreements")
            .exclude(status="취소완료")
        )


@admin.register(Order.history.model)
class CompletedOrderHistoryAdmin(admin.ModelAdmin):
    """
    개통완료된 주문의 히스토리를 보여주는 Admin
    - 개통완료 날짜
    - 개통완료 + 185일 (약정 해지 가능일 등)
    """

    list_display = [
        "order_id",
        "customer_name",
        "customer_phone",
        "product",
        "plan_carrier",
        "completed_date",
        "day_185_later",
        "days_remaining",
    ]
    list_filter = ["history_date"]
    search_fields = ["customer_name", "customer_phone", "id"]
    ordering = ["-history_date"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def order_id(self, obj):
        return obj.id

    order_id.short_description = "주문 ID"

    def plan_carrier(self, obj):
        if obj.plan:
            return obj.plan.carrier
        return "-"

    plan_carrier.short_description = "통신사"

    def completed_date(self, obj):
        return obj.history_date.strftime("%Y-%m-%d %H:%M")

    completed_date.short_description = "개통완료일"
    completed_date.admin_order_field = "history_date"

    def day_185_later(self, obj):
        target_date = obj.history_date + timedelta(days=185)
        return target_date.strftime("%Y-%m-%d")

    day_185_later.short_description = "185일 후"

    def days_remaining(self, obj):
        target_date = obj.history_date + timedelta(days=185)
        today = timezone.now()
        remaining = (target_date - today).days

        if remaining < 0:
            return format_html(
                '<span style="color: green;">완료 ({}일 경과)</span>', abs(remaining)
            )
        elif remaining <= 14:
            return format_html(
                '<span style="color: red; font-weight: bold;">{}일 남음</span>',
                remaining,
            )
        elif remaining <= 30:
            return format_html(
                '<span style="color: orange;">{}일 남음</span>', remaining
            )
        else:
            return f"{remaining}일 남음"

    days_remaining.short_description = "남은 일수"

    def get_queryset(self, request):
        """
        각 Order별로 status='개통완료'가 된 첫 번째 시점만 가져옴
        """
        HistoricalOrder = Order.history.model

        # 각 Order ID별로 개통완료가 된 가장 이른 시점의 history_id를 찾음
        first_completed_subquery = (
            HistoricalOrder.objects.filter(
                id=OuterRef("id"),
                status="개통완료",
            )
            .order_by("history_date")
            .values("history_id")[:1]
        )

        # 개통완료 상태인 레코드 중 첫 번째 것만 필터링
        queryset = (
            HistoricalOrder.objects.filter(status="개통완료")
            .filter(history_id=Subquery(first_completed_subquery))
            .select_related("plan", "product")
            .order_by("-history_date")
        )

        return queryset


@admin.register(DiagnosisInquiry)
class DiagnosisInquiryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "contact",
        "prev_carrier",
        "device_name",
        "total_saving",
        "created_at",
    )
    list_filter = ("prev_carrier", "created_at")
    search_fields = ("name", "contact", "device_name")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    ordering = ("-created_at",)
