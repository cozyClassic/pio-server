import traceback
from io import BytesIO
import pandas as pd

from datetime import timedelta
from django.utils.html import format_html
from django.db.models import Prefetch, F, Subquery, OuterRef
from django.contrib import admin, messages
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import format_html
from django.utils import timezone
from phone.inventory.kt_first.excel_kt_first import (
    read_inventory_excel as read_kt_first_inventory_excel,
    update_inventory as update_kt_first_inventory,
)
from phone.inventory.lg_hunet.image_lg_hunet import (
    extract_json_from_image as extract_json_from_image_lg_hunet,
    update_inventory as update_inventory_lg_hunet,
)

import nested_admin
from simple_history.admin import SimpleHistoryAdmin

from .models import *
from .external_services.channel_talk import send_shipping_noti_to_customer


def format_price(num: int):
    if num is None:
        return "0"
    return f"{num:,}"


class commonAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at", "deleted_at")

    def delete_model(self, request, obj):
        obj.delete()  # 모델에 정의한 soft delete 호출

    # 2. 여러 객체 일괄 삭제 시 (목록 페이지 액션)
    def delete_queryset(self, request, queryset):
        queryset.delete()  # 쿼리셋에 정의한 soft delete 호출

    def get_action(self, action):
        return super().get_action(action)


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

    queryset = DeviceColor.objects.filter(deleted_at__isnull=True)


@admin.register(DeviceVariant)
class DeviceVariantsAdmin(commonAdmin):
    list_display = ("device", "storage_capacity", "device_price")
    search_fields = ("device__name", "storage_capacity")

    queryset = DeviceVariant.objects.filter(deleted_at__isnull=True)


class ProductDetailImageInline(nested_admin.NestedTabularInline):
    model = ProductDetailImage
    extra = 0
    exclude = ("deleted_at",)

    queryset = ProductDetailImage.objects.filter(deleted_at__isnull=True)


class ProductOptionFormset(nested_admin.formsets.NestedInlineFormSet):
    def save_existing_objects(self, initial_forms=None, commit=True):
        return []

    def is_valid(self):
        return True


