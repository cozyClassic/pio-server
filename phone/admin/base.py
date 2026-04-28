# pyright: reportAttributeAccessIssue=false
from django.contrib import admin


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
