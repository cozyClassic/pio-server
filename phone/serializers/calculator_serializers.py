from rest_framework import serializers

from internet.models import InternetCarrier
from phone.constants import (
    CardSlotChoices,
    ContactChannelChoices,
    WinnerChoices,
)
from phone.models import CalculatorSession, CustomerIdentity, PartnerCard

SLOT_KEYS = {"slot", "card_id", "card_name", "spend_allocated", "amount_monthly"}


class CalculatorSessionCreateSerializer(serializers.Serializer):
    funnel_variant = serializers.CharField(max_length=20, required=False)
    copy_variant = serializers.CharField(max_length=50, required=False)
    pricing_path = serializers.CharField(max_length=50, required=False)
    ga4_client_id = serializers.CharField(
        max_length=64, required=False, allow_null=True, allow_blank=True
    )

    answers = serializers.DictField(required=False)
    auto_selected = serializers.DictField(required=False)
    result = serializers.DictField(required=False)
    benefit_amounts_snapshot = serializers.DictField(required=False)

    def validate_answers(self, answers):
        slot_value = answers.get("internet")
        if slot_value is not None and not isinstance(slot_value, list):
            raise serializers.ValidationError(
                {"internet": "internet 은 list 여야 합니다 (carrier id list)"}
            )
        return answers

    def validate_auto_selected(self, auto):
        slots = auto.get("partner_card_slots")
        if slots is None:
            return auto
        if not isinstance(slots, list):
            raise serializers.ValidationError(
                {"partner_card_slots": "list 여야 합니다"}
            )

        card_ids = []
        for idx, slot in enumerate(slots):
            if not isinstance(slot, dict):
                raise serializers.ValidationError(
                    {"partner_card_slots": f"index {idx} 는 dict 여야 합니다"}
                )
            missing = SLOT_KEYS - slot.keys()
            if missing:
                raise serializers.ValidationError(
                    {
                        "partner_card_slots": (
                            f"index {idx} 누락된 키: {sorted(missing)}"
                        )
                    }
                )
            if slot["slot"] not in CardSlotChoices.VALUES:
                raise serializers.ValidationError(
                    {
                        "partner_card_slots": (
                            f"index {idx} slot='{slot['slot']}' "
                            f"는 {CardSlotChoices.VALUES} 중 하나여야 합니다"
                        )
                    }
                )
            if slot["card_id"] is not None:
                card_ids.append(slot["card_id"])

        if card_ids:
            existing = set(
                PartnerCard.objects.filter(id__in=card_ids).values_list("id", flat=True)
            )
            missing_cards = set(card_ids) - existing
            if missing_cards:
                raise serializers.ValidationError(
                    {
                        "partner_card_slots": (
                            f"존재하지 않는 PartnerCard id: {sorted(missing_cards)}"
                        )
                    }
                )
        return auto

    def validate_result(self, result):
        winner = result.get("winner")
        if winner is not None and winner not in WinnerChoices.VALUES:
            raise serializers.ValidationError(
                {
                    "winner": (
                        f"winner='{winner}' 는 {WinnerChoices.VALUES} "
                        f"중 하나여야 합니다"
                    )
                }
            )
        ranks = result.get("ranks")
        if ranks is not None:
            if not isinstance(ranks, list):
                raise serializers.ValidationError({"ranks": "list 여야 합니다"})
            for idx, rank in enumerate(ranks):
                if not isinstance(rank, dict) or "key" not in rank:
                    raise serializers.ValidationError(
                        {"ranks": f"index {idx} 형식 오류"}
                    )
                if rank["key"] not in WinnerChoices.VALUES:
                    raise serializers.ValidationError(
                        {
                            "ranks": (
                                f"index {idx} key='{rank['key']}' 는 "
                                f"{WinnerChoices.VALUES} 중 하나여야 합니다"
                            )
                        }
                    )
        return result

    def create(self, validated_data):
        answers = validated_data.get("answers", {}) or {}
        auto = validated_data.get("auto_selected", {}) or {}
        result = validated_data.get("result", {}) or {}
        snapshot = validated_data.get("benefit_amounts_snapshot", {}) or {}

        internet_ids = answers.get("internet") or []
        device_id = answers.get("device_id")

        flat = {
            "funnel_variant": validated_data.get("funnel_variant", "control"),
            "copy_variant": validated_data.get("copy_variant", "v2"),
            "pricing_path": validated_data.get("pricing_path", "selfbuy_v1"),
            "ga4_client_id": validated_data.get("ga4_client_id") or None,
            # answers
            "carrier": answers.get("carrier"),
            "keep_carrier": answers.get("keep_carrier"),
            "device_id": device_id,
            "device_name": answers.get("device_name"),
            "family_bundle": answers.get("family_bundle"),
            "gift": answers.get("gift"),
            "data_usage": answers.get("data_usage"),
            "plan_price_mvno": answers.get("plan_price_mvno"),
            "plan_price_mno": answers.get("plan_price_mno"),
            "card": answers.get("card"),
            "card_spend": answers.get("card_spend"),
            "card_history": answers.get("card_history") or [],
            "internet_new": answers.get("internet_new"),
            # auto
            "device_price": auto.get("device_price", 0) or 0,
            "public_subsidy": auto.get("public_subsidy", 0) or 0,
            "additional_discount": auto.get("additional_discount", 0) or 0,
            "skt_plan_id": auto.get("skt_plan_id"),
            "skt_plan_monthly_fee": auto.get("skt_plan_monthly_fee", 0) or 0,
            "static_card_recommended": auto.get("static_card_recommended"),
            "static_card_monthly": auto.get("static_card_monthly", 0) or 0,
            "static_card_total24": auto.get("static_card_total24", 0) or 0,
            "partner_card_slots": auto.get("partner_card_slots") or [],
            "partner_card_monthly": auto.get("partner_card_monthly", 0) or 0,
            "partner_card_total24": auto.get("partner_card_total24", 0) or 0,
            "final_card_total24": auto.get("final_card_total24", 0) or 0,
            "final_card_monthly": auto.get("final_card_monthly", 0) or 0,
            "family_bundle_eligible": bool(auto.get("family_bundle_eligible")),
            "gift_eligible": bool(auto.get("gift_eligible")),
            "internet_new_eligible": bool(auto.get("internet_new_eligible")),
            # result
            "pio_total": result.get("pio_total", 0) or 0,
            "selfbuy_total": result.get("selfbuy_total", 0) or 0,
            "official_total": result.get("official_total", 0) or 0,
            "benefit_only": result.get("benefit_only", 0) or 0,
            "total_saving": result.get("total_saving", 0) or 0,
            "official_vs_pio": result.get("official_vs_pio", 0) or 0,
            "winner": result.get("winner"),
            "ranks": result.get("ranks") or [],
            "benefit_amounts_snapshot": snapshot,
        }

        instance = CalculatorSession.objects.create(**flat)

        if internet_ids:
            carriers_qs = InternetCarrier.objects.filter(id__in=internet_ids)
            instance.internet_carriers.set(carriers_qs)

        return instance


