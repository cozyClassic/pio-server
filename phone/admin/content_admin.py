# pyright: reportAttributeAccessIssue=false
import logging
from collections import OrderedDict

from django.db.models import Prefetch, Sum
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

logger = logging.getLogger(__name__)


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


def _trigger_11st_display_sync():
    """재고 동기화 커밋 후 11번가 전시상태 동기화 Celery 태스크를 큐잉한다.

    admin 요청 트랜잭션이 커밋된 뒤에 실행되도록 transaction.on_commit을 사용해,
    Celery 워커가 최신 재고를 읽도록 보장한다. 큐잉 실패는 재고 동기화 자체를
    막지 않도록 격리한다.
    """
    from django.db import transaction
    from phone.tasks import task_sync_11st_display_status

    def _enqueue():
        try:
            task_sync_11st_display_status.delay()
        except Exception:
            logger.exception("[11st display sync] 태스크 큐잉 실패")

    transaction.on_commit(_enqueue)


def _trigger_ssg_sales_sync():
    """재고 동기화 커밋 후 SSG 판매상태 동기화 Celery 태스크를 큐잉한다.

    판매재개는 하지 않고(재고 소진 → 판매중지 방향만) 동기화한다. 11번가 트리거와
    동일하게 on_commit 후 비동기 실행하며, 큐잉 실패는 격리한다.
    """
    from django.db import transaction
    from phone.tasks import task_sync_ssg_sales_status

    def _enqueue():
        try:
            task_sync_ssg_sales_status.delay()
        except Exception:
            logger.exception("[ssg sales sync] 태스크 큐잉 실패")

    transaction.on_commit(_enqueue)


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
            _trigger_11st_display_sync()
            _trigger_ssg_sales_sync()
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
                _trigger_11st_display_sync()
                _trigger_ssg_sales_sync()

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
                _trigger_11st_display_sync()
                _trigger_ssg_sales_sync()

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


@admin.register(InventorySummary)
class InventorySummaryAdmin(commonAdmin):
    """제품별(단말기/용량) 합계 재고를 대리점별 피벗 표로 보여주는 읽기전용 리포트."""

    change_list_template = "admin/inventory_summary.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        group_by = request.GET.get("group_by", "variant")
        if group_by not in ("variant", "device"):
            group_by = "variant"
        # 기본은 재고(합계>0)만 노출, ?all=1 이면 전체 노출
        in_stock_only = request.GET.get("all") != "1"

        base = Inventory.objects.filter(
            device_variant__deleted_at__isnull=True,
            device_variant__device__deleted_at__isnull=True,
            dealership__deleted_at__isnull=True,
        )

        # 대리점 컬럼 목록 (이름순)
        dealer_rows = (
            base.values("dealership_id", "dealership__name")
            .distinct()
            .order_by("dealership__name")
        )
        dealerships = [
            {"id": d["dealership_id"], "name": d["dealership__name"]}
            for d in dealer_rows
        ]
        dealer_ids = [d["id"] for d in dealerships]

        # (단말기, 용량, 대리점) 별 합계 집계
        agg_rows = (
            base.values(
                "device_variant_id",
                "device_variant__storage_capacity",
                "device_variant__device_id",
                "device_variant__device__model_name",
                "device_variant__device__brand",
                "dealership_id",
            )
            .annotate(total=Sum("count"))
            .order_by(
                "device_variant__device__model_name",
                "device_variant__storage_capacity",
                "device_variant_id",
            )
        )

        devices = OrderedDict()
        for r in agg_rows:
            did = r["device_variant__device_id"]
            dev = devices.get(did)
            if dev is None:
                dev = {
                    "id": did,
                    "model_name": r["device_variant__device__model_name"],
                    "brand": r["device_variant__device__brand"],
                    "variants": OrderedDict(),
                }
                devices[did] = dev
            vid = r["device_variant_id"]
            variant = dev["variants"].get(vid)
            if variant is None:
                variant = {
                    "id": vid,
                    "storage": r["device_variant__storage_capacity"],
                    "cells": {d: 0 for d in dealer_ids},
                    "total": 0,
                }
                dev["variants"][vid] = variant
            variant["cells"][r["dealership_id"]] = r["total"]
            variant["total"] += r["total"]

        groups = []
        col_totals = {d: 0 for d in dealer_ids}
        grand_total = 0
        for dev in devices.values():
            variant_rows = []
            subtotal = {d: 0 for d in dealer_ids}
            dev_total = 0
            for variant in dev["variants"].values():
                if in_stock_only and variant["total"] == 0:
                    continue
                variant_rows.append(
                    {
                        "id": variant["id"],
                        "storage": variant["storage"],
                        "cells": [variant["cells"][d] for d in dealer_ids],
                        "total": variant["total"],
                    }
                )
                for d in dealer_ids:
                    subtotal[d] += variant["cells"][d]
                dev_total += variant["total"]

            if in_stock_only and dev_total == 0:
                continue

            groups.append(
                {
                    "device_id": dev["id"],
                    "model_name": dev["model_name"],
                    "brand": dev["brand"],
                    "variant_count": len(variant_rows),
                    "variant_rows": variant_rows,
                    "subtotal_cells": [subtotal[d] for d in dealer_ids],
                    "subtotal_total": dev_total,
                }
            )
            for d in dealer_ids:
                col_totals[d] += subtotal[d]
            grand_total += dev_total

        context = {
            **self.admin_site.each_context(request),
            "title": "제품별 재고",
            "opts": self.model._meta,
            "dealerships": dealerships,
            "col_count": len(dealerships),
            "groups": groups,
            "col_totals": [col_totals[d] for d in dealer_ids],
            "grand_total": grand_total,
            "group_by": group_by,
            "in_stock_only": in_stock_only,
        }
        if extra_context:
            context.update(extra_context)
        return render(request, self.change_list_template, context)


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

    list_filter = ["open_market", OpenMarketCarrierFilter, "is_display_stopped"]
    autocomplete_fields = ["device_variant"]

    list_display = ["id", "open_market", "name", "is_display_stopped"]


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


# 사이드바 그룹화는 `phone/admin/grouping.py` 로 이동됨 (모든 admin 등록 후 import).
