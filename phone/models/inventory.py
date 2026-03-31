from django.db import models

from phone.constants import CarrierChoices, ContractTypeChoices
from phone.utils import UniqueFilePathGenerator

from .base import SoftDeleteModel
from .device import DeviceVariant, DeviceColor


class Dealership(SoftDeleteModel):
    """대리점 관리 테이블"""

    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=50, choices=CarrierChoices.CHOICES)
    contact_number = models.CharField(max_length=20)
    manager = models.CharField(max_length=100)
    credit_check_agree_format = models.TextField(null=True)
    opening_request_format = models.TextField(null=True)

    def __str__(self):
        return self.name


class OfficialContractLink(SoftDeleteModel):
    """공식신청서 관리 테이블 - (대리점, 단말기(용량), 신규/기변/번이) 별 관리"""

    dealer = models.ForeignKey(
        Dealership, on_delete=models.CASCADE, related_name="official_links"
    )
    device_variant = models.ForeignKey(
        DeviceVariant,
        on_delete=models.CASCADE,
        related_name="official_links",
    )
    contract_type = models.CharField(
        max_length=50,
        choices=ContractTypeChoices.CHOICES,
        default=ContractTypeChoices.CHANGE,
    )
    link = models.URLField(help_text="Official contract submission link")

    class Meta:
        unique_together = ("dealer", "device_variant", "contract_type")


class Inventory(SoftDeleteModel):
    """각 대리점에서 받는 재고표와 DB에 있는 device_varaint, device_color 정보를 매칭하기 위한 테이블"""

    device_variant = models.ForeignKey(
        DeviceVariant,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    name_in_sheet = models.CharField(
        max_length=100,
        help_text="재고표에 있는 모델명. 텍스트 안에 쉼표가 들어가서 여러 모델명이 있을 수 있음",
    )
    dealership = models.ForeignKey(
        Dealership,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    device_color = models.ForeignKey(
        DeviceColor,
        on_delete=models.CASCADE,
        related_name="inventories",
    )
    color_in_sheet = models.CharField(
        max_length=50,
        help_text="재고표에 있는 색상명. 텍스트 안에 쉼표가 들어가서 여러 색상명이 있을 수 있음",
    )
    count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name_in_sheet} ({self.color_in_sheet})"

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["device_variant", "device_color", "dealership"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["device_variant", "device_color", "dealership"],
                name="unique_inventory_item",
            )
        ]
