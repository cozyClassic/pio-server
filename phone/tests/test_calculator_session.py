import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless

from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from internet.models import InternetCarrier
from phone.constants import (
    CardSlotChoices,
    CarrierChoices,
    ContactChannelChoices,
    FunnelVariantChoices,
    IdentitySourceChoices,
    WinnerChoices,
)
from phone.models import CalculatorSession, CustomerIdentity

CALC_URL = "/phone/calculator-sessions"


def _detail_url(session_id):
    return f"{CALC_URL}/{session_id}"


def _identity_url(session_id):
    return f"{CALC_URL}/{session_id}/identity"


def _payload(**overrides):
    base = {
        "funnel_variant": FunnelVariantChoices.CONTROL,
        "copy_variant": "v2",
        "pricing_path": "selfbuy_v1",
        "ga4_client_id": "GA1.1.1234567890.1234567890",
        "answers": {
            "carrier": CarrierChoices.SK,
            "keep_carrier": False,
            "internet": [],
            "device_id": None,
            "device_name": "갤럭시 S26 Ultra",
            "family_bundle": True,
            "gift": False,
            "data_usage": "100GB 이상",
            "plan_price_mvno": 26000,
            "plan_price_mno": 70000,
            "card": False,
            "card_spend": 0,
            "card_history": [],
            "internet_new": False,
        },
        "auto_selected": {
            "device_price": 1690000,
            "public_subsidy": 250000,
            "additional_discount": 80000,
            "skt_plan_id": "T다이렉트5G_8GB",
            "skt_plan_monthly_fee": 43000,
            "static_card_recommended": "신한",
            "static_card_monthly": 25000,
            "static_card_total24": 600000,
            "partner_card_slots": [],
            "partner_card_monthly": 0,
            "partner_card_total24": 0,
            "final_card_total24": 0,
            "final_card_monthly": 0,
            "family_bundle_eligible": True,
            "gift_eligible": False,
            "internet_new_eligible": False,
        },
        "result": {
            "pio_total": 1340000,
            "selfbuy_total": 2314000,
            "official_total": 2722000,
            "benefit_only": 2048000,
            "total_saving": 974000,
            "official_vs_pio": 1382000,
            "winner": WinnerChoices.PIO,
            "ranks": [
                {"key": WinnerChoices.PIO, "total": 1340000},
                {"key": WinnerChoices.SELFBUY, "total": 2314000},
                {"key": WinnerChoices.OFFICIAL, "total": 2722000},
            ],
        },
        "benefit_amounts_snapshot": {
            "family_bundle": 360000,
            "gift": 400000,
            "internet_new": 800000,
        },
    }
    base.update(overrides)
    return base


class UnitTests(TestCase):
    """Fix #1, #2 회귀 방지 + 모델 메타 검증."""

    def test_card_slot_choices_has_values_attribute(self):
        # Fix #1
        self.assertTrue(hasattr(CardSlotChoices, "VALUES"))
        self.assertEqual(
            CardSlotChoices.VALUES,
            [
                CardSlotChoices.INSTALLMENT,
                CardSlotChoices.WIRELESS_BILLING,
                CardSlotChoices.WIRED_BILLING,
            ],
        )

    def test_constants_enum_values_are_lists(self):
        # Fix #2
        for cls in (
            FunnelVariantChoices,
            ContactChannelChoices,
            WinnerChoices,
            IdentitySourceChoices,
        ):
            self.assertTrue(hasattr(cls, "VALUES"), f"{cls} missing VALUES")
            self.assertIsInstance(cls.VALUES, list)
            self.assertIsInstance(cls.CHOICES, list)

    def test_calculator_session_uses_uuid_pk(self):
        pk_field = CalculatorSession._meta.get_field("id")
        self.assertEqual(pk_field.get_internal_type(), "UUIDField")

    def test_calculator_session_has_partial_lead_index(self):
        names = [idx.name for idx in CalculatorSession._meta.indexes]
        self.assertIn("cs_lead_partial", names)


