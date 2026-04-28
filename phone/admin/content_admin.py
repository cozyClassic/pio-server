# pyright: reportAttributeAccessIssue=false
from django.db.models import Prefetch
from django.contrib import admin, messages
from django.urls import path
from django.http import HttpResponseRedirect
from django.shortcuts import render

import nested_admin

from django import forms

from phone.constants import CardSlotChoices, CarrierChoices
from phone.models import *
from phone.inventory.kt_first.excel_kt_first import (
    read_inventory_excel as read_kt_first_inventory_excel,
    update_inventory as update_kt_first_inventory,
)
from phone.inventory.lg_hunet.image_lg_hunet import (
    extract_json_from_image as extract_json_from_image_lg_hunet,
    update_inventory as update_inventory_lg_hunet,
)
from .base import commonAdmin, format_price


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


@admin.register(Review)
class ReviewAdmin(nested_admin.NestedModelAdmin):
    list_display = ("customer_name", "created_at")
    search_fields = ("created_at",)
    exclude = ("deleted_at",)

    queryset = Review.objects.filter(deleted_at__isnull=True)


@admin.register(FAQ)
class FAQAdmin(commonAdmin):
    list_display = ("question", "answer", "created_at")
    search_fields = ("question", "answer")
    list_filter = ("created_at",)

    queryset = FAQ.objects.filter(deleted_at__isnull=True)


@admin.register(Notice)
class NoticeAdmin(commonAdmin):
    list_display = ("title", "created_at")
    search_fields = ("title", "content")
    list_filter = ("created_at",)
    queryset = Notice.objects.filter(deleted_at__isnull=True)


@admin.register(Banner)
class BannerAdmin(commonAdmin):
    list_display = ("title", "image", "created_at")
    search_fields = ("title",)
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    queryset = Banner.objects.filter(deleted_at__isnull=True)


@admin.register(PolicyDocument)
class PolicyDocumentAdmin(commonAdmin):
    list_display = ("document_type", "effective_date", "created_at")
    search_fields = ("document_type",)
    list_filter = ("effective_date", "created_at")
    readonly_fields = ("created_at", "updated_at", "deleted_at")

    queryset = PolicyDocument.objects.filter(deleted_at__isnull=True)


