from django.db import models

from .base import SoftDeleteModel


class DiagnosisLog(SoftDeleteModel):
    """요금제 진단 로그 - 사용자 진단 결과 익명 기록"""

    prev_carrier = models.CharField(max_length=50)
    keep_carrier = models.BooleanField(default=False)
    device_name = models.CharField(max_length=100)
    data_usage = models.CharField(max_length=50)
    internet = models.CharField(max_length=50)
    family_bundle = models.BooleanField(default=False)
    gift = models.BooleanField(default=False)
    card = models.BooleanField(default=False)
    internet_new = models.BooleanField(default=False)
    selfbuy_total = models.IntegerField(default=0)
    pio_total = models.IntegerField(default=0)
    total_saving = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    ga4_id = models.CharField(
        max_length=255, blank=True, help_text="GA4 ID", default=""
    )

    def __str__(self):
        return f"{self.prev_carrier} {self.device_name}"


class DiagnosisInquiry(SoftDeleteModel):
    """요금제 진단 상담 신청 - 이름/연락처 포함"""

    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=20)
    prev_carrier = models.CharField(max_length=50)
    keep_carrier = models.BooleanField(default=False)
    device_name = models.CharField(max_length=100)
    data_usage = models.CharField(max_length=50)
    internet = models.CharField(max_length=50)
    family_bundle = models.BooleanField(default=False)
    gift = models.BooleanField(default=False)
    card = models.BooleanField(default=False)
    internet_new = models.BooleanField(default=False)
    selfbuy_total = models.IntegerField(default=0)
    pio_total = models.IntegerField(default=0)
    total_saving = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.contact})"
