import traceback
from io import BytesIO
import pandas as pd

from django.utils.html import format_html
from django.db.models import Prefetch
from django.contrib import admin, messages
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import format_html

import nested_admin
from simple_history.admin import SimpleHistoryAdmin

from .models import *


class commonAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at", "deleted_at")


@admin.register(ProductImages)
class ProductImagesAdmin(commonAdmin):
    pass


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
        return (
            queryset.select_related(
                "device_variant__device",  # device_variant와 device 함께 로드
                "plan",  # plan도 함께 로드
            )
            .prefetch_related(
                # 추가로 필요한 관계가 있다면 여기에 추가
            )
            .filter(deleted_at__isnull=True)
        )


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [ProductDetailImageInline, ProductOptionsInline]
    exclude = ("deleted_at",)
    change_list_template = "admin/product_changelist.html"
    change_form_template = "admin/product_nested_change_form.html"

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
        ]
        # 커스텀 URL을 기본 URL보다 먼저 배치
        return custom_urls + urls

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
                            device_price=dv_db_dict[f"{device_id}_{row['용량']}"][
                                "device_price"
                            ],
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
                                    device_price=dv_db_dict[
                                        f"{device_id}_{row['용량']}"
                                    ]["device_price"],
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

    queryset = Order.objects.filter(deleted_at__isnull=True)


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
    from mdeditor.widgets import MDEditorWidget

    formfield_overrides = {models.TextField: {"widget": MDEditorWidget}}


@admin.register(PlanPremiumChoices)
class PlanPremiumChoicesAdmin(commonAdmin):
    pass


@admin.register(ProductSeries)
class ProductSeriesAdmin(commonAdmin):
    pass
