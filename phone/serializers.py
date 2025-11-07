from rest_framework import serializers

from .models import *
from .constants import CarrierChoices


class ProductOptionSimpleSerializer(serializers.ModelSerializer):
    carrier = serializers.SerializerMethodField()
    is_best = serializers.BooleanField(default=False)
    device_price = serializers.SerializerMethodField()
    device_name = serializers.SerializerMethodField()

    class Meta:
        model = ProductOption
        fields = [
            "id",
            "final_price",
            "carrier",
            "contract_type",
            "discount_type",
            "is_best",
            "device_price",
            "device_name",
        ]

    def get_carrier(self, obj):
        return obj.plan.carrier

    def get_device_price(self, obj):
        return obj.device_variant.device_price

    def get_device_name(self, obj):
        return obj.product.device.model_name


class DecoratorTagSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecoratorTag
        fields = [
            "name",
            "text_color",
            "tag_color",
        ]


class ProductListSerializer(serializers.ModelSerializer):
    series = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    tags = DecoratorTagSimpleSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "series",
            "is_featured",
            "options",
            "images",
            "tags",
        ]

    def get_images(self, obj):
        return [img.image.url for img in obj.images.all()]

    def get_series(self, obj):
        return obj.product_series.name if obj.product_series else None

    # 통신사별로 단말기 할인이 제일 많이 되는 옵션을 (번호이동, 기기변경)에 따라 보여주기
    def get_options(self, obj):
        options = obj.options.all()
        best_options = {
            CarrierChoices.SK: None,
            CarrierChoices.KT: None,
            CarrierChoices.LG: None,
        }
        best_price = 99999999

        for option in options:
            carrier = option.plan.carrier
            if carrier not in best_options:
                continue

            current = best_options[carrier]

            # 첫 번째 옵션이거나, final_price가 더 낮거나,
            # final_price가 같고 plan.price가 더 낮은 경우
            if (
                current is None
                or option.final_price < current.final_price
                or (
                    option.final_price == current.final_price
                    and option.plan.price < current.plan.price
                )
            ):
                best_options[carrier] = option
                if option.final_price < best_price:
                    best_price = option.final_price

        for carrier, option in best_options.items():
            if option is not None and option.final_price == best_price:
                option.is_best = True

        return list(
            ProductOptionSimpleSerializer(best_options.values(), many=True).data
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    best_option_id = serializers.IntegerField(
        source="best_price_option_id", read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "options",
            "device",
            "reviews",
            "images",
            "best_option_id",
            "description",
        ]

    def get_options(self, obj):
        options = obj.options.all()
        device_variants = {
            dv.id: {
                "storage_capacity": dv.storage_capacity,
            }
            for dv in obj.device.variants.all()
        }
        result = {}

        # discount_type을 안으로 넣고, plan을 위로 올리기
        for op in options:
            dv_id = op.device_variant_id
            storage_capacity = device_variants[dv_id]["storage_capacity"]
            plan = op.plan
            if storage_capacity not in result:
                result[storage_capacity] = {}
            if plan.carrier not in result[storage_capacity]:
                result[storage_capacity][plan.carrier] = {}
            if op.contract_type not in result[storage_capacity][plan.carrier]:
                result[storage_capacity][plan.carrier][op.contract_type] = {}
            if (
                op.plan_id
                not in result[storage_capacity][plan.carrier][op.contract_type]
            ):
                result[storage_capacity][plan.carrier][op.contract_type][
                    op.plan_id
                ] = []
                result[storage_capacity][plan.carrier][op.contract_type][op.plan_id] = {
                    "plan_id": op.plan_id,
                    "name": op.plan.name,
                    "price": op.plan.price,
                    "data_allowance": op.plan.data_allowance,
                    "call_allowance": op.plan.call_allowance,
                    "sms_allowance": op.plan.sms_allowance,
                    "description": op.plan.description,
                }
            if (
                op.discount_type
                not in result[storage_capacity][plan.carrier][op.contract_type][
                    op.plan_id
                ]
            ):
                result[storage_capacity][plan.carrier][op.contract_type][op.plan_id][
                    op.discount_type
                ] = {
                    "option_id": op.id,
                    "final_price": op.final_price,
                    "additional_discount": op.additional_discount,
                    "subsidy_amount": op.subsidy_amount,
                    "subsidy_amount_mnp": op.subsidy_amount_mnp,
                }

        return result

    def get_device(self, obj):
        # device_varaints: [storage_capacity, price]
        # device_colors: {color_name, color_code, [device_color_images]}
        result = {
            "device_variants": [],
            "device_colors": [],
            "model_name": obj.device.model_name,
            "brand": obj.device.brand,
        }

        for dv in obj.device.variants.all():
            result["device_variants"].append(
                {
                    "storage_capacity": dv.storage_capacity,
                    "price": dv.device_price,
                }
            )

        for color in obj.device.colors.all():  # prefetch_related 제거
            result["device_colors"].append(
                {
                    "color": color.color,
                    "color_code": color.color_code,
                    "images": [image.image.url for image in color.images.all()],
                }
            )

        return result

    def get_reviews(self, obj):
        reviews = getattr(obj, "limited_reviews", [])
        return [
            {
                "id": review.id,
                "customer_name": review.customer_name,
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at,
                "image": str(review.image.url) if review.image else "",
            }
            for review in reviews
        ]

    def get_images(self, obj):
        imgs = [img for img in obj.images.all()]
        return [
            {
                "url": img.image.url,
                "type": img.type,
            }
            for img in sorted(imgs, key=lambda x: x.sort_order)
        ]


class ProductSimpleSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "images"]

    def get_images(self, obj):
        return [image.image.url for image in obj.images.all()]


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
            "image": obj.image,
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
        ]

    def get_device_color(self, obj):
        return {
            "color": obj.color,
            "color_code": obj.color_code,
            "image": obj.image,
        }


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
    product_id = serializers.IntegerField(write_only=True)  # 명시적으로 정의

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
        """Rating 값 검증 (1-5 사이)"""
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
        fields = ["id", "title", "thumbnail"]
        read_only_fields = ["id", "title", "thumbnail"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "description"]
        read_only_fields = ["id", "title", "description"]
