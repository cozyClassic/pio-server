from rest_framework import serializers

from phone.models import (
    FAQ,
    Notice,
    Banner,
    Review,
    PolicyDocument,
    PartnerCard,
    CardBenefit,
    Event,
    Product,
)


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["category", "id", "question", "answer", "created_at"]
        read_only_fields = ["category", "id", "question", "answer", "created_at"]


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ["id", "title", "content", "created_at"]
        read_only_fields = ["id", "title", "content", "created_at"]


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ["id", "link", "title", "image_pc", "image_mobile", "location"]
        read_only_fields = [
            "id",
            "link",
            "title",
            "image_pc",
            "image_mobile",
            "location",
        ]


class ReviewCreateSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Review
        fields = [
            "product_id",
            "customer_name",
            "rating",
            "comment",
            "image",
        ]

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate_product_id(self, value):
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise serializers.ValidationError("Invalid product_id format.")

        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError("Product does not exist.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "customer_name",
            "rating",
            "comment",
            "created_at",
            "image",
            "product",
        ]
        read_only_fields = ["id", "created_at", "images"]

    def get_product(self, obj):
        if obj.product is None or obj.product.deleted_at is not None:
            return None
        return {
            "id": obj.product.id,
            "name": obj.product.name,
            "image": (
                obj.product.images.all()[0].image.url
                if obj.product.images.all()
                else None
            ),
        }


class PolicyDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyDocument
        fields = ["id", "document_type", "content", "effective_date"]
        read_only_fields = ["id", "document_type", "content", "effective_date"]


class CardBenefitSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardBenefit
        fields = ["condition", "benefit_price", "is_optional"]
        read_only_fields = ["id", "title", "description"]


class PartnerCardSerializer(serializers.ModelSerializer):
    card_benefits = CardBenefitSimpleSerializer(many=True, read_only=True)

    class Meta:
        model = PartnerCard
        fields = [
            "id",
            "name",
            "carrier",
            "benefit_type",
            "image",
            "link",
            "card_benefits",
            "contact",
        ]
        read_only_fields = [
            "id",
            "name",
            "carrier",
            "benefit_type",
            "image",
            "link",
            "sort_order",
            "card_benefits",
            "contact",
        ]


class EventSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"
