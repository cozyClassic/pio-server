from rest_framework import serializers

from phone.models import Device, DeviceVariant, Plan
from phoneinone_server.settings import AWS_CLOUDFRONT_DOMAIN


class DeviceVairantSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceVariant
        fields = ["id", "storage_capacity", "device_price"]
        read_only_fields = ["id", "storage_capacity", "device_price"]


class DeviceSerializer(serializers.ModelSerializer):
    variants = DeviceVairantSimpleSerializer(many=True, read_only=True)
    first_image_url = serializers.SerializerMethodField(read_only=True, allow_null=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "model_name",
            "brand",
            "variants",
            "series",
            "first_image_url",
        ]
        read_only_fields = [
            "id",
            "model_name",
            "brand",
            "variants",
            "series",
            "first_image_url",
        ]

    def get_first_image_url(self, obj):
        return f"https://{AWS_CLOUDFRONT_DOMAIN}/{obj.first_image_url}"


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "carrier",
            "price",
            "data_allowance",
            "call_allowance",
            "sms_allowance",
            "description",
        ]
        read_only_fields = [
            "id",
            "name",
            "carrier",
            "price",
            "data_allowance",
            "call_allowance",
            "sms_allowance",
            "description",
        ]
