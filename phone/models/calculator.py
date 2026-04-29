import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

from phone.constants import (
    CarrierChoices,
    ContactChannelChoices,
    FunnelVariantChoices,
    IdentitySourceChoices,
    WinnerChoices,
)

from .base import SoftDeleteModel


class CalculatorSession(SoftDeleteModel):
    """
    Calculator 1회 진행 = 1 row.
    - result_view 시점 POST → submit/카톡클릭 시점 PATCH (2-hit lifecycle).
    - first-write-wins: contact_channel IS NOT NULL row 의 PATCH 는 무시.
    - simple_history 미적용 결정:
        (1) PII 변경 row 가 history 테이블에 영구 보존 → anonymize cron 과 충돌
        (2) volume 대비 storage cost
        (3) PATCH 가 단 1회 (first-write-wins) 라 변경 추적 가치 낮음
        추적 수단: applied 응답 + first_write_wins.ignored WARN 로그.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    funnel_variant = models.CharField(
        max_length=20,
        choices=FunnelVariantChoices.CHOICES,
        default=FunnelVariantChoices.CONTROL,
    )
    copy_variant = models.CharField(max_length=50, default="v2")
    pricing_path = models.CharField(max_length=50, default="selfbuy_v1")
    copy_variant_v3 = models.CharField(max_length=50, null=True, blank=True)

    contact_channel = models.CharField(
        max_length=20,
        choices=ContactChannelChoices.CHOICES,
        null=True,
        blank=True,
    )
    name_field_omitted = models.BooleanField(default=False)

    carrier = models.CharField(
        max_length=10,
        choices=CarrierChoices.CHOICES,
        null=True,
        blank=True,
    )
    keep_carrier = models.BooleanField(null=True)

    internet_carriers = models.ManyToManyField(
        "internet.InternetCarrier",
        blank=True,
        related_name="calculator_sessions",
    )

    device = models.ForeignKey(
        "phone.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="calculator_sessions",
    )
    device_name = models.CharField(max_length=100, null=True, blank=True)

    family_bundle = models.BooleanField(null=True)
    gift = models.BooleanField(null=True)
    data_usage = models.CharField(max_length=20, null=True, blank=True)
    plan_price_mvno = models.IntegerField(null=True)
    plan_price_mno = models.IntegerField(null=True)
    card = models.BooleanField(null=True)
    card_spend = models.IntegerField(null=True)
    card_history = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    internet_new = models.BooleanField(null=True)

    device_price = models.IntegerField(default=0)
    public_subsidy = models.IntegerField(default=0)
    additional_discount = models.IntegerField(default=0)

    skt_plan_id = models.CharField(max_length=50, null=True, blank=True)
    skt_plan_monthly_fee = models.IntegerField(default=0)

    static_card_recommended = models.CharField(max_length=20, null=True, blank=True)
    static_card_monthly = models.IntegerField(default=0)
    static_card_total24 = models.IntegerField(default=0)

    partner_card_slots = models.JSONField(default=list, blank=True)
    partner_card_monthly = models.IntegerField(default=0)
    partner_card_total24 = models.IntegerField(default=0)

    final_card_total24 = models.IntegerField(default=0)
    final_card_monthly = models.IntegerField(default=0)

    family_bundle_eligible = models.BooleanField(default=False)
    gift_eligible = models.BooleanField(default=False)
    internet_new_eligible = models.BooleanField(default=False)

    pio_total = models.IntegerField(default=0)
    selfbuy_total = models.IntegerField(default=0)
    official_total = models.IntegerField(default=0)
    benefit_only = models.IntegerField(default=0)
    total_saving = models.IntegerField(default=0)
    official_vs_pio = models.IntegerField(default=0)
    winner = models.CharField(
        max_length=10,
        choices=WinnerChoices.CHOICES,
        null=True,
        blank=True,
    )
    ranks = models.JSONField(default=list, blank=True)
    benefit_amounts_snapshot = models.JSONField(default=dict, blank=True)

    submitted_name = models.CharField(max_length=50, null=True, blank=True)
    submitted_contact = models.CharField(max_length=20, null=True, blank=True)

    ga4_client_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "calculator_session"
        indexes = [
            models.Index(fields=["funnel_variant", "contact_channel"]),
            models.Index(fields=["ga4_client_id"]),
            models.Index(
                fields=["contact_channel"],
                name="cs_lead_partial",
                condition=models.Q(contact_channel__isnull=False),
            ),
        ]

    def __str__(self):
        return (
            f"CalcSession({self.id} / {self.funnel_variant} / "
            f"{self.contact_channel or 'abandoned'})"
        )


class CustomerIdentity(SoftDeleteModel):
    """V1 placeholder. 모델·endpoint 만 두고 운영 invocation 은 V1 release 에 활성."""

    session = models.OneToOneField(
        CalculatorSession,
        on_delete=models.CASCADE,
        related_name="identity",
    )
    source = models.CharField(
        max_length=20,
        choices=IdentitySourceChoices.CHOICES,
        default=IdentitySourceChoices.NAME_PHONE,
    )
    pre_name = models.CharField(max_length=50)
    pre_contact = models.CharField(max_length=20)
    identified_at = models.DateTimeField()

    oauth_provider = models.CharField(max_length=20, null=True, blank=True)
    oauth_user_id = models.CharField(max_length=100, null=True, blank=True)
    oauth_email = models.EmailField(null=True, blank=True)
    oauth_phone = models.CharField(max_length=20, null=True, blank=True)
    oauth_raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "customer_identity"
        indexes = [
            models.Index(fields=["oauth_provider", "oauth_user_id"]),
        ]

    def __str__(self):
        return f"Identity({self.session_id} / {self.source})"