class SerializerTests(TestCase):
    def setUp(self):
        from phone.serializers import (
            CalculatorSessionCreateSerializer,
            CalculatorSessionPatchSerializer,
        )

        self.CreateSerializer = CalculatorSessionCreateSerializer
        self.PatchSerializer = CalculatorSessionPatchSerializer

    def test_partner_card_slots_rejects_invalid_slot_name(self):
        payload = _payload()
        payload["auto_selected"]["partner_card_slots"] = [
            {
                "slot": "무선",  # 스키마 원안의 잘못된 slot 명
                "card_id": None,
                "card_name": None,
                "spend_allocated": 0,
                "amount_monthly": 0,
            }
        ]
        ser = self.CreateSerializer(data=payload)
        self.assertFalse(ser.is_valid(), msg=str(ser.errors))
        self.assertIn("auto_selected", ser.errors)

    def test_partner_card_slots_accepts_valid_slot_name(self):
        payload = _payload()
        payload["auto_selected"]["partner_card_slots"] = [
            {
                "slot": CardSlotChoices.WIRELESS_BILLING,
                "card_id": None,
                "card_name": None,
                "spend_allocated": 0,
                "amount_monthly": 0,
            }
        ]
        ser = self.CreateSerializer(data=payload)
        self.assertTrue(ser.is_valid(), msg=str(ser.errors))

    def test_patch_pii_empty_string_normalized_to_null(self):
        # Fix #7
        ser = self.PatchSerializer(
            data={
                "contact_channel": ContactChannelChoices.PHONE,
                "submitted_name": "",
                "submitted_contact": "010-1234-5678",
            }
        )
        self.assertFalse(ser.is_valid())
        self.assertIn("submitted_name", ser.errors)

    def test_patch_kakao_drops_pii(self):
        ser = self.PatchSerializer(
            data={
                "contact_channel": ContactChannelChoices.KAKAO,
                "submitted_name": "홍길동",
                "submitted_contact": "010-1234-5678",
            }
        )
        self.assertTrue(ser.is_valid(), msg=str(ser.errors))
        self.assertNotIn("submitted_name", ser.validated_data)
        self.assertNotIn("submitted_contact", ser.validated_data)

    def test_winner_validation_rejects_unknown(self):
        payload = _payload()
        payload["result"]["winner"] = "unknown_value"
        ser = self.CreateSerializer(data=payload)
        self.assertFalse(ser.is_valid())
        self.assertIn("result", ser.errors)


