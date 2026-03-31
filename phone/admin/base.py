# pyright: reportAttributeAccessIssue=false
import traceback
from io import BytesIO
import pandas as pd

from collections import defaultdict
from datetime import timedelta
from django import forms
from django.utils.html import format_html
from django.db.models import Prefetch, F, Subquery, OuterRef
from django.contrib import admin, messages
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import format_html
from django.utils import timezone

BAIT_MARGIN = 10_000  # 미끼 상품 고정 마진


class UpdatePriceForm(forms.Form):
    db_margin = forms.IntegerField(
        label="DB 상품에 포함된 마진 (원)",
        initial=60_000,
        help_text="DB product_option의 final_price에 이미 포함된 마진 (예: 60000~80000)",
    )
    om_margin = forms.IntegerField(
        label="오픈마켓 추가 마진 (원)",
        initial=30_000,
        help_text="오픈마켓 옵션 가격에 추가할 마진 (예: 30000)",
    )


from phone.tasks import task_a_remove_options
from phone.external_services.st_11.put_product.set_options import SetOptions11ST
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

from phone.models import *
from phone.external_services.channel_talk import send_shipping_noti_to_customer


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
