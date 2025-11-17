from django.db import models

# Create your models here.
INSTALLATION_TYPES = [
    ("I", "Internet"),
    ("IT", "Internet + TV"),
    ("AT", "Additional TV"),
]


class CombinedDataView(models.Model):
    pass

    class Meta:
        managed = False  # ★★★ 이것이 핵심! DB 테이블을 만들지 않습니다.
        verbose_name = "종합 리포트"
        verbose_name_plural = "종합 리포트"


class InternetCarrier(models.Model):
    name = models.CharField(max_length=100)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to="carrier_logos/", blank=True, null=True)
    wifi_router_rental_price_per_month = models.IntegerField(default=0)
    tv_settop_box_rental_price_per_month = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class InternetPlan(models.Model):
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="internet_plans"
    )
    name = models.CharField(max_length=100)
    speed = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    internet_price_per_month = models.IntegerField(default=0)
    internet_contract_discount = models.IntegerField(default=0)
    is_wifi_router_free = models.BooleanField(default=False)
    is_wifi_router_selectable = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.speed}({self.name})"


class TVPlan(models.Model):
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="tv_plans"
    )
    name = models.CharField(max_length=100)
    channel_count = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    tv_price_per_month = models.IntegerField(default=0)
    tv_contract_discount = models.IntegerField(default=0)
    is_settop_box_free = models.BooleanField(default=False)
    is_settop_box_selectable = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.channel_count} ({self.name})"


class BundleCondition(models.Model):
    MOBILE_TYPES = [
        ("MNO", "MNO"),
        ("MVNO", "MVNO"),
        ("None", "None"),
    ]
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="bundle_conditions"
    )
    internet_plan = models.ForeignKey(
        InternetPlan, on_delete=models.CASCADE, related_name="bundle_conditions"
    )
    tv_plan = models.ForeignKey(
        TVPlan, on_delete=models.CASCADE, related_name="bundle_conditions"
    )
    mobile_price_min = models.IntegerField(default=0)
    mobile_type = models.CharField(
        max_length=50, choices=MOBILE_TYPES, blank=True, null=True
    )

    class Meta:
        unique_together = ("carrier", "internet_plan", "tv_plan", "mobile_type")

    def __str__(self):
        return f"{self.carrier.name}/인터넷 {self.internet_plan}/TV {self.tv_plan}/모바일 {self.mobile_type}"


class BundleDiscount(models.Model):
    DISCOUNT_TYPES = [
        ("Mobile", "Mobile"),
        ("Internet", "Internet"),
        ("TV", "TV"),
    ]
    bundle_condition = models.ForeignKey(
        BundleCondition, on_delete=models.CASCADE, related_name="bundle_discounts"
    )
    bundle_name = models.CharField(max_length=100)
    discount_type = models.CharField(max_length=100, choices=DISCOUNT_TYPES)
    discount_amount = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.bundle_name} ({self.discount_type})"


class BundlePromotion(models.Model):
    bundle_condition = models.ForeignKey(
        BundleCondition, on_delete=models.CASCADE, related_name="bundle_promotions"
    )
    coupon_amount = models.IntegerField(default=0)
    cash_amount = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.bundle_condition}"


class InstallationOption(models.Model):
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="installation_options"
    )
    installation_type = models.CharField(max_length=2, choices=INSTALLATION_TYPES)
    installation_fee = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.carrier.name} - {self.get_installation_type_display()}"