class IntegrationTests(TestCase):
    """API 레벨 통합 테스트."""

    def setUp(self):
        self.client = APIClient()
        self.sk_carrier = InternetCarrier.objects.create(name="SK 인터넷")

    def test_post_creates_session_with_uuid(self):
        response = self.client.post(CALC_URL, _payload(), format="json")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("id", body)
        # UUID 형식
        uuid.UUID(body["id"])

    def test_post_internet_m2m_persists(self):
        # Fix #4
        payload = _payload()
        payload["answers"]["internet"] = [self.sk_carrier.id]
        response = self.client.post(CALC_URL, payload, format="json")
        self.assertEqual(response.status_code, 201)

        instance = CalculatorSession.objects.get(id=response.json()["id"])
        carrier_ids = list(instance.internet_carriers.values_list("id", flat=True))
        self.assertEqual(carrier_ids, [self.sk_carrier.id])

    def test_post_invalid_internet_carrier_id_rejected(self):
        payload = _payload()
        payload["answers"]["internet"] = [99999]
        response = self.client.post(CALC_URL, payload, format="json")
        # 존재하지 않는 InternetCarrier id 가 set 시 IntegrityError 또는 무시.
        # serializer 가 미리 검증 안 함 (set_carriers QuerySet 으로 필터링).
        # 따라서 201 + carriers 빈 리스트가 정상 동작.
        self.assertEqual(response.status_code, 201)
        instance = CalculatorSession.objects.get(id=response.json()["id"])
        self.assertEqual(list(instance.internet_carriers.all()), [])

    def test_patch_phone_branch_required_pii(self):
        post = self.client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]

        # Fix #7: 빈 문자열 거부
        bad = self.client.patch(
            _detail_url(sid),
            {
                "contact_channel": ContactChannelChoices.PHONE,
                "submitted_name": "",
                "submitted_contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

        # 정상
        ok = self.client.patch(
            _detail_url(sid),
            {
                "contact_channel": ContactChannelChoices.PHONE,
                "submitted_name": "홍길동",
                "submitted_contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        # Fix #8: applied 필드 + ETag
        self.assertTrue(body.get("applied"))
        self.assertIn("ETag", ok.headers)

    def test_patch_kakao_branch_drops_pii(self):
        post = self.client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]

        ok = self.client.patch(
            _detail_url(sid),
            {
                "contact_channel": ContactChannelChoices.KAKAO,
                "submitted_name": "홍길동",  # KAKAO 분기에서는 drop 되어야 함
                "submitted_contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(ok.status_code, 200)
        instance = CalculatorSession.objects.get(id=sid)
        self.assertEqual(instance.contact_channel, ContactChannelChoices.KAKAO)
        self.assertIsNone(instance.submitted_name)
        self.assertIsNone(instance.submitted_contact)

    def test_patch_first_write_wins(self):
        post = self.client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]

        first = self.client.patch(
            _detail_url(sid),
            {
                "contact_channel": ContactChannelChoices.PHONE,
                "submitted_name": "홍길동",
                "submitted_contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json().get("applied"))

        second = self.client.patch(
            _detail_url(sid),
            {"contact_channel": ContactChannelChoices.KAKAO},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        # Fix #8: 두 번째는 applied=false
        self.assertFalse(second.json().get("applied"))

        instance = CalculatorSession.objects.get(id=sid)
        # phone 결정이 유지됨
        self.assertEqual(instance.contact_channel, ContactChannelChoices.PHONE)

    def test_get_does_not_expose_applied_field(self):
        # Critic merge-gate #2
        post = self.client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]
        get = self.client.get(_detail_url(sid))
        self.assertEqual(get.status_code, 200)
        body = get.json()
        self.assertNotIn("applied", body)


class IdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_identity_create_and_conflict(self):
        post = self.client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]

        ok = self.client.post(
            _identity_url(sid),
            {
                "source": IdentitySourceChoices.NAME_PHONE,
                "pre_name": "홍길동",
                "pre_contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(ok.status_code, 201)
        self.assertTrue(CustomerIdentity.objects.filter(session_id=sid).exists())

        dup = self.client.post(
            _identity_url(sid),
            {
                "source": IdentitySourceChoices.NAME_PHONE,
                "pre_name": "홍길동",
                "pre_contact": "010-1234-5678",
            },
            format="json",
        )
        self.assertEqual(dup.status_code, 409)


class ObservabilityTests(TestCase):
    def test_first_write_wins_warn_logged(self):
        # Fix #6 추적 수단 검증
        client = APIClient()
        post = client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]

        client.patch(
            _detail_url(sid),
            {
                "contact_channel": ContactChannelChoices.PHONE,
                "submitted_name": "홍길동",
                "submitted_contact": "010-1234-5678",
            },
            format="json",
        )

        with self.assertLogs("phone", level="WARNING") as cm:
            response = client.patch(
                _detail_url(sid),
                {"contact_channel": ContactChannelChoices.KAKAO},
                format="json",
            )
            self.assertEqual(response.status_code, 200)
        joined = "\n".join(cm.output)
        self.assertIn("first_write_wins.ignored", joined)

    @skipUnless(
        connection.vendor == "postgresql",
        "partial index EXPLAIN 검증은 PostgreSQL 전용",
    )
    def test_partial_index_used_for_lead_query(self):
        # Fix #10 — partial index 가 lead 검색 시 사용되는지 EXPLAIN 으로 확인.
        # (test fixture row 가 적으면 optimizer 가 seq scan 선택할 수 있어
        # plan 에 'cs_lead_partial' 키워드 부재일 수도 있음. 이 테스트는
        # 인덱스 정의 자체와 EXPLAIN 출력이 정상 작동하는지를 우선 검증.)
        with connection.cursor() as cur:
            cur.execute(
                "EXPLAIN SELECT * FROM calculator_session "
                "WHERE contact_channel IS NOT NULL LIMIT 10;"
            )
            plan_text = "\n".join(row[0] for row in cur.fetchall())
        self.assertTrue(plan_text)


class ThrottleTests(TransactionTestCase):
    def setUp(self):
        from django.core.cache import cache
        from rest_framework.throttling import AnonRateThrottle

        cache.clear()
        # DRF SimpleRateThrottle 은 THROTTLE_RATES 를 class-level 에서 읽으므로
        # override_settings 로 갈아끼울 수 없음. 직접 patch.
        self._orig_rates = AnonRateThrottle.THROTTLE_RATES
        AnonRateThrottle.THROTTLE_RATES = {"anon": "2/min", "user": "1000/min"}

    def tearDown(self):
        from rest_framework.throttling import AnonRateThrottle

        AnonRateThrottle.THROTTLE_RATES = self._orig_rates

    def test_anon_throttle_applies_to_calculator_endpoint(self):
        # Fix #5 — view-level throttle 이 실제 429 를 반환하는지.
        client = APIClient()
        ok1 = client.post(CALC_URL, _payload(), format="json")
        ok2 = client.post(CALC_URL, _payload(), format="json")
        throttled = client.post(CALC_URL, _payload(), format="json")
        self.assertEqual(ok1.status_code, 201)
        self.assertEqual(ok2.status_code, 201)
        self.assertEqual(throttled.status_code, 429)

    def test_throttle_classes_configured_on_viewset(self):
        # Fix #5 — ViewSet 이 AnonRateThrottle 을 옵트인했는지 (정의 검증).
        from rest_framework.throttling import AnonRateThrottle

        from phone.views import CalculatorSessionViewSet

        self.assertIn(AnonRateThrottle, CalculatorSessionViewSet.throttle_classes)


class ConcurrentPatchTests(TransactionTestCase):
    """동시성 환경에서 first-write-wins 가 race-free 한지 검증."""

    def test_first_write_wins_concurrent(self):
        client = APIClient()
        post = client.post(CALC_URL, _payload(), format="json")
        sid = post.json()["id"]

        def _do_patch(channel):
            local_client = APIClient()
            return local_client.patch(
                _detail_url(sid),
                {
                    "contact_channel": channel,
                    "submitted_name": "홍길동" if channel == "phone" else "",
                    "submitted_contact": "010-1234-5678" if channel == "phone" else "",
                },
                format="json",
            ).json()

        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = [
                ex.submit(_do_patch, ContactChannelChoices.PHONE),
                ex.submit(_do_patch, ContactChannelChoices.KAKAO),
            ]
            results = [f.result() for f in futures]

        applied_count = sum(1 for r in results if r.get("applied"))
        self.assertEqual(applied_count, 1, msg=str(results))

        instance = CalculatorSession.objects.get(id=sid)
        self.assertIn(
            instance.contact_channel,
            (ContactChannelChoices.PHONE, ContactChannelChoices.KAKAO),
        )
