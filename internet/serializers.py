from .models import *
from rest_framework import serializers
from typing import List
from typing import DefaultDict


class InternetCarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternetCarrier
        fields = "__all__"


class BCSerializer(serializers.BaseSerializer):
    @staticmethod
    def get_bundle_discount_amount(bundle_condition: BundleCondition):
        bundle_discount: List[BundleDiscount] = bundle_condition.bundle_discounts.all()
        total_month_discount = sum(
            [b.discount_amount for b in bundle_discount if b.discount_type != "Mobile"]
        )
        return total_month_discount

    @staticmethod
    def get_mobile_discount(bundle_condition: BundleCondition):
        bundle_discount: List[BundleDiscount] = bundle_condition.bundle_discounts.all()
        total_month_discount = sum(
            [b.discount_amount for b in bundle_discount if b.discount_type == "Mobile"]
        )
        return total_month_discount

    @classmethod
    def get_IT(
        cls,
        bundle_condition: BundleCondition,
        installation_fee_dict,
    ):
        if len(bundle_condition.bundle_promotions.all()) == 0:
            return {}

        promotion = bundle_condition.bundle_promotions.all()[0]
        month_discount = cls.get_bundle_discount_amount(bundle_condition)

        return {
            "bundle_condition_id": bundle_condition.id,
            "month_discount": month_discount,
            "cash": promotion.cash_amount,
            "coupon": promotion.coupon_amount,
            "installation_fee": installation_fee_dict[bundle_condition.carrier_id][
                "IT"
            ],
            "mobile_discount": cls.get_mobile_discount(bundle_condition),
        }

    @classmethod
    def get_I(
        cls,
        bundle_condition: BundleCondition,
        installation_fee_dict,
    ):
        if len(bundle_condition.bundle_promotions.all()) == 0:
            return {}

        promotion = bundle_condition.bundle_promotions.all()[0]
        month_discount = cls.get_bundle_discount_amount(bundle_condition)

        return {
            "bundle_condition_id": bundle_condition.id,
            "month_discount": month_discount,
            "cash": promotion.cash_amount,
            "coupon": promotion.coupon_amount,
            "installation_fee": installation_fee_dict[bundle_condition.carrier_id]["I"],
            "mobile_discount": cls.get_mobile_discount(bundle_condition),
        }

    @classmethod
    def get_IM(
        cls,
        bundle_condition: BundleCondition,
        installation_fee_dict,
    ):
        if len(bundle_condition.bundle_promotions.all()) == 0:
            return {}

        promotion = bundle_condition.bundle_promotions.all()[0]
        month_discount = cls.get_bundle_discount_amount(bundle_condition)
        return {
            "bundle_condition_id": bundle_condition.id,
            "month_discount": month_discount,
            "cash": promotion.cash_amount,
            "coupon": promotion.coupon_amount,
            "installation_fee": installation_fee_dict[bundle_condition.carrier_id]["I"],
            "mobile_discount": cls.get_mobile_discount(bundle_condition),
        }

    @classmethod
    def get_IMT(
        cls,
        bundle_condition: BundleCondition,
        installation_fee_dict,
    ):
        if len(bundle_condition.bundle_promotions.all()) == 0:
            return {}

        promotion = bundle_condition.bundle_promotions.all()[0]
        month_discount = cls.get_bundle_discount_amount(bundle_condition)

        return {
            "bundle_condition_id": bundle_condition.id,
            "month_discount": month_discount,
            "cash": promotion.cash_amount,
            "coupon": promotion.coupon_amount,
            "installation_fee": installation_fee_dict[bundle_condition.carrier_id][
                "IT"
            ],
            "mobile_discount": cls.get_mobile_discount(bundle_condition),
        }


class SimpleInternetPlanSerializer(serializers.ModelSerializer):
    wifi_fee = serializers.SerializerMethodField()

    def get_wifi_fee(self, obj):
        return obj.carrier.wifi_router_rental_price_per_month

    class Meta:
        model = InternetPlan
        fields = [
            "id",
            "name",
            "speed",
            "description",
            "internet_price_per_month",
            "internet_contract_discount",
            "is_wifi_router_free",
            "is_wifi_router_selectable",
            "wifi_fee",
        ]