class CalculatorSessionPatchSerializer(serializers.Serializer):
    contact_channel = serializers.ChoiceField(
        choices=ContactChannelChoices.CHOICES, required=False
    )
    submitted_name = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    submitted_contact = serializers.CharField(
        max_length=20, required=False, allow_null=True, allow_blank=True
    )
    copy_variant_v3 = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    name_field_omitted = serializers.BooleanField(required=False)

    def validate(self, attrs):
        ch = attrs.get("contact_channel")
        if ch == ContactChannelChoices.PHONE:
            for key in ("submitted_name", "submitted_contact"):
                value = attrs.get(key)
                if value == "":
                    attrs[key] = None
                if not attrs.get(key):
                    raise serializers.ValidationError(
                        {key: "phone 분기에서 필수 (빈 문자열 포함 거부)"}
                    )
        elif ch == ContactChannelChoices.KAKAO:
            attrs.pop("submitted_name", None)
            attrs.pop("submitted_contact", None)
        return attrs


class CalculatorSessionDetailSerializer(serializers.ModelSerializer):
    """
    GET / PATCH 응답 공통.

    `applied` 는 PATCH context 에 'applied' 키가 주입된 경우에만 응답에
    포함된다 (Critic merge-gate #2: GET 시 applied: null 노출 차단).
    """

    answers = serializers.SerializerMethodField()
    auto_selected = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()
    internet_carrier_ids = serializers.SerializerMethodField()

    class Meta:
        model = CalculatorSession
        fields = (
            "id",
            "funnel_variant",
            "copy_variant",
            "pricing_path",
            "contact_channel",
            "copy_variant_v3",
            "name_field_omitted",
            "answers",
            "auto_selected",
            "result",
            "benefit_amounts_snapshot",
            "submitted_name",
            "submitted_contact",
            "ga4_client_id",
            "internet_carrier_ids",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "applied" in self.context:
            data["applied"] = self.context["applied"]
        return data

    def get_internet_carrier_ids(self, obj):
        return list(obj.internet_carriers.values_list("id", flat=True))

    def get_answers(self, obj):
        return {
            "carrier": obj.carrier,
            "keep_carrier": obj.keep_carrier,
            "internet": self.get_internet_carrier_ids(obj),
            "device_id": obj.device_id,
            "device_name": obj.device_name,
            "family_bundle": obj.family_bundle,
            "gift": obj.gift,
            "data_usage": obj.data_usage,
            "plan_price_mvno": obj.plan_price_mvno,
            "plan_price_mno": obj.plan_price_mno,
            "card": obj.card,
            "card_spend": obj.card_spend,
            "card_history": obj.card_history,
            "internet_new": obj.internet_new,
        }

    def get_auto_selected(self, obj):
        return {
            "device_price": obj.device_price,
            "public_subsidy": obj.public_subsidy,
            "additional_discount": obj.additional_discount,
            "skt_plan_id": obj.skt_plan_id,
            "skt_plan_monthly_fee": obj.skt_plan_monthly_fee,
            "static_card_recommended": obj.static_card_recommended,
            "static_card_monthly": obj.static_card_monthly,
            "static_card_total24": obj.static_card_total24,
            "partner_card_slots": obj.partner_card_slots,
            "partner_card_monthly": obj.partner_card_monthly,
            "partner_card_total24": obj.partner_card_total24,
            "final_card_total24": obj.final_card_total24,
            "final_card_monthly": obj.final_card_monthly,
            "family_bundle_eligible": obj.family_bundle_eligible,
            "gift_eligible": obj.gift_eligible,
            "internet_new_eligible": obj.internet_new_eligible,
        }

    def get_result(self, obj):
        return {
            "pio_total": obj.pio_total,
            "selfbuy_total": obj.selfbuy_total,
            "official_total": obj.official_total,
            "benefit_only": obj.benefit_only,
            "total_saving": obj.total_saving,
            "official_vs_pio": obj.official_vs_pio,
            "winner": obj.winner,
            "ranks": obj.ranks,
        }


class CustomerIdentityCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerIdentity
        fields = ("source", "pre_name", "pre_contact")