class PartnerCardAdminForm(forms.ModelForm):
    carriers = forms.MultipleChoiceField(
        choices=CarrierChoices.CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    discount_types = forms.MultipleChoiceField(
        choices=CardSlotChoices.CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = PartnerCard
        fields = "__all__"


class CardBenefitInlineForm(forms.ModelForm):
    threshold_amount_manwon = forms.IntegerField(
        label="전월실적(만원)",
        min_value=0,
        help_text="만원 단위로 입력하세요. 0 입력 시 실적 무관.",
    )

    class Meta:
        model = CardBenefit
        exclude = ("threshold_amount",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if (
            self.instance
            and self.instance.pk
            and self.instance.threshold_amount is not None
        ):
            self.fields["threshold_amount_manwon"].initial = (
                self.instance.threshold_amount // 10000
            )

    def clean(self):
        cleaned = super().clean()
        manwon = cleaned.get("threshold_amount_manwon")
        if manwon is not None:
            cleaned["threshold_amount"] = manwon * 10000
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.threshold_amount = self.cleaned_data["threshold_amount_manwon"] * 10000
        if commit:
            instance.save()
        return instance


class CardBenefitInline(nested_admin.NestedStackedInline):
    model = CardBenefit
    form = CardBenefitInlineForm
    fields = ("kind", "threshold_amount_manwon", "amount")
    extra = 1
    exclude = ("deleted_at",)


class CardAdditionalPromotionInline(nested_admin.NestedStackedInline):
    model = CardAdditionalPromotion
    extra = 0
    exclude = ("deleted_at",)
    filter_horizontal = ("target_series",)


@admin.register(CardIssuer)
class CardIssuerAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "is_active")
    search_fields = ("name",)
    ordering = ("sort_order", "name")


@admin.register(PartnerCard)
class PartnerCardAdmin(admin.ModelAdmin):
    form = PartnerCardAdminForm
    list_display = (
        "name",
        "issuer",
        "carriers_display",
        "discount_types_display",
        "is_active",
    )
    search_fields = ("name",)
    list_filter = ("is_active", "created_at")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    autocomplete_fields = ("issuer",)
    inlines = [CardBenefitInline, CardAdditionalPromotionInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(deleted_at__isnull=True)
            .select_related("issuer")
            .prefetch_related(
                Prefetch(
                    "card_benefits",
                    queryset=CardBenefit.objects.order_by("kind", "threshold_amount"),
                )
            )
        )

    @admin.display(description="통신사")
    def carriers_display(self, obj):
        return ", ".join(obj.carriers) if obj.carriers else "-"

    @admin.display(description="할인유형")
    def discount_types_display(self, obj):
        return ", ".join(obj.discount_types) if obj.discount_types else "-"


@admin.register(CustomImage)
class CustomImageAdmin(commonAdmin):
    pass


@admin.register(Event)
class EventAdmin(commonAdmin):

    class Meta:
        from tinymce.widgets import TinyMCE

        model = Event
        widgets = {
            "description": TinyMCE(),
        }


@admin.register(PlanPremiumChoices)
class PlanPremiumChoicesAdmin(commonAdmin):
    pass


@admin.register(ProductSeries)
class ProductSeriesAdmin(commonAdmin):
    pass


@admin.register(PriceHistory)
class PriceHistoryAdmin(commonAdmin):
    list_display = ("product", "carrier", "final_price_display", "plan", "price_at")
    list_filter = ("carrier", "price_at", "product")
    search_fields = ("product__name",)
    ordering = ("-price_at", "product", "carrier")

    @admin.display(description="최종가격")
    def final_price_display(self, obj):
        return format_price(obj.final_price)


@admin.register(Dealership)
class DealershipAdmin(commonAdmin):
    pass


@admin.register(OfficialContractLink)
class OfficialContractLinkAdmin(commonAdmin):
    pass


class InventoryDeviceFilter(admin.SimpleListFilter):
    title = "단말기"
    parameter_name = "device_id"

    def lookups(self, request, model_admin):
        devices = (
            Device.objects.filter(deleted_at__isnull=True)
            .values_list("id", "model_name")
            .order_by("model_name")
        )
        return list(devices)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(device_variant__device_id=self.value())
        return queryset


class InventoryCountFilter(admin.SimpleListFilter):
    title = "재고 수량"
    parameter_name = "count_filter"

    def lookups(self, request, model_admin):
        return [("gt0", "count 0 초과")]

    def queryset(self, request, queryset):
        if self.value() == "gt0":
            return queryset.filter(count__gt=0)
        return queryset


@admin.register(Inventory)
class InventoryAdmin(commonAdmin):
    list_display = ("dealership", "color_in_sheet", "name_in_sheet", "count")
    list_filter = ("dealership", InventoryDeviceFilter, InventoryCountFilter)
    change_list_template = "admin/inventory_changelist.html"
    search_fields = ("device_variant__device__model_name",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("dealership", "device_variant__device")
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sync-smartel/",
                self.admin_site.admin_view(self.sync_smartel_inventory_view),
                name="sync_smartel_inventory",
            ),
            path(
                "sync-kt-first/",
                self.admin_site.admin_view(self.sync_kt_first_inventory_view),
                name="sync_kt_first_inventory",
            ),
            path(
                "sync-lg-hunet/",
                self.admin_site.admin_view(self.sync_lg_hunet_inventory_view),
                name="sync_lg_hunet_inventory",
            ),
        ]
        return custom_urls + urls

    def sync_smartel_inventory_view(self, request):
        from phone.inventory.api_smartel import sync_smartel_inventory

        try:
            missed_items, updated_count = sync_smartel_inventory()
            messages.success(
                request,
                f"스마텔 재고 동기화가 완료되었습니다. 업데이트된 항목 수: {updated_count}개",
            )
            if missed_items:
                messages.warning(
                    request,
                    f"매칭되지 않은 항목: {len(missed_items)}개\n"
                    + "\n".join(str(item) for item in missed_items),
                )
        except Exception as e:
            messages.error(request, f"동기화 중 오류가 발생했습니다: {str(e)}")

        return HttpResponseRedirect("../")

    def sync_kt_first_inventory_view(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            import tempfile
            import os

            excel_file = request.FILES["excel_file"]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                for chunk in excel_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                inventory_data = read_kt_first_inventory_excel(tmp_path)
                not_matched = update_kt_first_inventory(inventory_data)

                if not_matched:
                    messages.warning(
                        request,
                        f"KT 퍼스트 재고 동기화 완료. 매칭되지 않은 항목: {len(not_matched)}개\n"
                        + "\n".join(not_matched),
                    )
                else:
                    messages.success(request, "KT 퍼스트 재고 동기화가 완료되었습니다.")
            except Exception as e:
                messages.error(request, f"동기화 중 오류가 발생했습니다: {str(e)}")
            finally:
                os.unlink(tmp_path)

            return HttpResponseRedirect("../")

        return render(
            request,
            "admin/inventory_kt_first_upload.html",
            {
                "title": "KT 퍼스트 재고 엑셀 업로드",
                "opts": self.model._meta,
            },
        )

    def sync_lg_hunet_inventory_view(self, request):
        if request.method == "POST" and request.FILES.get("image_file"):
            import tempfile
            import os

            image_file = request.FILES["image_file"]

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                for chunk in image_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                inventory_data = extract_json_from_image_lg_hunet(tmp_path)
                not_matched = update_inventory_lg_hunet(inventory_data)

                if not_matched:
                    messages.warning(
                        request,
                        f"LG 엘비휴넷 재고 동기화 완료. 매칭되지 않은 항목: {len(not_matched)}개\n"
                        + "\n".join(not_matched),
                    )
                else:
                    messages.success(
                        request, "LG 엘비휴넷 재고 동기화가 완료되었습니다."
                    )
            except Exception as e:
                messages.error(request, f"동기화 중 오류가 발생했습니다: {str(e)}")
            finally:
                os.unlink(tmp_path)

            return HttpResponseRedirect("../")

        return render(
            request,
            "admin/inventory_lg_hunet_upload.html",
            {
                "title": "LG 엘비휴넷 재고 이미지 업로드",
                "opts": self.model._meta,
            },
        )


@admin.register(OpenMarket)
class OpenMarketAdmin(commonAdmin):
    pass


class OpenMarketCarrierFilter(admin.SimpleListFilter):
    title = "통신사"
    parameter_name = "carrier"

    def lookups(self, request, model_admin):
        return [
            ("SK", "SK"),
            ("KT", "KT"),
            ("LG", "LG"),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__contains=self.value())
        return queryset


@admin.register(OpenMarketProduct)
class OpenMarketProductAdmin(commonAdmin):

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "open_market",
                "device_variant",
                "device_variant__device",
            )
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "device_variant":
            kwargs["queryset"] = DeviceVariant.objects.select_related("device")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    list_filter = ["open_market", OpenMarketCarrierFilter]
    autocomplete_fields = ["device_variant"]

    list_display = ["id", "open_market", "name"]


@admin.register(OpenMarketProductOption)
class OpenMarketProductOptionAdmin(commonAdmin):
    pass


@admin.register(DiagnosisLog)
class DiagnosisLogAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "prev_carrier",
        "device_name",
        "data_usage",
        "total_saving",
        "created_at",
    ]
    list_filter = [
        "internet",
        "family_bundle",
        "gift",
        "card",
        "internet_new",
    ]
    readonly_fields = ["created_at"]


