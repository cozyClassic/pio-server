"""1회성 시드 마이그레이션 — PartnerCard·CardBenefit·CardAdditionalPromotion·CardIssuer.

12개 사용자 결정사항 기반으로 .omc/output/card_list_merged.json을 가공한
phone/migrations/_seed_partner_cards_data.py 모듈을 import해서 INSERT한다.

reverse는 시드된 카드명 목록을 기준으로 soft delete (deleted_at = now()).
"""

from datetime import date

from django.db import migrations
from django.utils import timezone

from phone.migrations._seed_partner_cards_data import PARTNER_CARDS


def _to_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def forwards(apps, _schema_editor):
    del _schema_editor  # noqa: required by RunPython signature
    CardIssuer = apps.get_model("phone", "CardIssuer")
    PartnerCard = apps.get_model("phone", "PartnerCard")
    CardBenefit = apps.get_model("phone", "CardBenefit")
    CardAdditionalPromotion = apps.get_model("phone", "CardAdditionalPromotion")
    ProductSeries = apps.get_model("phone", "ProductSeries")

    issuer_names = sorted({c["issuer"] for c in PARTNER_CARDS if c.get("issuer")})
    issuer_map = {}
    for name in issuer_names:
        obj, _ = CardIssuer.objects.get_or_create(
            name=name,
            defaults={"sort_order": 0, "is_active": True},
        )
        issuer_map[name] = obj

    for c in PARTNER_CARDS:
        issuer = issuer_map.get(c["issuer"]) if c.get("issuer") else None
        card = PartnerCard.objects.create(
            issuer=issuer,
            name=c["name"],
            carriers=c.get("carriers", []),
            discount_types=c.get("discount_types", []),
            signup_start_date=_to_date(c.get("signup_start_date")),
            signup_end_date=_to_date(c.get("signup_end_date")),
            add_discount_months=c.get("add_discount_months"),
            add_discount_condition=c.get("add_discount_condition", "") or "",
            min_installment_amount=c.get("min_installment_amount"),
            installment_excluded_items=c.get("installment_excluded_items", "") or "",
            annual_fee=c.get("annual_fee", 0) or 0,
            contact=c.get("contact", "") or "",
            signup_url=c.get("signup_url", "") or "",
            extra_benefits=c.get("extra_benefits", "") or "",
            sort_order=c.get("sort_order", 0) or 0,
            is_active=c.get("is_active", True),
        )

        for b in c.get("benefits_basic", []) or []:
            CardBenefit.objects.create(
                card=card,
                kind="basic",
                threshold_amount=b["threshold"],
                amount=b["amount"],
            )
        for b in c.get("benefits_additional", []) or []:
            CardBenefit.objects.create(
                card=card,
                kind="additional",
                threshold_amount=b["threshold"],
                amount=b["amount"],
            )

        cb = c.get("cashback_promo")
        if cb:
            promo = CardAdditionalPromotion.objects.create(
                card=card,
                title=cb.get("title", "") or "",
                description=cb.get("description", "") or "",
                cashback_amount=cb.get("cashback_amount"),
                min_installment_amount=cb.get("min_installment_amount"),
                sort_order=cb.get("sort_order", 0) or 0,
                is_active=cb.get("is_active", True),
            )
            for series_id in cb.get("target_series_ids", []) or []:
                if ProductSeries.objects.filter(pk=series_id).exists():
                    promo.target_series.add(series_id)


def reverse(apps, _schema_editor):
    """시드된 카드들을 soft delete (deleted_at 채우기)."""
    del _schema_editor  # noqa: required by RunPython signature
    PartnerCard = apps.get_model("phone", "PartnerCard")
    CardBenefit = apps.get_model("phone", "CardBenefit")
    CardAdditionalPromotion = apps.get_model("phone", "CardAdditionalPromotion")

    names = [c["name"] for c in PARTNER_CARDS]
    now = timezone.now()

    CardAdditionalPromotion.objects.filter(
        card__name__in=names, deleted_at__isnull=True
    ).update(deleted_at=now)
    CardBenefit.objects.filter(card__name__in=names, deleted_at__isnull=True).update(
        deleted_at=now
    )
    PartnerCard.objects.filter(name__in=names, deleted_at__isnull=True).update(
        deleted_at=now
    )


class Migration(migrations.Migration):

    dependencies = [
        ("phone", "0071_partnercard_contact_partnercard_extra_benefits_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
