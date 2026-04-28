from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.urls import reverse

from phone.admin.content_admin import CardBenefitInlineForm, PartnerCardAdminForm
from phone.constants import CarrierChoices, CardSlotChoices, DiscountTypeChoices
from phone.models import (
    CardAdditionalPromotion,
    CardBenefit,
    CardIssuer,
    PartnerCard,
    ProductSeries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_issuer(name="신한카드", sort_order=1):
    return CardIssuer.objects.create(name=name, sort_order=sort_order, is_active=True)


def make_card(issuer, name="Deep Dream", carriers=None, discount_types=None, **kwargs):
    return PartnerCard.objects.create(
        issuer=issuer,
        name=name,
        carriers=carriers or ["SK", "KT"],
        discount_types=discount_types or ["할부"],
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Unit — CardIssuer
# ---------------------------------------------------------------------------


class CardIssuerStrTest(TestCase):
    def test_str_returns_name(self):
        issuer = CardIssuer(name="KB국민카드")
        self.assertEqual(str(issuer), "KB국민카드")


# ---------------------------------------------------------------------------
# Unit — PartnerCard 라운드트립
# ---------------------------------------------------------------------------


class PartnerCardRoundtripTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer()

    def test_carriers_array_roundtrip(self):
        card = make_card(self.issuer, carriers=["SK", "KT"])
        card.refresh_from_db()
        self.assertEqual(card.carriers, ["SK", "KT"])

    def test_discount_types_array_roundtrip(self):
        card = make_card(self.issuer, discount_types=["할부", "무선청구"])
        card.refresh_from_db()
        self.assertEqual(card.discount_types, ["할부", "무선청구"])

    def test_default_carriers_is_empty_list(self):
        card = PartnerCard.objects.create(issuer=self.issuer, name="빈카드")
        self.assertEqual(card.carriers, [])

    def test_default_discount_types_is_empty_list(self):
        card = PartnerCard.objects.create(issuer=self.issuer, name="빈카드2")
        self.assertEqual(card.discount_types, [])


# ---------------------------------------------------------------------------
# Unit — CardBenefit
# ---------------------------------------------------------------------------


class CardBenefitTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer()
        self.card = make_card(self.issuer)

    def test_basic_benefit_created(self):
        b = CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=0, amount=6000
        )
        self.assertEqual(b.kind, "basic")
        self.assertEqual(b.threshold_amount, 0)
        self.assertEqual(b.amount, 6000)

    def test_multiple_benefits_per_card(self):
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=0, amount=6000
        )
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=300000, amount=12000
        )
        CardBenefit.objects.create(
            card=self.card, kind="additional", threshold_amount=0, amount=5000
        )
        self.assertEqual(self.card.card_benefits.count(), 3)

    def test_max_threshold_selection_helper(self):
        """실적 ≤ threshold 중 max threshold 1개 선택 패턴 검증."""
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=0, amount=6000
        )
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=300000, amount=12000
        )
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=500000, amount=18000
        )

        user_spending = 350000
        eligible = (
            self.card.card_benefits.filter(
                kind="basic", threshold_amount__lte=user_spending
            )
            .order_by("-threshold_amount")
            .first()
        )
        self.assertIsNotNone(eligible)
        self.assertEqual(eligible.threshold_amount, 300000)
        self.assertEqual(eligible.amount, 12000)

    def test_no_eligible_benefit_when_spending_below_all(self):
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=300000, amount=12000
        )
        user_spending = 100000
        eligible = (
            self.card.card_benefits.filter(
                kind="basic", threshold_amount__lte=user_spending
            )
            .order_by("-threshold_amount")
            .first()
        )
        self.assertIsNone(eligible)


# ---------------------------------------------------------------------------
# Unit — 만원→원 변환 helper (CardBenefitInlineForm)
# ---------------------------------------------------------------------------


class ManwonToWonConversionTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer()
        self.card = make_card(self.issuer)

    def _make_form_data(self, manwon, kind="basic", amount=10000):
        return {
            "card": self.card.pk,
            "kind": kind,
            "threshold_amount_manwon": manwon,
            "amount": amount,
        }

    def test_manwon_20_saves_as_200000(self):
        form = CardBenefitInlineForm(data=self._make_form_data(20))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.threshold_amount, 200000)

    def test_manwon_0_saves_as_0(self):
        form = CardBenefitInlineForm(data=self._make_form_data(0))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.threshold_amount, 0)

    def test_negative_manwon_is_invalid(self):
        form = CardBenefitInlineForm(data=self._make_form_data(-1))
        self.assertFalse(form.is_valid())
        self.assertIn("threshold_amount_manwon", form.errors)

    def test_manwon_30_saves_as_300000(self):
        form = CardBenefitInlineForm(data=self._make_form_data(30))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.threshold_amount, 300000)


# ---------------------------------------------------------------------------
# Unit — CardAdditionalPromotion M2M target_series
# ---------------------------------------------------------------------------


class CardAdditionalPromotionTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer()
        self.card = make_card(self.issuer)
        self.series1 = ProductSeries.objects.create(name="갤럭시 S25", sort_order=1)
        self.series2 = ProductSeries.objects.create(name="갤럭시 S24", sort_order=2)

    def test_target_series_m2m_add(self):
        promo = CardAdditionalPromotion.objects.create(
            card=self.card, title="S25 캐시백", cashback_amount=100000
        )
        promo.target_series.add(self.series1, self.series2)
        self.assertEqual(promo.target_series.count(), 2)

    def test_target_series_m2m_remove(self):
        promo = CardAdditionalPromotion.objects.create(
            card=self.card, title="S25 캐시백", cashback_amount=100000
        )
        promo.target_series.add(self.series1, self.series2)
        promo.target_series.remove(self.series2)
        self.assertEqual(promo.target_series.count(), 1)
        self.assertIn(self.series1, promo.target_series.all())


# ---------------------------------------------------------------------------
# Unit — SoftDelete
# ---------------------------------------------------------------------------


class PartnerCardSoftDeleteTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer()
        self.card = make_card(self.issuer)

    def test_soft_delete_hides_from_default_manager(self):
        card_id = self.card.pk
        self.card.delete()
        self.assertFalse(PartnerCard.objects.filter(pk=card_id).exists())

    def test_soft_delete_sets_deleted_at(self):
        self.card.delete()
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT deleted_at FROM phone_partnercard WHERE id = %s",
                [self.card.pk],
            )
            deleted_at = cursor.fetchone()[0]
        self.assertIsNotNone(deleted_at)

    def test_card_issuer_soft_delete(self):
        issuer_id = self.issuer.pk
        self.issuer.delete()
        self.assertFalse(CardIssuer.objects.filter(pk=issuer_id).exists())


# ---------------------------------------------------------------------------
# Unit — constants
# ---------------------------------------------------------------------------


class CardSlotChoicesTest(TestCase):
    def test_installment_value(self):
        self.assertEqual(CardSlotChoices.INSTALLMENT, "할부")

    def test_wireless_billing_value(self):
        self.assertEqual(CardSlotChoices.WIRELESS_BILLING, "무선청구")

    def test_wired_billing_value(self):
        self.assertEqual(CardSlotChoices.WIRED_BILLING, "유선청구")

    def test_choices_has_three_items(self):
        self.assertEqual(len(CardSlotChoices.CHOICES), 3)

    def test_discount_type_choices_unchanged(self):
        """기존 DiscountTypeChoices(보조금)가 변경되지 않았는지 확인."""
        self.assertEqual(DiscountTypeChoices.SUBSIDY, "공시지원금")
        self.assertEqual(DiscountTypeChoices.SELECTION, "선택약정")

    def test_card_slot_choices_independent_from_discount_type(self):
        """CardSlotChoices와 DiscountTypeChoices는 별도 클래스."""
        slot_values = {c[0] for c in CardSlotChoices.CHOICES}
        discount_values = {c[0] for c in DiscountTypeChoices.CHOICES}
        self.assertTrue(slot_values.isdisjoint(discount_values))


# ---------------------------------------------------------------------------
# Integration — API GET /phone/partner-cards
# ---------------------------------------------------------------------------