_ADMIN_GROUPS = {
    "단말기 · 요금제": [Plan, PlanPremiumChoices, Device, DeviceColor, DeviceVariant],
    "상품": [
        Product,
        ProductOption,
        ProductDetailImage,
        ProductSeries,
        DecoratorTag,
        PriceHistory,
    ],
    "주문": [Order, Order.history.model, DiagnosisInquiry],
    "콘텐츠 · 마케팅": [
        Review,
        FAQ,
        Notice,
        Banner,
        Event,
        PolicyDocument,
        CardIssuer,
        PartnerCard,
        CardAdditionalPromotion,
        CustomImage,
    ],
    "재고": [Inventory],
    "오픈마켓": [OpenMarket, OpenMarketProduct, OpenMarketProductOption],
    "기타": [Dealership, OfficialContractLink],
    "진단": [DiagnosisLog],
}

_original_get_app_list = admin.AdminSite.get_app_list


def _grouped_get_app_list(self, request, app_label=None):
    app_list = _original_get_app_list(self, request, app_label)

    phone_models = {}
    other_apps = []

    for app in app_list:
        if app["app_label"] == "phone":
            for model in app["models"]:
                phone_models[model["object_name"]] = model
        else:
            other_apps.append(app)

    grouped_apps = []
    for group_name, model_classes in _ADMIN_GROUPS.items():
        models = [
            phone_models[m.__name__]
            for m in model_classes
            if m.__name__ in phone_models
        ]
        if models:
            grouped_apps.append(
                {
                    "name": group_name,
                    "app_label": f"phone__{group_name}",
                    "app_url": "/admin/phone/",
                    "has_module_perms": True,
                    "models": models,
                }
            )

    return grouped_apps + other_apps


admin.AdminSite.get_app_list = _grouped_get_app_list
