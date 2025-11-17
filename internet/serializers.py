from .models import *
from rest_framework import serializers
from typing import List


class InternetCarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternetCarrier
        fields = "__all__"


"""
1. InternetPlan, TvPlan, BundleCondition, BundleDiscount, BundlePromotion을 모두 호출한다.
2. 각각 아래의 조건에 대한 Serializer를 만든다.
 - I, I + M, I + T, I + M + T
 - 설치비용 옵션도 호출해서 추가한다. (I=I+M, I+T=I+M+T)
3. 각각의 Serializer에서는, 각각의 condition의 가격 조건에 맞는 discount와 promotion을 불러온다.


{
"selectable": ["I", "IT", "IM", "IMT"],
"I": ...,
 "IT": ...,
 "IM": ...,
 "IMT": ...
}
"""


class I_Serializer(serializers.BaseSerializer):
    def to_representation(self, instance: InternetPlan):
        price = instance.internet_price_per_month - instance.internet_contract_discount
        if not instance.is_wifi_router_selectable and not instance.is_wifi_router_free:
            price += instance.carrier.wifi_router_rental_price_per_month

        bundle_discount: List[BundleDiscount] = (
            instance.bundle_coditions.bundle_discounts
        )
        bundle_promotion: BundlePromotion = instance.bundle_coditions.bundle_promotions[
            0
        ]
        total_month_discount = sum([b.discount_amount for b in bundle_discount])

        return {
            "price_per_month": price - total_month_discount,
            "name": instance.name,
            "speed": instance.speed,
            "description": instance.description,
            "is_wifi_router_free": instance.is_wifi_router_free,
            "is_wifi_router_selectable": instance.is_wifi_router_selectable,
            "cash": bundle_promotion.cash_amount,
            "coupon": bundle_promotion.coupon_amount,
        }


class InternetPlanSerializer(serializers.BaseSerializer):
    def to_representation(self, instance):

        return super().to_representation(instance)
