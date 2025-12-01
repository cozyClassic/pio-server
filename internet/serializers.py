from .models import *
from rest_framework import serializers
from collections import defaultdict
from typing import List


class InternetCarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternetCarrier
        fields = "__all__"


class BCSerializer(serializers.BaseSerializer):
    @staticmethod
    def get_internet_install_fee(
        bc: BundleCondition,
        installation_fees: dict[str, int],
    ):
        return installation_fees.get("I", 0) - sum(
            [
                bd.discount_amount
                for bd in bc.bundle_discounts.all()
                if bd.discount_type == "Internet Install"
            ]
        )

    @staticmethod
    def get_tv_install_fee(
        bc: BundleCondition,
        installation_fees: dict[str, int],
    ):
        return installation_fees.get("T", 0) - sum(
            [
                bd.discount_amount
                for bd in bc.bundle_discounts.all()
                if bd.discount_type == "TV Install"
            ]
        )

    @staticmethod
    def get_bundle_discount(bundle_condition: BundleCondition):
        bundle_discount: List[BundleDiscount] = bundle_condition.bundle_discounts.all()
        total_month_discount = {
            b.discount_type: b.discount_amount
            for b in bundle_discount
            if b.discount_type not in ("Mobile", "Internet Install", "TV Install")
        }
        return total_month_discount

    @staticmethod
    def get_mobile_discount(bundle_condition: BundleCondition):
        bundle_discount: List[BundleDiscount] = bundle_condition.bundle_discounts.all()
        total_month_discount = sum(
            [b.discount_amount for b in bundle_discount if b.discount_type == "Mobile"]
        )
        return total_month_discount

    @classmethod
    def get_combine(
        cls,
        bundle_condition: BundleCondition,
        installation_fees: dict[str, int],
    ):
        if len(bundle_condition.bundle_promotions.all()) == 0:
            return {}

        promotion = bundle_condition.bundle_promotions.all()[0]
        month_discount = cls.get_bundle_discount(bundle_condition)

        return {
            "bundle_condition_id": bundle_condition.id,
            "discount": {
                "month": month_discount,
                "mobile": cls.get_mobile_discount(bundle_condition),
            },
            "promotion": {
                "cash": promotion.cash_amount,
                "coupon": promotion.coupon_amount,
            },
            "installation_fee": {
                "internet": cls.get_internet_install_fee(
                    bundle_condition, installation_fees
                ),
                "tv": cls.get_tv_install_fee(bundle_condition, installation_fees),
            },
        }


class SimpleInternetPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternetPlan
        fields = [
            "id",
            "name",
            "speed",
            "description",
            "internet_price_per_month",
            "internet_contract_discount",
        ]


class SimpleTVPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = TVPlan
        fields = [
            "id",
            "name",
            "channel_count",
            "description",
            "tv_price_per_month",
            "tv_contract_discount",
        ]


class InternetPlanSerializer(serializers.Serializer):
    def to_representation(self, instance):

        carriers = InternetCarrier.objects.all()
        carrier_dict = {c.id: c.name for c in carriers}
        result = {
            carrier.name: {
                "name": carrier.name,
                "logo": carrier.logo.url,
                "internet_plans": [],
                "tv_plans": [],
                "wifi_options": [],
                "settop_options": [],
                "combines": {},
            }
            for carrier in carriers
        }
        tv_plans = TVPlan.objects.select_related("carrier").order_by(
            "tv_price_per_month"
        )

        for tv_plan in tv_plans:
            result[carrier_dict[tv_plan.carrier_id]]["tv_plans"].append(
                SimpleTVPlanSerializer(tv_plan).data
            )

        wifi_options = WifiOption.objects.all()
        for wifi_option in wifi_options:
            result[carrier_dict[wifi_option.carrier_id]]["wifi_options"].append(
                {
                    "id": wifi_option.id,
                    "name": wifi_option.name,
                    "price_per_month": wifi_option.rental_price_per_month,
                    "description": wifi_option.description,
                }
            )

        settop_options = SettopBoxOption.objects.all()
        for settop_option in settop_options:
            result[carrier_dict[settop_option.carrier_id]]["settop_options"].append(
                {
                    "id": settop_option.id,
                    "name": settop_option.name,
                    "price_per_month": settop_option.rental_price_per_month,
                    "description": settop_option.description,
                }
            )

        for internet_plan in instance:
            result[carrier_dict[internet_plan.carrier_id]]["internet_plans"].append(
                SimpleInternetPlanSerializer(internet_plan).data
            )

        # setup installation dict
        installation_fee_dict = defaultdict(dict)
        installation_fees = InstallationOption.objects.all()
        for install_fee in installation_fees:
            installation_fee_dict[install_fee.carrier_id][
                install_fee.installation_type
            ] = install_fee.installation_fee

        # key_type = internet_id,mobile_type,tv_plan_id,wifi_option_id,settop_box_option_id
        # I, IW, IT, IM, IWT, IWM, IMT, IWMT
        for plan in instance:
            combines = result[carrier_dict[plan.carrier_id]]["combines"]
            for bc in plan.bundle_conditions.all():
                key = f"{plan.id},{bc.mobile_type},{bc.tv_plan_id},{bc.wifi_option_id},{bc.settop_box_option_id}".replace(
                    "None", ""
                )
                combines[key] = BCSerializer.get_combine(
                    bc, installation_fee_dict[plan.carrier_id]
                )

        return result
