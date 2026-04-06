# pyright: reportAttributeAccessIssue=false
from collections import defaultdict
from django.db.models import Prefetch
from django.contrib import admin, messages
from django.urls import path
from django.http import HttpResponseRedirect
from django.shortcuts import render

import nested_admin

from phone.constants import OpenMarketChoices, CarrierChoices
from phone.models import *
from phone.tasks import task_a_remove_options
from phone.inventory.kt_first.excel_kt_first import (
    read_inventory_excel as read_kt_first_inventory_excel,
    update_inventory as update_kt_first_inventory,
)
from phone.inventory.lg_hunet.image_lg_hunet import (
    extract_json_from_image as extract_json_from_image_lg_hunet,
    update_inventory as update_inventory_lg_hunet,
)
from .base import commonAdmin, format_price, UpdatePriceForm, BAIT_MARGIN


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


class CardBenefitInline(nested_admin.NestedStackedInline):
    model = CardBenefit
    extra = 1
    exclude = ("deleted_at",)


@admin.register(PartnerCard)
class PartnerCardAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    list_filter = ("created_at",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    inlines = [CardBenefitInline]

    queryset = PartnerCard.objects.filter(deleted_at__isnull=True).prefetch_related(
        Prefetch(
            "benefits",
            queryset=CardBenefit.objects.filter(deleted_at__isnull=True),
        )
    )


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


@admin.register(Inventory)
class InventoryAdmin(commonAdmin):
    list_display = ("dealership", "color_in_sheet", "name_in_sheet", "count")
    list_filter = ("dealership", InventoryDeviceFilter)
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
    actions = ["update_11st_prices"]
    change_list_template = "admin/open_market_product_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "update-naver-compare/",
                self.admin_site.admin_view(self.update_naver_compare),
                name="open_market_product_update_naver_compare",
            ),
        ]
        return custom_urls + urls

    def update_naver_compare(self, request):
        from phone.external_services.naver_compare.engine_page_generator import (
            NaverCompareEnginePageGenerator,
        )

        try:
            NaverCompareEnginePageGenerator().generate()
            self.message_user(
                request, "네이버 가격비교 EP가 성공적으로 업데이트되었습니다."
            )
        except Exception as e:
            self.message_user(
                request, f"업데이트 중 오류가 발생했습니다: {e}", messages.ERROR
            )
        return HttpResponseRedirect("../")

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

    @admin.action(description="11번가 가격 업데이트")
    def update_11st_prices(self, request, queryset):

        if "apply" not in request.POST:
            form = UpdatePriceForm()
            return render(
                request,
                "admin/update_11st_price_intermediate.html",
                {"form": form, "queryset": queryset},
            )

        form = UpdatePriceForm(request.POST)
        if not form.is_valid():
            self.message_user(request, "입력값이 올바르지 않습니다.", messages.ERROR)
            return

        db_margin = form.cleaned_data["db_margin"]
        om_margin = form.cleaned_data["om_margin"]

        om_products = list(
            queryset.filter(open_market__source=OpenMarketChoices.ST11).select_related(
                "open_market"
            )
        )

        if not om_products:
            self.message_user(
                request, "선택된 11번가 상품이 없습니다.", messages.WARNING
            )
            return

        # DB N+1 방지: 대상 device_variant의 ProductOption 전체를 1회 조회
        device_variant_ids = [
            p.device_variant_id for p in om_products if p.device_variant_id
        ]
        all_product_options = list(
            ProductOption.objects.filter(
                device_variant_id__in=device_variant_ids,
                discount_type="공시지원금",
            )
            .select_related("plan")
            .order_by("-plan__price")
        )

        po_by_dv = defaultdict(list)
        for po in all_product_options:
            po_by_dv[po.device_variant_id].append(po)

        queued = 0
        for om_product in om_products:
            seller_code = om_product.seller_code or ""
            carriers = [c for c in CarrierChoices.VALUES if c in seller_code]
            if not carriers:
                self.message_user(
                    request,
                    f"[{om_product.name}] 셀러코드에서 통신사를 찾을 수 없어 건너뜁니다.",
                    messages.WARNING,
                )
                continue

            carrier = carriers[0]
            contract_type = "번호이동" if "MNP" in seller_code else "기기변경"

            matching_pos = [
                po
                for po in po_by_dv.get(om_product.device_variant_id, [])
                if po.plan.carrier == carrier and po.contract_type == contract_type
            ]
            if not matching_pos:
                self.message_user(
                    request,
                    f"[{om_product.name}] 적합한 요금제 옵션이 없어 건너뜁니다.",
                    messages.WARNING,
                )
                continue

            bait_base = min([pos.final_price for pos in matching_pos]) - db_margin
            commission_rate = om_product.open_market.commision_rate_default
            target_price = int(
                round((bait_base + BAIT_MARGIN) / (1 - commission_rate), -3)
            )
            if target_price <= 1000:
                # 마이너스 가격 세팅 불가 - 최소 1000원으로 설정
                target_price = 1000

            task_a_remove_options.delay(
                om_product_id_internal=om_product.id,
                target_price=target_price,
                om_margin=om_margin,
            )
            queued += 1

        if queued:
            self.message_user(
                request,
                f"{queued}개 상품에 대한 11번가 가격 업데이트 Task가 Queue에 추가되었습니다.",
            )


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


@admin.register(DiagnosisInquiry)
class DiagnosisInquiryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "contact",
        "prev_carrier",
        "device_name",
        "total_saving",
        "created_at",
    ]
    list_filter = [
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
    "주문": [Order, Order.history.model],
    "콘텐츠 · 마케팅": [
        Review,
        FAQ,
        Notice,
        Banner,
        Event,
        PolicyDocument,
        PartnerCard,
        CustomImage,
    ],
    "재고": [Inventory],
    "오픈마켓": [OpenMarket, OpenMarketProduct, OpenMarketProductOption],
    "기타": [Dealership, OfficialContractLink],
    "진단": [DiagnosisLog, DiagnosisInquiry],
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
