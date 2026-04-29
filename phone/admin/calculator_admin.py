# pyright: reportAttributeAccessIssue=false
from django.contrib import admin

from phone.models import CalculatorSession, CustomerIdentity

from .base import commonAdmin


@admin.register(CalculatorSession)
class CalculatorSessionAdmin(commonAdmin):
    list_display = (
        "id",
        "funnel_variant",
        "contact_channel",
        "winner",
        "pio_total",
        "total_saving",
        "created_at",
    )
    list_filter = (
        "funnel_variant",
        "contact_channel",
        "winner",
        "created_at",
    )
    search_fields = (
        "id",
        "ga4_client_id",
        "submitted_name",
        "submitted_contact",
        "device_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "deleted_at")
    autocomplete_fields = ("internet_carriers", "device")
    fieldsets = (
        (
            "식별",
            {
                "fields": (
                    "id",
                    "ga4_client_id",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Variant",
            {
                "fields": (
                    "funnel_variant",
                    "copy_variant",
                    "pricing_path",
                    "contact_channel",
                    "copy_variant_v3",
                    "name_field_omitted",
                )
            },
        ),
        (
            "답변",
            {
                "fields": (
                    "carrier",
                    "keep_carrier",
                    "internet_carriers",
                    "device",
                    "device_name",
                    "family_bundle",
                    "gift",
                    "data_usage",
                    "plan_price_mvno",
                    "plan_price_mno",
                    "card",
                    "card_spend",
                    "card_history",
                    "internet_new",
                )
            },
        ),
        (
            "자동 선택값",
            {
                "fields": (
                    "device_price",
                    "public_subsidy",
                    "additional_discount",
                    "skt_plan_id",
                    "skt_plan_monthly_fee",
                    "static_card_recommended",
                    "static_card_monthly",
                    "static_card_total24",
                    "partner_card_slots",
                    "partner_card_monthly",
                    "partner_card_total24",
                    "final_card_total24",
                    "final_card_monthly",
                    "family_bundle_eligible",
                    "gift_eligible",
                    "internet_new_eligible",
                )
            },
        ),
        (
            "결과",
            {
                "fields": (
                    "pio_total",
                    "selfbuy_total",
                    "official_total",
                    "benefit_only",
                    "total_saving",
                    "official_vs_pio",
                    "winner",
                    "ranks",
                    "benefit_amounts_snapshot",
                )
            },
        ),
        (
            "PII",
            {"fields": ("submitted_name", "submitted_contact")},
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("internet_carriers")
            .select_related("device")
        )


@admin.register(CustomerIdentity)
class CustomerIdentityAdmin(commonAdmin):
    list_display = (
        "id",
        "session",
        "source",
        "pre_name",
        "pre_contact",
        "identified_at",
    )
    search_fields = (
        "session__id",
        "pre_name",
        "pre_contact",
        "oauth_user_id",
    )
    list_filter = ("source",)
    readonly_fields = ("created_at", "updated_at", "deleted_at", "identified_at")
    autocomplete_fields = ("session",)
