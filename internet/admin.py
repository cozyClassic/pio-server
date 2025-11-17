from django.contrib import admin

# Register your models here.
import nested_admin
from .models import *

admin.site.register(InternetCarrier)
admin.site.register(InternetPlan)
admin.site.register(TVPlan)


class BundlePromotionInline(nested_admin.NestedStackedInline):
    model = BundlePromotion
    min_num = 1
    max_num = 1


class BundleDiscountInline(nested_admin.NestedStackedInline):
    model = BundleDiscount
    extra = 1


@admin.register(BundleCondition)
class BundleConditionAdmin(nested_admin.NestedModelAdmin):
    inlines = [BundleDiscountInline, BundlePromotionInline]


@admin.register(CombinedDataView)
class CombinedDataAdmin(admin.ModelAdmin):
    list_display = (
        "carrier_name",
        "mobile_type",
        "internet_plan_name",
        "internet_plan_sum",
        "internet_plan_discount_list",
        "tv_plan_name",
        "tv_plan_sum",
        "tv_plan_discount_list",
        "total_sum",
    )
    readonly_fields = (
        "carrier_name",
        "mobile_type",
        "internet_plan_name",
        "internet_plan_sum",
        "internet_plan_discount_list",
        "tv_plan_name",
        "tv_plan_sum",
        "tv_plan_discount_list",
        "total_sum",
    )

    def mobile_type(self, obj):
        return obj.mobile_type if obj.mobile_type else "N/A"

    def carrier_name(self, obj):
        return obj.carrier.name

    def internet_plan_name(self, obj):
        return f"{obj.internet_plan.name} ({obj.internet_plan.speed})"

    def internet_plan_sum(self, obj):
        total_price = (
            obj.internet_plan.internet_price_per_month
            - obj.internet_plan.internet_contract_discount
        )
        internet_plan_discounts = [
            dc
            for dc in obj.bundle_discounts.all()
            if dc.discount_type == BundleDiscount.DISCOUNT_TYPES[1][0]
        ]
        if obj.internet_plan.is_wifi_router_free is False:
            total_price += obj.carrier.wifi_router_rental_price_per_month
        return total_price - sum(dc.discount_amount for dc in internet_plan_discounts)

    def internet_plan_discount_list(self, obj):
        tables = [f"정가: {obj.internet_plan.internet_price_per_month}원"]
        if obj.internet_plan.internet_contract_discount > 0:
            tables.append(
                f"약정할인: -{obj.internet_plan.internet_contract_discount}원"
            )
        if obj.internet_plan.is_wifi_router_free is False:
            tables.append(
                f"WiFi 임대료: {obj.carrier.wifi_router_rental_price_per_month}원"
            )
        tables += [
            f"{dc.bundle_name}: -{dc.discount_amount}원"
            for dc in obj.bundle_discounts.all()
            if dc.discount_type == BundleDiscount.DISCOUNT_TYPES[1][0]
        ]
        return ",\n ".join(tables)

    def tv_plan_name(self, obj):
        return f"{obj.tv_plan.name}"

    def tv_plan_sum(self, obj):
        total_price = obj.tv_plan.tv_price_per_month - obj.tv_plan.tv_contract_discount
        tv_plan_discounts = [
            dc
            for dc in obj.bundle_discounts.all()
            if dc.discount_type == BundleDiscount.DISCOUNT_TYPES[2][0]
        ]
        if obj.tv_plan.is_settop_box_free is False:
            total_price += obj.carrier.tv_settop_box_rental_price_per_month

        return total_price - sum(dc.discount_amount for dc in tv_plan_discounts)

    def tv_plan_discount_list(self, obj):
        tables = [f"정가: {obj.tv_plan.tv_price_per_month}원"]
        if obj.tv_plan.tv_contract_discount > 0:
            tables.append(f"약정할인: -{obj.tv_plan.tv_contract_discount}원")
        if obj.tv_plan.is_settop_box_free is False:
            tables.append(
                f"셋탑박스 임대료: {obj.carrier.tv_settop_box_rental_price_per_month}원"
            )
        tables += [
            f"{dc.bundle_name}: -{dc.discount_amount}원"
            for dc in obj.bundle_discounts.all()
            if dc.discount_type == BundleDiscount.DISCOUNT_TYPES[2][0]
        ]
        return ",\n ".join(tables)

    def total_sum(self, obj):
        return self.internet_plan_sum(obj) + self.tv_plan_sum(obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    # 3. 데이터 표시를 위한 메서드 (list_display에 사용)

    def get_queryset(self, request):
        return BundleCondition.objects.select_related(
            "carrier", "internet_plan", "tv_plan"
        ).prefetch_related("bundle_discounts", "bundle_promotions")
