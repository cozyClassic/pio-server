from rest_framework import serializers

from phone.models import Order, Plan
from phoneinone_server.settings import AWS_CLOUDFRONT_DOMAIN

from .product_serializers import ProductSimpleSerializer


class PlanSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name", "price", "carrier"]


class OrderSerializer(serializers.ModelSerializer):
    plan = PlanSimpleSerializer()
    product = ProductSimpleSerializer()
    device_color = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "customer_phone",
            "customer_phone2",
            "customer_email",
            "product",
            "plan",
            "contract_type",
            "device_price",
            "plan_monthly_fee",
            "subsidy_standard",
            "subsidy_mnp",
            "final_price",
            "discount_type",
            "monthly_discount",
            "additional_discount",
            "storage_capacity",
            "device_color",
            "customer_memo",
            "status",
            "created_at",
            "updated_at",
            "shipping_method",
            "shipping_address",
            "shipping_address_detail",
            "zipcode",
            "shipping_number",
            "payment_period",
            "customer_birth",
        ]

        read_only_fields = [
            "id",
            "status",
            "created_at",
            "shipping_method",
            "shipping_number",
        ]

    def get_device_color(self, obj):
        return {
            "color": obj.color,
            "color_code": obj.color_code,
            "image": f"https://{AWS_CLOUDFRONT_DOMAIN}/{obj.image}",
        }


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "customer_name",
            "customer_phone",
            "customer_phone2",
            "customer_email",
            "customer_birth",
            "product_id",
            "plan_id",
            "contract_type",
            "device_price",
            "plan_monthly_fee",
            "subsidy_standard",
            "subsidy_mnp",
            "final_price",
            "discount_type",
            "monthly_discount",
            "additional_discount",
            "storage_capacity",
            "color",
            "customer_memo",
            "shipping_address",
            "shipping_address_detail",
            "zipcode",
            "payment_period",
            "ga4_id",
            "prev_carrier",
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    plan = PlanSimpleSerializer()
    product = ProductSimpleSerializer()
    device_color = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "customer_phone",
            "customer_phone2",
            "customer_email",
            "plan",
            "product",
            "contract_type",
            "device_price",
            "plan_monthly_fee",
            "subsidy_standard",
            "subsidy_mnp",
            "final_price",
            "discount_type",
            "monthly_discount",
            "additional_discount",
            "storage_capacity",
            "device_color",
            "customer_memo",
            "status",
            "created_at",
            "updated_at",
            "shipping_method",
            "shipping_address",
            "shipping_address_detail",
            "zipcode",
            "shipping_number",
            "payment_period",
            "customer_birth",
            "credit_check_agreements",
        ]

    def get_device_color(self, obj):
        return {
            "color": obj.color,
            "color_code": obj.color_code,
            "image": obj.image,
        }
