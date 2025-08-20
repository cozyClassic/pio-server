from django.contrib import admin
import nested_admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from django.db.models import Prefetch, F
from django.contrib import admin
from django import forms

from .models import (
    Plan,
    Device,
    DeviceColor,
    DeviceVariant,
    Product,
    ProductOption,
    ProductDetailImage,
    DevicesColorImage,
    Order,
    FAQ,
    Notice,
    Review,
    Banner,
)


class commonAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at", "deleted_at")


@admin.register(Plan)
class PlanAdmin(commonAdmin):
    list_display = (
        "name",
        "price",
        "data_allowance",
        "call_allowance",
        "sms_allowance",
    )
    search_fields = ("name",)


# 2. DevicesColorImages 모델을 위한 인라인 클래스
class DeviceImagesInline(nested_admin.NestedStackedInline):
    model = DevicesColorImage
    extra = 0
    exclude = ("deleted_at",)

    readonly_fields = ("image_preview",)

    # 이미지 미리보기를 위한 커스텀 메서드
    def image_preview(self, obj):
        # 이미지가 있을 경우에만 미리보기를 보여줍니다.
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.image.url,
            )
        return "이미지 없음"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(deleted_at__isnull=True)

    # 메서드에 짧은 설명을 붙여 Admin 페이지에 표시될 이름으로 사용
    image_preview.short_description = "미리보기"


class ColorsInline(nested_admin.NestedStackedInline):
    model = DeviceColor
    extra = 0  # 기본으로 1개의 빈 폼을 더 보여줍니다.
    # SoftDeleteModel의 deleted_at 필드를 숨깁니다.
    exclude = ("deleted_at",)

    inlines = [DeviceImagesInline]


@admin.register(Device)
class DeviceAdmin(commonAdmin, nested_admin.NestedModelAdmin):
    list_display = ("model_name", "brand")
    search_fields = ("model_name", "brand")

    inlines = [ColorsInline]


@admin.register(DeviceColor)
class DeviceColorsAdmin(commonAdmin):
    list_display = ("device", "color", "color_code")
    search_fields = ("device__name", "color")


@admin.register(DeviceVariant)
class DeviceVariantsAdmin(commonAdmin):
    list_display = ("device", "storage_capacity", "device_price")
    search_fields = ("device__name", "storage_capacity")


class ProductOptionsInline(nested_admin.NestedTabularInline):
    model = ProductOption
    extra = 0
    exclude = ("deleted_at",)
    readonly_fields = (
        "device_storage",
        "final_price",
        "custom_plan_carrier",
        "custom_plan_name",
        "discount_type",
        "contract_type",
        "subsidy_amount",
        "subsidy_amount_mnp",
        "additional_discount",
    )

    # 필드 순서 지정 (커스텀 필드들 포함)
    fields = (
        "device_storage",
        "custom_plan_carrier",
        "discount_type",
        "contract_type",
        "custom_plan_name",
        "subsidy_amount",
        "subsidy_amount_mnp",
        "additional_discount",
        "final_price",
    )

    def custom_plan_carrier(self, obj):
        """올바른 방법: select_related로 이미 로드된 데이터 사용"""
        if not obj or not obj.plan:
            return "-"
        return obj.plan.carrier

    custom_plan_carrier.short_description = "통신사"

    def custom_plan_name(self, obj):
        """올바른 방법: select_related로 이미 로드된 데이터 사용"""
        if not obj or not obj.plan:
            return "-"
        return obj.plan.name

    def device_storage(self, obj):
        """N+1 방지: select_related된 device_variant 사용"""
        if not obj or not obj.device_variant:
            return "-"
        # device_variant와 device도 이미 로드되어 있음
        return (
            f"{obj.device_variant.storage_capacity} ({obj.device_variant.device.brand})"
        )

    device_storage.short_description = "저장용량 (브랜드)"

    # N+1 문제 해결을 위한 핵심: get_queryset 오버라이드
    def get_queryset(self, request):
        """
        Inline에서 사용할 queryset을 미리 최적화
        이렇게 하면 커스텀 필드에서 obj.plan.carrier 같은 접근이 추가 쿼리를 발생시키지 않음
        """
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "device_variant__device",  # device_variant와 device 함께 로드
            "plan",  # plan도 함께 로드
        ).prefetch_related(
            # 추가로 필요한 관계가 있다면 여기에 추가
        )


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [ProductOptionsInline]
    exclude = ("deleted_at",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return (
            queryset.filter(deleted_at__isnull=True).select_related("device")
            # N+1 문제 해결을 위한 최적화된 prefetch
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=ProductOption.objects.filter(deleted_at__isnull=True)
                    .select_related(
                        "device_variant__device",
                        "plan",  # 필요한 관계들을 모두 포함
                        "product",
                    )
                    .order_by(
                        "plan__carrier",
                        "discount_type",
                        "contract_type",
                        "plan__price",
                    ),
                ),
            )
        )


@admin.register(ProductOption)
class ProductOptionsAdmin(commonAdmin):
    list_display = ("product", "device_variant")
    search_fields = ("product__name", "device_variant__device__name")
    list_filter = ("product", "device_variant")


@admin.register(ProductDetailImage)
class ProductDetailImagesAdmin(commonAdmin):
    list_display = ("product", "image", "description")
    search_fields = ("product__name", "description")
    list_filter = ("product",)


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ("customer_name", "product", "status", "created_at")
    search_fields = ("user__username", "product__name")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at", "deleted_at")

    history_list_display = [
        "status",
        "admin_memo",
    ]

    history_list_per_page = 100


@admin.register(Review)
class ReviewAdmin(nested_admin.NestedModelAdmin):
    list_display = ("customer_name", "created_at")
    search_fields = ("created_at",)
    exclude = ("deleted_at",)


@admin.register(FAQ)
class FAQAdmin(commonAdmin):
    list_display = ("question", "answer", "created_at")
    search_fields = ("question", "answer")
    list_filter = ("created_at",)


@admin.register(Notice)
class NoticeAdmin(commonAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)


@admin.register(Banner)
class BannerAdmin(commonAdmin):
    list_display = ("title", "image", "created_at")
    search_fields = ("title",)
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
