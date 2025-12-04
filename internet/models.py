from django.db import models

# Create your models here.
INSTALLATION_TYPES = [
    ("I", "Internet"),
    ("T", "TV"),
    ("AI", "Additional Internet"),
    ("AT", "Additional TV"),
]


class CombinedDataView(models.Model):
    pass

    class Meta:
        managed = False
        verbose_name = "종합 리포트"
        verbose_name_plural = "종합 리포트"


class InternetCarrier(models.Model):
    name = models.CharField(max_length=100)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to="carrier_logos/", blank=True, null=True)

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
    isWifiIncluded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.speed}({self.name})({self.carrier.name})"


class WifiOption(models.Model):
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="wifi_options"
    )
    name = models.CharField(max_length=100)
    rental_price_per_month = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name}"


class TVPlan(models.Model):
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="tv_plans"
    )
    name = models.CharField(max_length=100)
    channel_count = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    tv_price_per_month = models.IntegerField(default=0)
    tv_contract_discount = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.channel_count} ({self.name})"


class SettopBoxOption(models.Model):
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="settop_box_options"
    )
    name = models.CharField(max_length=100)
    rental_price_per_month = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name}"


class BundleCondition(models.Model):
    MOBILE_TYPES = [
        ("MNO", "MNO"),
        ("MVNO", "MVNO"),
    ]
    carrier = models.ForeignKey(
        InternetCarrier, on_delete=models.CASCADE, related_name="bundle_conditions"
    )
    internet_plan = models.ForeignKey(
        InternetPlan, on_delete=models.CASCADE, related_name="bundle_conditions"
    )
    tv_plan = models.ForeignKey(
        TVPlan,
        on_delete=models.CASCADE,
        related_name="bundle_conditions",
        null=True,
        blank=True,
    )
    wifi_option = models.ForeignKey(
        WifiOption,
        on_delete=models.CASCADE,
        related_name="bundle_conditions",
        null=True,
        blank=True,
    )
    settop_box_option = models.ForeignKey(
        SettopBoxOption,
        on_delete=models.CASCADE,
        related_name="bundle_conditions",
        null=True,
        blank=True,
    )
    mobile_price_min = models.IntegerField(default=0)
    mobile_type = models.CharField(
        max_length=50, choices=MOBILE_TYPES, blank=True, null=True
    )

    class Meta:
        unique_together = (
            "carrier",
            "internet_plan",
            "tv_plan",
            "mobile_type",
            "wifi_option",
            "settop_box_option",
        )

    def __str__(self):
        return f"{self.internet_plan_id}/{self.tv_plan_id}/{self.mobile_type}"


class BundleDiscount(models.Model):
    DISCOUNT_TYPES = [
        ("Mobile", "Mobile"),
        ("Internet", "Internet"),
        ("TV", "TV"),
        ("Internet_Install", "Internet Install"),
        ("TV_Install", "TV Install"),
        ("Wifi", "Wifi"),
        ("TV_Settop", "TV Settop"),
    ]
    bundle_condition = models.ForeignKey(
        BundleCondition, on_delete=models.CASCADE, related_name="bundle_discounts"
    )
    bundle_name = models.CharField(max_length=100)
    discount_type = models.CharField(max_length=100, choices=DISCOUNT_TYPES)
    discount_amount = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.bundle_name} ({self.discount_type})"

    class Meta:
        unique_together = (
            "bundle_condition",
            "bundle_name",
            "discount_type",
        )


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


class Inquiry(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ("주문접수", "주문접수"),
            ("해피콜진행중", "해피콜진행중"),
            ("해피콜완료", "해피콜완료"),
            ("설치요청", "설치요청"),
            ("설치중", "설치중"),
            ("배송완료", "배송완료"),
            ("개통대기", "개통대기"),
            ("개통완료", "개통완료"),
            ("사은품지급완료", "사은품지급완료"),
            ("취소요청", "취소요청"),
            ("취소완료", "취소완료"),
        ],
        default="주문접수",
    )
    bundle_condition = models.ForeignKey(
        BundleCondition, on_delete=models.CASCADE, related_name="inquiries"
    )

    def __str__(self):
        return f"Inquiry from {self.name} ({self.contact}) at {self.created_at}"