class PartnerCardAPITest(TestCase):
    def setUp(self):
        self.issuer = make_issuer("현대카드")
        self.card = make_card(
            self.issuer,
            name="현대카드 M",
            carriers=["SK", "KT"],
            discount_types=["할부"],
            is_active=True,
            sort_order=1,
        )
        CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=0, amount=6000
        )
        CardBenefit.objects.create(
            card=self.card, kind="additional", threshold_amount=300000, amount=5000
        )

    def test_list_returns_200(self):
        response = self.client.get("/phone/partner-cards")
        self.assertEqual(response.status_code, 200)

    def test_new_schema_fields_present(self):
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        self.assertTrue(len(results) > 0)
        card = results[0]
        for field in [
            "id",
            "issuer",
            "name",
            "carriers",
            "discount_types",
            "card_benefits",
            "additional_promotions",
            "sort_order",
            "is_active",
        ]:
            self.assertIn(field, card, f"필드 '{field}' 누락")

    def test_old_fields_absent(self):
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        card = results[0]
        for old_field in ["carrier", "benefit_type", "link", "contact"]:
            self.assertNotIn(old_field, card, f"구 필드 '{old_field}' 여전히 존재")

    def test_carriers_is_list(self):
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        self.assertIsInstance(results[0]["carriers"], list)

    def test_card_benefits_new_structure(self):
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        benefits = results[0]["card_benefits"]
        self.assertTrue(len(benefits) > 0)
        benefit = benefits[0]
        for field in ["kind", "threshold_amount", "amount"]:
            self.assertIn(field, benefit, f"card_benefits 필드 '{field}' 누락")
        for old_field in ["condition", "benefit_price", "is_optional"]:
            self.assertNotIn(
                old_field, benefit, f"구 benefit 필드 '{old_field}' 여전히 존재"
            )

    def test_issuer_nested_object(self):
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        issuer = results[0]["issuer"]
        self.assertIn("id", issuer)
        self.assertIn("name", issuer)
        self.assertEqual(issuer["name"], "현대카드")

    def test_inactive_card_excluded(self):
        inactive_issuer = make_issuer("롯데카드")
        make_card(inactive_issuer, name="롯데 inactive", is_active=False)
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        names = [c["name"] for c in results]
        self.assertNotIn("롯데 inactive", names)

    def test_soft_deleted_card_excluded(self):
        deleted_issuer = make_issuer("삼성카드")
        deleted_card = make_card(deleted_issuer, name="삼성 deleted")
        deleted_card.delete()
        response = self.client.get("/phone/partner-cards")
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        names = [c["name"] for c in results]
        self.assertNotIn("삼성 deleted", names)

    def test_query_count(self):
        """prefetch 적용으로 쿼리 수가 합리적 범위 내인지 확인."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            self.client.get("/phone/partner-cards")
        # 메인(1) + card_benefits prefetch(1) + additional_promotions prefetch(1)
        # + target_series M2M prefetch(1) = 최대 5 (페이지네이션 count 포함)
        self.assertLessEqual(len(ctx.captured_queries), 6)


# ---------------------------------------------------------------------------
# Integration — Admin 페이지 접근 + CheckboxSelectMultiple 위젯
# ---------------------------------------------------------------------------


class PartnerCardAdminTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin", password="adminpass", email="admin@test.com"
        )
        self.client.login(username="admin", password="adminpass")
        self.issuer = make_issuer("KB국민카드")

    def test_add_page_returns_200(self):
        response = self.client.get("/admin/phone/partnercard/add/")
        self.assertEqual(response.status_code, 200)

    def test_add_page_has_checkbox_for_carriers(self):
        response = self.client.get("/admin/phone/partnercard/add/")
        self.assertContains(response, 'type="checkbox"')

    def test_card_issuer_add_page_returns_200(self):
        response = self.client.get("/admin/phone/cardissuer/add/")
        self.assertEqual(response.status_code, 200)

    def test_card_issuer_list_page_returns_200(self):
        response = self.client.get("/admin/phone/cardissuer/")
        self.assertEqual(response.status_code, 200)

    def test_partner_card_list_page_returns_200(self):
        response = self.client.get("/admin/phone/partnercard/")
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Integration — PartnerCardAdminForm 유효성 검사
# ---------------------------------------------------------------------------


class PartnerCardAdminFormTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer("신한카드")

    def _base_data(self):
        return {
            "issuer": self.issuer.pk,
            "name": "신한 Deep Dream",
            "carriers": ["SK", "KT"],
            "discount_types": ["할부"],
            "add_discount_condition": "",
            "installment_excluded_items": "",
            "annual_fee": 10000,
            "sort_order": 1,
            "is_active": True,
        }

    def test_valid_form(self):
        form = PartnerCardAdminForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_carriers_required(self):
        data = self._base_data()
        data["carriers"] = []
        form = PartnerCardAdminForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("carriers", form.errors)

    def test_discount_types_required(self):
        data = self._base_data()
        data["discount_types"] = []
        form = PartnerCardAdminForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("discount_types", form.errors)

    def test_invalid_carrier_rejected(self):
        data = self._base_data()
        data["carriers"] = ["INVALID_CARRIER"]
        form = PartnerCardAdminForm(data=data)
        self.assertFalse(form.is_valid())

    def test_invalid_discount_type_rejected(self):
        data = self._base_data()
        data["discount_types"] = ["잘못된슬롯"]
        form = PartnerCardAdminForm(data=data)
        self.assertFalse(form.is_valid())


# ---------------------------------------------------------------------------
# Integration — CardBenefitInlineForm 저장 round-trip (DB)
# ---------------------------------------------------------------------------


class CardBenefitInlineFormDBTest(TestCase):
    def setUp(self):
        self.issuer = make_issuer()
        self.card = make_card(self.issuer)

    def test_manwon_20_stored_as_200000_in_db(self):
        form = CardBenefitInlineForm(
            data={
                "card": self.card.pk,
                "kind": "basic",
                "threshold_amount_manwon": 20,
                "amount": 12000,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        benefit = form.save()
        benefit.refresh_from_db()
        self.assertEqual(benefit.threshold_amount, 200000)

    def test_initial_value_shown_in_manwon_on_edit(self):
        """기존 threshold_amount=200000인 인스턴스 편집 시 initial이 20(만원)으로 표시."""
        benefit = CardBenefit.objects.create(
            card=self.card, kind="basic", threshold_amount=200000, amount=12000
        )
        form = CardBenefitInlineForm(instance=benefit)
        self.assertEqual(form.fields["threshold_amount_manwon"].initial, 20)
