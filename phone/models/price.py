from django.db import models

from phone.constants import CarrierChoices

from .base import SoftDeleteModel
from .product import Product
from .plan import Plan


class PriceHistory(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="best_prices"
    )
    carrier = models.CharField(max_length=100, choices=CarrierChoices.CHOICES)
    final_price = models.IntegerField(help_text="최종 가격", null=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="best_prices")
    price_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.price_at}"

    class Meta:
        unique_together = ("product", "price_at", "carrier")


class PriceNotificationRequest(SoftDeleteModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_notifications"
    )
    customer_phone = models.CharField(max_length=15)
    target_price = models.IntegerField(help_text="Target price for notification")
    prev_carrier = models.CharField(
        max_length=50,
        choices=CarrierChoices.CHOICES,
        help_text="Previous carrier",
        default=CarrierChoices.MVNO,
    )
    notified_at = models.DateTimeField(
        null=True, blank=True, help_text="Notification timestamp", default=None
    )
    channel_talk_user_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Channel Talk User ID for notification",
        default="",
    )
