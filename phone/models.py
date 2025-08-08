from django.db import models
from django.utils import timezone

# Create your models here.


class SoftDeleteModel(models.Model):
    """
    Abstract model to add soft delete functionality.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def delete(self, *args, **kwargs):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


class Plan(SoftDeleteModel):
    name = models.CharField(max_length=100)
    carrier = models.CharField(max_length=100)
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
    price = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.CharField(max_length=100, help_text="Data limit in MB")
    calling = models.CharField(max_length=100, help_text="Call minutes limit")
    sms = models.CharField(max_length=100, help_text="SMS limit")

    def __str__(self):
        return f"{self.name} - {self.price}"


class Device(SoftDeleteModel):
    name = models.CharField(max_length=100)
    maker = models.CharField(max_length=100)
    series = models.CharField(
        max_length=100,
        help_text="e.g., 갤럭시 S, 아이폰, 갤럭시 Z",
        blank=True,
        default="",
    )

    def __str__(self):
        return f"{self.name} by {self.maker}"


class DeviceColors(SoftDeleteModel):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="colors")
    color = models.CharField(max_length=50)
    color_code = models.CharField(
        max_length=7, help_text="Hex color code, e.g., #FFFFFF"
    )

    def __str__(self):
        return f"{self.color} for {self.device.name}"


class DevicesColorImages(SoftDeleteModel):
    device_color = models.ForeignKey(
        DeviceColors, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="device_color_images/")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"image for {self.device_color.device.name} - {self.device_color.color}"


class DeviceVariants(SoftDeleteModel):
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="variants"
    )
    capacity = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.device.name} - {self.capacity}"


class ProductOptions(SoftDeleteModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="options"
    )
    device_variant = models.ForeignKey(
        DeviceVariants,
        on_delete=models.CASCADE,
        related_name="product_options",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="product_options",
    )
    discount_type = models.CharField(
        max_length=50,
        choices=[
            ("공시지원금", "공시지원금"),
            ("선택약정", "선택약정"),
        ],
        default=("공시지원금", "공시지원금"),
    )
    contract_type = models.CharField(
        max_length=50,
        choices=[
            ("신규가입", "신규가입"),
            ("번호이동", "번호이동"),
            ("기기변경", "기기변경"),
        ],
        default=("기기변경", "기기변경"),
    )
    subsidy_amount_standard = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="공시지원금",
        null=True,
        blank=True,
    )
    subsidy_amount_mnp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="전환지원금",
        null=True,
        blank=True,
    )
    pio_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="추가지원금",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.product.name} - {self.discount_type}/{self.contract_type}"


class ProductDetailImages(SoftDeleteModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="product_images/")
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return (
            f"Image for {self.product.name} - {self.description[:20]}..."
            if self.description
            else f"Image for {self.product.name}"
        )


class Product(SoftDeleteModel):
    name = models.CharField(max_length=100)
    best_price_option = models.ForeignKey(
        "ProductOptions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="best_price_option",
    )
    image_main = models.ImageField(upload_to="product_images/", blank=True)

    def __str__(self):
        return f"{self.name}"
