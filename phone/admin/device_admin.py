# pyright: reportAttributeAccessIssue=false
import nested_admin
from django.contrib import admin
from django.utils.html import format_html

from phone.models import *
from .base import commonAdmin


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
    search_fields = ("device__model_name", "color")

    queryset = DeviceColor.objects.filter(deleted_at__isnull=True)


@admin.register(DeviceVariant)
class DeviceVariantsAdmin(commonAdmin):
    list_display = ("device", "storage_capacity", "device_price")
    search_fields = ("device__model_name", "storage_capacity")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(deleted_at__isnull=True)
            .select_related("device")
        )
