from django.contrib import admin
import nested_admin
from django.utils.html import format_html

from .models import (
    Plan,
    Device,
    DeviceColor,
    DeviceVariant,
    Product,
    ProductOption,
    ProductDetailImage,
    DevicesColorImage,
)


class commonAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at", "deleted_at")


@admin.register(Plan)
class PlanAdmin(commonAdmin):
    list_display = ("name", "price", "data", "calling", "sms")
    search_fields = ("name",)


# 2. DevicesColorImages 모델을 위한 인라인 클래스
class DeviceImagesInline(nested_admin.NestedStackedInline):
    model = DevicesColorImage
    extra = 1
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

    # 메서드에 짧은 설명을 붙여 Admin 페이지에 표시될 이름으로 사용
    image_preview.short_description = "미리보기"


class ColorsInline(nested_admin.NestedStackedInline):
    model = DeviceColor
    extra = 1  # 기본으로 1개의 빈 폼을 더 보여줍니다.
    # SoftDeleteModel의 deleted_at 필드를 숨깁니다.
    exclude = ("deleted_at",)

    inlines = [DeviceImagesInline]


@admin.register(Device)
class DeviceAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "maker")
    search_fields = ("name", "maker")

    inlines = [ColorsInline]


@admin.register(DeviceColor)
class DeviceColorsAdmin(commonAdmin):
    list_display = ("device", "color", "color_code")
    search_fields = ("device__name", "color")


@admin.register(DeviceVariant)
class DeviceVariantsAdmin(commonAdmin):
    list_display = ("device", "capacity", "price")
    search_fields = ("device__name", "capacity")


class ProductOptionsInline(nested_admin.NestedTabularInline):
    model = ProductOption
    extra = 0
    exclude = ("deleted_at",)
    readonly_fields = ("final_price",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        # 폼셋이 생성될 때 부모(Product) 객체를 참조하여 필터링합니다.
        if obj and obj.device:
            device_instance = obj.device

            class CustomForm(formset.form):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.fields["device_variant"].queryset = (
                        DeviceVariant.objects.filter(device_id=device_instance.id)
                    )

            formset.form = CustomForm
        else:

            class CustomForm(formset.form):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.fields["device_variant"].queryset = (
                        DeviceVariant.objects.none()
                    )

            formset.form = CustomForm

        return formset


@admin.register(Product)
class ProductAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    inlines = [ProductOptionsInline]
    exclude = ("deleted_at",)


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
