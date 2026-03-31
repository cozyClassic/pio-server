from django.db import models

from phone.constants import CarrierChoices
from phone.utils import UniqueFilePathGenerator

from .base import SoftDeleteModel, SoftDeleteImageModel


class PlanPremiumChoices(SoftDeleteImageModel):
    carrier = models.CharField(max_length=10, choices=CarrierChoices.CHOICES)
    name = models.CharField(max_length=100, help_text="넷플릭스, 유튜브 등")
    description = models.TextField()


class Plan(SoftDeleteModel):
    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=100, choices=CarrierChoices.CHOICES)
    category_1 = models.CharField(max_length=100, help_text="e.g., 5G, LTE, 3G")
    category_2 = models.CharField(
        max_length=100, help_text="통신사 별 요금제 구분 (5GX, 0청년 등)"
    )
    description = models.CharField(
        max_length=255,
        help_text="Brief description of the plan",
        null=True,
        blank=True,
        default="",
    )
    price = models.IntegerField(default=0, help_text="Price in KRW")
    data_allowance = models.CharField(max_length=100, help_text="Data limit in MB")
    call_allowance = models.CharField(max_length=100, help_text="Call minutes limit")
    sms_allowance = models.CharField(max_length=100, help_text="sms_allowance limit")
    sort_order = models.IntegerField(default=0)
    membership_level = models.CharField(max_length=100, default="")
    short_name = models.CharField(max_length=100, default="", null=True, blank=True)

    def __str__(self):
        return f"{self.carrier} / {self.name} - {self.price}"