class SimpleTVPlanSerializer(serializers.ModelSerializer):
    tv_box_fee = serializers.SerializerMethodField()

    def get_tv_box_fee(self, obj):
        return obj.carrier.tv_settop_box_rental_price_per_month

    class Meta:
        model = TVPlan
        fields = [
            "id",
            "name",
            "channel_count",
            "description",
            "tv_price_per_month",
            "tv_contract_discount",
            "is_settop_box_free",
            "is_settop_box_selectable",
            "tv_box_fee",
        ]


class InternetPlanSerializer(serializers.Serializer):
    def to_representation(self, instance):
        # 프론트엔드에서 사용할 API 형식?
        # 1. 인터넷 목록 별도 필요- 기본정보 + 와이파이 렌탈비 여부 및 가격 + 설치비
        # 2. tv 목록 별도 필요 - 기본정보
        # 3. 인터넷 목록 + tv = (Internet_ID, TV_ID) 조합별 key 사용
        # 4. 핸드폰 연결 가능 여부 -> combine을 보고 확인하세요!?
        # [carrier] : [internet_plan] : [I] / [IT] / [IM] / [IMT]
        # 4. 각 조건별 가격 정보 + 할인 정보
        # 5. 기본으로 tv 상품 목록도 나와있어야해서, carrier별 tv_plan도 별도로 불러와야 할 듯

        #  internet_plans: []
        #  INTERNET_PLAN = { id,  }
        #  combines: { "I": {}, "IT": {}, "IM": {}, "IMT": {} }
        #    KEY: "internet_plan_id,tv_plan_id_mobile_type"
        #    VALUE: { bundle_discount_id, price_per_month, cash, coupon, installation_fee, internet_price, tv_price }

        carriers = InternetCarrier.objects.all()
        carrier_dict = {c.id: c.name for c in carriers}
        result = {
            carrier.name: {
                "name": carrier.name,
                "logo": carrier.logo.url,
                "internet_plans": [],
                "tv_plans": [],
                "combines": {},
            }
            for carrier in carriers
        }
        tv_plans = TVPlan.objects.select_related("carrier").order_by(
            "tv_price_per_month"
        )

        # setup base tv plan list
        for tv_plan in tv_plans:
            carrier_name = carrier_dict[tv_plan.carrier_id]
            result[carrier_name]["tv_plans"].append(
                SimpleTVPlanSerializer(tv_plan).data
            )

        # setup base internet plan list
        for internet_plan in instance:
            result[internet_plan.carrier.name]["internet_plans"].append(
                SimpleInternetPlanSerializer(internet_plan).data
            )

        # setup installation dict
        installation_fee_dict = DefaultDict(dict)
        installation_fees = InstallationOption.objects.all()
        for install_fee in installation_fees:
            installation_fee_dict[install_fee.carrier_id][
                install_fee.installation_type
            ] = install_fee.installation_fee

        for plan in instance:
            #     # 이것도 아니고.. plan 하나에 I, IT, IM, IMT 여러개 다 될 수 있음..
            #     # -> 하나에 대해서 각각의 serializer를 돌려서 결과를 넣어줘야 함
            #     # 다만, 해당 serializer에서 조건에 맞는 경우에만 결과를 반환하도록 해야 함
            combines = result[carrier_dict[plan.carrier_id]]["combines"]
            for bc in plan.bundle_conditions.all():
                key = f"{plan.id},{bc.mobile_type},{bc.tv_plan_id}".replace("None", "")
                if bc.tv_plan is None and bc.mobile_type == "None":
                    combines[key] = BCSerializer.get_I(bc, installation_fee_dict)
                elif bc.tv_plan is not None and bc.mobile_type == "None":
                    combines[key] = BCSerializer.get_IT(bc, installation_fee_dict)
                elif bc.tv_plan is None and bc.mobile_type in ["MNO", "MVNO"]:
                    combines[key] = BCSerializer.get_IM(bc, installation_fee_dict)
                elif bc.tv_plan is not None and bc.mobile_type in ["MNO", "MVNO"]:
                    combines[key] = BCSerializer.get_IMT(bc, installation_fee_dict)

        return result