class ProductOptionsInline(nested_admin.NestedTabularInline):
    model = ProductOption
    extra = 0
    formset = ProductOptionFormset
    exclude = ("deleted_at",)
    readonly_fields = (
        "device_storage",
        "final_price_display",
        "custom_plan_carrier",
        "custom_plan_name",
        "discount_type",
        "contract_type",
        "subsidy_amount_display",
        "subsidy_amount_mnp_display",
        "additional_discount_display",
        "monthly_payment_display",
    )

    # 필드 순서 지정 (커스텀 필드들 포함)
    fields = (
        "device_storage",
        "custom_plan_carrier",
        "discount_type",
        "contract_type",
        "custom_plan_name",
        "subsidy_amount_display",
        "subsidy_amount_mnp_display",
        "additional_discount_display",
        "final_price_display",
        "monthly_payment_display",
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
        return f"{obj.plan.name}({format_price(obj.plan.price)}원)"

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
        request.GET = request.GET.copy()
        carrier = request.GET.get("plan_carrier", None)
        discount_type = request.GET.get("discount_type", None)
        contract_type = request.GET.get("contract_type", None)
        capacity = request.GET.get("capacity", None)

        if carrier:
            queryset = queryset.filter(
                plan__carrier__iexact=carrier,
            )
        if discount_type:
            queryset = queryset.filter(
                discount_type__iexact=discount_type,
            )
        if contract_type:
            queryset = queryset.filter(
                contract_type__iexact=contract_type,
            )
        if capacity:
            queryset = queryset.filter(
                device_variant__storage_capacity__iexact=capacity,
            )
        return (
            queryset.select_related(
                "device_variant__device",  # device_variant와 device 함께 로드
                "plan",  # plan도 함께 로드
            )
            .prefetch_related(
                # 추가로 필요한 관계가 있다면 여기에 추가
            )
            .filter(deleted_at__isnull=True)
            .order_by(
                "plan__carrier",
                "discount_type",
                "contract_type",
                "plan__price",
            )
        )

    @admin.display(description="할부원금")
    def final_price_display(self, obj):
        return format_price(obj.final_price)

    @admin.display(description="월 청구금액")
    def monthly_payment_display(self, obj):
        return format_price(obj.monthly_payment)

    @admin.display(description="공시지원금")
    def subsidy_amount_display(self, obj):
        return format_price(obj.subsidy_amount)

    @admin.display(description="전환지원금")
    def subsidy_amount_mnp_display(self, obj):
        return format_price(obj.subsidy_amount_mnp)

    @admin.display(description="추가지원금")
    def additional_discount_display(self, obj):
        return format_price(obj.additional_discount)


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [ProductDetailImageInline, ProductOptionsInline]
    exclude = ("deleted_at",)
    change_list_template = "admin/product_changelist.html"
    change_form_template = "admin/product_nested_change_form.html"
    actions = ["revalidate_selected_products"]

    readonly_fields = ["best_price_option"]

    def get_readonly_fields(self, request, obj=None):
        # obj가 None이면 새로 생성하는 경우, obj가 있으면 수정하는 경우
        if obj:  # 수정하는 경우
            return self.readonly_fields + ["device"]
        return self.readonly_fields  # 생성하는 경우는 기본 설정 사용

    # admin의 URL 패턴 확장
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("download-excel/", self.download_excel, name="product_download_excel"),
            path(
                "<path:object_id>/change/download-excel/",
                self.download_excel,
                name="product_download_excel",
            ),
            path("upload-excel/", self.upload_excel_view, name="product_upload_excel"),
            path(
                "process-upload/",
                self.upload_excel,
                name="product_process_upload",
            ),
            path(
                "revalidate-all/",
                self.revalidate_all_products,
                name="product_revalidate_all",
            ),
            path(
                "<path:object_id>/change/revalidate/",
                self.revalidate_single_product,
                name="product_revalidate_single",
            ),
            path(
                "save-current-prices/",
                self.save_current_prices,
                name="product_save_current_prices",
            ),
        ]
        # 커스텀 URL을 기본 URL보다 먼저 배치
        return custom_urls + urls

    def revalidate_all_products(self, request):
        """모든 제품 캐시 revalidate"""
        from .revalidate import revalidate_products

        success = revalidate_products()
        if success:
            messages.success(request, "✅ 모든 제품 캐시가 성공적으로 갱신되었습니다.")
        else:
            messages.error(request, "❌ 캐시 갱신에 실패했습니다. 로그를 확인해주세요.")

        return HttpResponseRedirect("../")

    def revalidate_single_product(self, request, object_id):
        """단일 제품 캐시 revalidate"""
        from .revalidate import revalidate_products

        success = revalidate_products()
        if success:
            messages.success(
                request, f"✅ 제품 ID {object_id} 캐시가 성공적으로 갱신되었습니다."
            )
        else:
            messages.error(request, "❌ 캐시 갱신에 실패했습니다. 로그를 확인해주세요.")

        return HttpResponseRedirect("../")

    @admin.action(description="선택한 제품 캐시 갱신 (Revalidate)")
    def revalidate_selected_products(self, request, queryset):
        """선택된 제품들의 캐시 revalidate (Admin Action)"""
        from .revalidate import revalidate_products

        success = revalidate_products()
        if success:
            messages.success(
                request,
                f"✅ {queryset.count()}개 제품의 캐시가 성공적으로 갱신되었습니다.",
            )
        else:
            messages.error(request, "❌ 캐시 갱신에 실패했습니다. 로그를 확인해주세요.")

    def save_current_prices(self, request):
        """
        모든 활성 상품의 현재 최저가를 PriceHistory에 저장
        - (product, carrier) 조합별로 6개월 총액 기준 가장 저렴한 공시지원금 옵션의 final_price 저장
        - 이전 가격과 동일하면 저장하지 않음
        """
        from django.db.models import OuterRef, Subquery
        from collections import defaultdict

        today = timezone.now().date()
        created_count = 0
        skipped_count = 0

        # 1. 활성 상품 목록 조회 (1 쿼리)
        products = list(
            Product.objects.filter(deleted_at__isnull=True, is_active=True).only("id")
        )

        if not products:
            messages.info(request, "활성 상품이 없습니다.")
            return HttpResponseRedirect("../")

        product_ids = [p.id for p in products]

        # 2. 모든 공시지원금 옵션을 한 번에 조회 (1 쿼리)
        # 6개월 총액 계산하여 정렬 - (product_id, carrier)별로 최저가 선택
        all_options = list(
            ProductOption.objects.filter(
                product_id__in=product_ids,
                discount_type="공시지원금",
                deleted_at__isnull=True,
                plan__deleted_at__isnull=True,
            )
            .select_related("plan")
            .annotate(six_month_total=F("final_price") + F("plan__price") * 6)
            .order_by("six_month_total")
        )

        # (product_id, carrier) -> best_option 매핑 (six_month_total 기준 최저가)
        best_options_map = {}
        for opt in all_options:
            key = (opt.product_id, opt.plan.carrier)
            if key not in best_options_map:
                best_options_map[key] = opt

        best_option_dict = defaultdict(defaultdict[str])
        for opt in best_options_map.values():
            best_option_dict[opt.product_id][opt.plan.carrier] = {
                "id": opt.id,
                "dv_id": opt.device_variant_id,
                "plan_id": opt.plan_id,
                "plan_name": opt.plan.name,
                "final_price": opt.final_price,
            }

        all_option_dict = defaultdict(defaultdict[str])
        for opt in all_options:
            if (
                opt.plan.carrier in all_option_dict[opt.product_id]
                and all_option_dict[opt.product_id][opt.plan.carrier] is not None
            ):
                continue
            all_option_dict[opt.product_id][opt.plan.carrier] = {
                "id": opt.id,
                "dv_id": opt.device_variant_id,
                "plan_id": opt.plan_id,
                "plan_name": opt.plan.name,
                "final_price": opt.final_price,
            }

        # 3. 기존 PriceHistory 중 최신 레코드만 조회 (1 쿼리)
        carriers = [code for code, _ in CarrierChoices.CHOICES]

        # 최신 price_at을 가진 레코드의 id를 서브쿼리로 조회
        latest_history_subquery = (
            PriceHistory.objects.filter(
                product_id=OuterRef("product_id"),
                carrier=OuterRef("carrier"),
                plan_id=OuterRef("plan_id"),
            )
            .order_by("-price_at")
            .values("id")[:1]
        )

        existing_histories = list(
            PriceHistory.objects.filter(
                product_id__in=product_ids,
                carrier__in=carriers,
                id=Subquery(latest_history_subquery),
            ).values("id", "product_id", "carrier", "plan_id", "final_price")
        )

        # (product_id, carrier, plan_id) -> history 매핑
        history_map = {
            (h["product_id"], h["carrier"], h["plan_id"]): h for h in existing_histories
        }

        # 4. 새로 생성할 PriceHistory 수집
        to_create = []

        for (product_id, carrier), best_option in best_options_map.items():
            history_key = (product_id, carrier, best_option.plan_id)
            existing = history_map.get(history_key)

            if existing and existing["final_price"] == best_option.final_price:
                # 가격이 동일하면 스킵
                skipped_count += 1
            else:
                # 새 레코드 생성 (가격이 다르거나 기존 기록이 없는 경우)
                to_create.append(
                    PriceHistory(
                        product_id=product_id,
                        carrier=carrier,
                        final_price=best_option.final_price,
                        plan_id=best_option.plan_id,
                        price_at=today,
                    )
                )
                created_count += 1

        # 5. bulk_create로 한 번에 저장 (1 쿼리)
        if to_create:
            PriceHistory.objects.bulk_create(to_create)

        messages.success(
            request,
            f"✅ 가격 기록 저장 완료: {created_count}개 생성, {skipped_count}개 스킵",
        )

        return HttpResponseRedirect("../")

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

    # Excel 업로드 페이지
    def upload_excel_view(self, request):
        if request.method == "GET":
            return render(request, "admin/upload_excel.html")

    def download_excel(self, request, object_id=None):
        # 특정 쿼리 (예: 재고가 10개 이하인 상품들)

        queryset = ProductOption.objects.select_related(
            "device_variant", "plan"
        ).filter(
            deleted_at__isnull=True,
            device_variant__deleted_at__isnull=True,
            plan__deleted_at__isnull=True,
        )
        if object_id:
            queryset = queryset.filter(product_id=object_id)
        devices_dict = {
            device.id: device.model_name
            for device in list(Device.objects.filter(deleted_at__isnull=True).all())
        }

        data = []
        for op in queryset:
            data.append(
                {
                    "단말기명": devices_dict[op.device_variant.device_id],
                    "용량": op.device_variant.storage_capacity,
                    "단말기가격": op.device_variant.device_price,
                    "통신사": op.plan.carrier,
                    "할인": op.discount_type,
                    "약정": op.contract_type,
                    "요금제명": op.plan.name,
                    "월요금": op.plan.price,
                    "공시지원금": op.subsidy_amount,
                    "전환지원금": op.subsidy_amount_mnp,
                    "추가지원금": op.additional_discount,
                    "단말기할부원금": op.final_price,
                }
            )

        # 정렬 먼저
        data.sort(
            key=lambda op: (
                op["단말기명"],
                op["용량"],
                op["통신사"],
                op["할인"],
                op["약정"],
                -op["월요금"],
            )
        )

        df = pd.DataFrame(data)

        output = BytesIO()
        csv_data = df.to_csv(
            index=False, encoding="utf-8-sig"
        )  # utf-8-sig는 한글 깨짐 방지
        output.write(csv_data.encode("utf-8-sig"))
        output.seek(0)

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=products.csv"

        return response

    def upload_excel(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            excel_file = request.FILES["excel_file"]

            try:
                # Excel 파일 읽기
                df = pd.read_csv(excel_file, delimiter=",").fillna(0)

                # 필수 컬럼 확인
                required_columns = [
                    "단말기명",
                    "용량",
                    "통신사",
                    "할인",
                    "약정",
                    "요금제명",
                    "공시지원금",
                    "전환지원금",
                    "추가지원금",
                ]
                missing_columns = [
                    col for col in required_columns if col not in df.columns
                ]

                if missing_columns:
                    messages.error(
                        request, f'필수 컬럼이 없습니다: {", ".join(missing_columns)}'
                    )
                    return HttpResponseRedirect("../upload-excel/")

                # 단말기명 전체 가져와서 필터링하기
                device_names = df["단말기명"].unique()

                # 데이터 처리 전 db에서 미리 가져오기
                # 너무 많아지지 않게, 단말기명 기준으로 필터링하기
                devices_db = list(
                    Device.objects.filter(
                        model_name__in=device_names, deleted_at__isnull=True
                    ).values("id", "model_name")
                )

                # 단말기명 : 단말기 id
                device_db_dict = {d["model_name"]: d["id"] for d in devices_db}

                products = list(
                    Product.objects.filter(
                        device__id__in=[d["id"] for d in devices_db],
                        deleted_at__isnull=True,
                    )
                )

                product_ids = [p.id for p in products]
                device_product_dict = {p.device_id: p.id for p in products}

                product_options_db = list(
                    ProductOption.objects.filter(deleted_at__isnull=True)
                    .filter(product_id__in=product_ids)
                    .all()
                )

                device_variants_db = list(
                    DeviceVariant.objects.filter(deleted_at__isnull=True).values(
                        "id", "device_id", "storage_capacity", "device_price"
                    )
                )

                # 단말기id_용량: {단말기옵션 id, 상품id, 단말기 가격)
                dv_db_dict = {
                    f"{dv['device_id']}_{dv['storage_capacity']}": {
                        "dv_id": dv["id"],
                        "product_id": device_product_dict[dv["device_id"]],
                        "device_price": dv["device_price"],
                    }
                    for dv in device_variants_db
                    if dv["device_id"] in device_product_dict
                }

                plans_db = list(
                    Plan.objects.filter(deleted_at__isnull=True).values(
                        "id", "carrier", "name", "price"
                    )
                )

                # 통신사_요금제명: 요금제 id
                plan_db_dict = {
                    f"{plan['carrier']}_{plan['name']}": plan["id"] for plan in plans_db
                }

                # dvID_planId_할인_약정: {옵션id, 공시지원금, 전환지원금, 추가지원금}
                option_db_dict = {
                    f"{op.device_variant_id}_{op.plan_id}_{op.discount_type}_{op.contract_type}": {
                        "id": op.id,
                        "공시지원금": op.subsidy_amount,
                        "전환지원금": op.subsidy_amount_mnp,
                        "추가지원금": op.additional_discount,
                        "단말기가격": op.device_price,
                    }
                    for op in product_options_db
                }

                option_id_to_instance = {op.id: op for op in product_options_db}

                errors = []
                creates = []
                updates = []

                for index, row in df.iterrows():
                    device_id = device_db_dict.get(row["단말기명"])
                    plan_id = plan_db_dict.get(f"{row['통신사']}_{row['요금제명']}")
                    if f"{device_id}_{row['용량']}" not in dv_db_dict:
                        print(
                            f"단말기 {row['단말기명']}의 용량 {row['용량']}이(가) 존재하지 않습니다. (행 {index + 2})"
                        )
                        continue
                    if "dv_id" not in dv_db_dict.get(f"{device_id}_{row['용량']}"):
                        print(
                            f"단말기 {row['단말기명']}의 용량 {row['용량']}이(가) 존재하지 않습니다. (행 {index + 2})"
                        )
                        continue
                    dv_id = dv_db_dict.get(f"{device_id}_{row['용량']}")["dv_id"]

                    key = f"{dv_id}_{plan_id}_{row['할인']}_{row['약정']}"
                    if key in option_db_dict:
                        # update

                        # 만약 가격이 똑같으면 굳이 업데이트 하지 않음
                        if (
                            option_db_dict[key]["공시지원금"] == row["공시지원금"]
                            and option_db_dict[key]["전환지원금"] == row["전환지원금"]
                            and option_db_dict[key]["추가지원금"] == row["추가지원금"]
                        ):
                            continue
                        instance = option_id_to_instance[option_db_dict[key]["id"]]
                        instance.subsidy_amount = row["공시지원금"]
                        instance.subsidy_amount_mnp = row["전환지원금"]
                        instance.additional_discount = row["추가지원금"]
                        instance.final_price = ProductOption.calculate_final_price(
                            device_price=option_db_dict[key]["단말기가격"],
                            discount_type=row["할인"],
                            contract_type=row["약정"],
                            subsidy_amount=row["공시지원금"],
                            subsidy_amount_mnp=row["전환지원금"],
                            additional_discount=row["추가지원금"],
                        )

                        updates.append(instance)
                    else:
                        # create
                        creates.append(
                            ProductOption(
                                product_id=device_product_dict[
                                    device_db_dict[row["단말기명"]]
                                ],
                                device_variant_id=dv_id,
                                plan_id=plan_id,
                                discount_type=row["할인"],
                                contract_type=row["약정"],
                                subsidy_amount=row["공시지원금"],
                                subsidy_amount_mnp=row["전환지원금"],
                                additional_discount=row["추가지원금"],
                                final_price=ProductOption.calculate_final_price(
                                    device_price=option_db_dict[key]["단말기가격"],
                                    discount_type=row["할인"],
                                    contract_type=row["약정"],
                                    subsidy_amount=row["공시지원금"],
                                    subsidy_amount_mnp=row["전환지원금"],
                                    additional_discount=row["추가지원금"],
                                ),
                            )
                        )

                ProductOption.objects.bulk_update(
                    updates,
                    [
                        "subsidy_amount",
                        "subsidy_amount_mnp",
                        "additional_discount",
                        "final_price",
                    ],
                )

                ProductOption.objects.bulk_create([data for data in creates])

                products = Product.objects.filter(id__in=product_ids)
                for product in products:
                    product._update_product_best_option()

            except Exception as e:
                error_info = traceback.format_exc()
                messages.error(
                    request, f"파일 처리 중 오류 발생: {str(e)}\n{error_info}"
                )

            return HttpResponseRedirect("../../")

        return HttpResponseRedirect("../upload-excel/")

    def save_related(self, request, form, formsets, change):
        form.save_m2m()
        for formset in formsets:
            if formset.model == ProductOption:
                formset.new_objects = []
                formset.changed_objects = []
                formset.deleted_objects = []
            else:
                self.save_formset(request, form, formset, change=change)


@admin.register(ProductOption)
class ProductOptionsAdmin(commonAdmin):
    list_display = (
        "product",
        "device_variant__storage_capacity",
        "plan__carrier",
        "plan__name",
        "discount_type",
        "contract_type",
    )
    search_fields = ("product__name", "device_variant__device__name")
    list_filter = ("product", "device_variant")

    queryset = ProductOption.objects.filter(deleted_at__isnull=True).select_related(
        "plan", "device_variant"
    )
    change_list_template = "admin/productoption_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "upload_sk_jungchaek/",
                self.upload_sk_jungchaek_view,
                name="upload_sk_jungchaek",
            ),
            path(
                "process_upload_sk_jungchaek/",
                self.upload_sk_jungchaek,
                name="process_upload_sk_jungchaek",
            ),
            path(
                "upload_lg_jungchaek/",
                self.upload_lg_jungchaek_view,
                name="upload_lg_jungchaek",
            ),
            path(
                "process_upload_lg_jungchaek/",
                self.upload_lg_jungchaek,
                name="process_upload_lg_jungchaek",
            ),
            path(
                "upload_kt_jungchaek/",
                self.upload_kt_jungchaek_view,
                name="upload_kt_jungchaek",
            ),
            path(
                "process_upload_kt_jungchaek/",
                self.upload_kt_jungchaek,
                name="process_upload_kt_jungchaek",
            ),
        ]
        return custom_urls + urls

    def upload_sk_jungchaek_view(self, request):
        if request.method == "GET":
            return render(request, "admin/upload_excel_sk_jungchaek_html.html")

    def upload_lg_jungchaek_view(self, request):
        if request.method == "GET":
            return render(request, "admin/upload_excel_lg_jungchaek_html.html")

    def upload_kt_jungchaek_view(self, request):
        if request.method == "GET":
            return render(request, "admin/upload_excel_kt_jungchaek_html.html")

    def upload_kt_jungchaek(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            from .product_option_update.excel_kt_first import (
                update_product_option_kt_subsidy_addtional,
            )

            excel_file = request.FILES["excel_file"].read()
            margin = int(request.POST.get("margin", 0))

            try:
                result = update_product_option_kt_subsidy_addtional(excel_file, margin)
                messages.info(request, result)
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return HttpResponseRedirect("../")

        return HttpResponseRedirect("../")

    def upload_sk_jungchaek(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            from .product_option_update.excel_sk_smartel import (
                update_product_option_SK_subsidy_addtional,
            )

            excel_file = request.FILES["excel_file"].read()
            margin = int(request.POST.get("margin", 0))

            try:
                result = update_product_option_SK_subsidy_addtional(excel_file, margin)
                messages.info(request, result)
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return HttpResponseRedirect("../")

        return HttpResponseRedirect("../")

    def upload_lg_jungchaek(self, request):
        if request.method == "POST" and request.FILES.get("excel_file"):
            from .product_option_update.excel_lg_hutel import (
                update_product_option_LG_subsidy_addtional,
            )

            excel_file = request.FILES["excel_file"].read()
            margin = int(request.POST.get("margin", 0))

            try:
                result = update_product_option_LG_subsidy_addtional(excel_file, margin)
                messages.info(request, result)
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return HttpResponseRedirect("../")

        return HttpResponseRedirect("../")


@admin.register(ProductDetailImage)
class ProductDetailImagesAdmin(commonAdmin):
    list_display = ("product", "image", "description")
    search_fields = ("product__name", "description")
    list_filter = ("product",)

    queryset = ProductDetailImage.objects.filter(deleted_at__isnull=True)


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


class ProductTagInline(nested_admin.NestedStackedInline):
    model = DecoratorTag.product.through
    extra = 1  # 기본으로 1개의 빈 폼을 더 보여줍니다.
    # SoftDeleteModel의 deleted_at 필드를 숨깁니다.


@admin.register(DecoratorTag)
class DecoratorTagAdmin(nested_admin.NestedModelAdmin):
    inlines = [ProductTagInline]

    fields = (
        "name",
        "text_color",
        "tag_color",
    )


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


@admin.register(Inventory)
class InventoryAdmin(commonAdmin):
    change_list_template = "admin/inventory_changelist.html"

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
