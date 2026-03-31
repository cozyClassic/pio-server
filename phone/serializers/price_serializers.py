from rest_framework import serializers

from phone.models import PriceNotificationRequest, Product


class PriceNotificationRequestSerializer(serializers.ModelSerializer):
    created_at = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()

    def get_created_at(self, obj):
        return obj.created_at.strftime("%Y-%m-%d")

    def get_product_name(self, obj):
        return obj.product.name if obj.product else ""

    class Meta:
        model = PriceNotificationRequest
        fields = [
            "id",
            "customer_phone",
            "product_id",
            "product_name",
            "target_price",
            "prev_carrier",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "product_name",
        ]


class PriceNotificationRequestCreateSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = PriceNotificationRequest
        fields = [
            "customer_phone",
            "product_id",
            "prev_carrier",
            "target_price",
            "channel_talk_user_id",
        ]

    def validate_channel_talk_user_id(self, value):
        if value is None:
            raise serializers.ValidationError("채널톡 사용자 ID는 null일 수 없습니다.")
        return value

    def validate_customer_phone(self, value):
        import re

        if not re.match(r"^01[0-9]{8,9}$", value):
            raise serializers.ValidationError("올바른 전화번호 형식이 아닙니다.")
        return value

    def validate_target_price(self, value):
        if value < 0:
            raise serializers.ValidationError("목표 가격은 0 이상이어야 합니다.")
        return value

    def validate_product_id(self, value):
        if not Product.objects.filter(
            id=value, deleted_at__isnull=True, is_active=True
        ).exists():
            raise serializers.ValidationError("존재하지 않거나 비활성화된 상품입니다.")
        return value

    def create(self, validated_data):
        product_id = validated_data.pop("product_id")
        return PriceNotificationRequest.objects.create(
            product_id=product_id, **validated_data
        )


class PriceNotificationRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceNotificationRequest
        fields = [
            "target_price",
        ]
