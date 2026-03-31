from typing import TYPE_CHECKING

from django.db import models
from django.db.models import QuerySet
from phoneinone_server.settings import DEBUG

from phone.utils import UniqueFilePathGenerator

from .base import SoftDeleteModel, SoftDeleteImageModel


class Device(SoftDeleteModel):
    model_name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    series = models.CharField(
        max_length=100,
        help_text="e.g., 갤럭시 S, 아이폰, 갤럭시 Z",
        blank=True,
        default="",
    )

    def __str__(self):
        return f"{self.model_name}"


class DeviceColor(SoftDeleteModel):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="colors")
    color = models.CharField(max_length=50)
    color_code = models.CharField(
        max_length=7, help_text="Hex color code, e.g., #FFFFFF"
    )
    sort_order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.color}"


class DevicesColorImage(SoftDeleteImageModel):
    device_color = models.ForeignKey(
        DeviceColor, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to=UniqueFilePathGenerator("device_color_images/"))
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return (
            f"image - {self.device_color.device.model_name}  {self.device_color.color}"
        )


class DeviceVariant(SoftDeleteModel):
    if TYPE_CHECKING:
        from .product import ProductOption

        product_options: QuerySet[ProductOption]

    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="variants"
    )
    storage_capacity = models.CharField(max_length=100)
    device_price = models.IntegerField(default=0, help_text="Price in KRW")
    name_sk = models.CharField(
        max_length=100, help_text="SK 모델명", blank=True, default="", null=True
    )
    price_sk = models.IntegerField(
        help_text="SK 모델 가격", blank=True, default=0, null=True
    )
    name_kt = models.CharField(
        max_length=100, help_text="KT 모델명", blank=True, default="", null=True
    )
    price_kt = models.IntegerField(
        help_text="KT 모델 가격", blank=True, default=0, null=True
    )
    name_lg = models.CharField(
        max_length=100, help_text="LG 모델명", blank=True, default="", null=True
    )
    price_lg = models.IntegerField(
        help_text="LG 모델 가격", blank=True, default=0, null=True
    )

    def __str__(self):
        if DEBUG:
            return f"{self.device.model_name} ({self.storage_capacity})"
        return super().__str__()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .product import ProductOption

        product_options: QuerySet[ProductOption] = self.product_options.filter(
            device_variant_id=self.id
        )

        for option in product_options:
            option.final_price = option._get_final_price()
            option.save()
