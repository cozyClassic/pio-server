from rest_framework import serializers

from .models import *


class ProductListSerializer(serializers.ModelSerializer):
    best_price_option = serializers.SerializerMethodField()
    brand = serializers.CharField(source="device.brand")
    series = serializers.CharField(source="device.series")

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "image_main",
            "best_price_option",
            "brand",
            "series",
            "is_featured",
            "description",
        ]

    def get_best_price_option(self, obj):
        option = {
            "device_price": obj.best_price_option.device_variant.device_price,
            "final_price": obj.best_price_option.final_price,
            "carrier": obj.best_price_option.plan.carrier,
            "plan": obj.best_price_option.plan.name,
            "discount_type": obj.best_price_option.discount_type,
            "contract_type": obj.best_price_option.contract_type,
        }
        return option


class ProductDetailSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    best_option_id = serializers.IntegerField(
        source="best_price_option_id", read_only=True
    )
    model_name = serializers.CharField(source="device.model_name", read_only=True)
    brand = serializers.CharField(source="device.brand", read_only=True)

    class Meta:
        model = Product
        fields = [
            "image_main",
            "options",
            "device",
            "reviews",
            "images",
            "best_option_id",
            "model_name",
            "brand",
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
                op.discount_type
                not in result[storage_capacity][plan.carrier][op.contract_type]
            ):
                result[storage_capacity][plan.carrier][op.contract_type][
                    op.discount_type
                ] = []
            result[storage_capacity][plan.carrier][op.contract_type][
                op.discount_type
            ].append(
                {
                    "option_id": op.id,
                    "final_price": op.final_price,
                    "plan": {
                        "id": op.plan.id,
                        "name": op.plan.name,
                        "price": op.plan.price,
                        "data_allowance": op.plan.data_allowance,
                        "call_allowance": op.plan.call_allowance,
                        "sms_allowance": op.plan.sms_allowance,
                        "description": op.plan.description,
                    },
                    "subsidy_standard": op.subsidy_amount,
                    "subsidy_mnp": op.subsidy_amount_mnp,
                    "additional_discount": op.additional_discount,
                }
            )

        return result

    def get_device(self, obj):
        # device_varaints: [storage_capacity, price]
        # device_colors: {color_name, color_code, [device_color_images]}
        result = {"device_variants": [], "device_colors": []}
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
                "image": str(review.image),
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


class OrderSerializer(serializers.ModelSerializer):
    plan_id = serializers.IntegerField(source="plan.id")
    product_id = serializers.IntegerField(source="product.id")

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "customer_phone",
            "customer_phone2",
            "customer_email",
            "product_id",
            "plan_id",
            "contract_type",
            "device_price",
            "plan_monthly_fee",
            "subsidy_amount",
            "subsidy_amount_mnp",
            "final_price",
            "discount_type",
            "monthly_discount",
            "additional_discount",
            "storage_capacity",
            "color",
            "customer_memo",
            "status",
            "created_at",
            "updated_at",
            "shipping_method",
            "shipping_address",
            "shipping_address_detail",
            "zipcode",
            "shipping_number",
        ]

        read_only_fields = [
            "id",
            "status",
            "created_at",
            "shipping_method",
            "shipping_number",
        ]


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
        fields = ["id", "link", "title", "image_pc", "image_mobile", "created_at"]
        read_only_fields = [
            "id",
            "link",
            "title",
            "image_pc",
            "image_mobile",
            "created_at",
        ]


class ReviewCreateSerializer(serializers.ModelSerializer):
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

    def validate_product(self, value):
        """Product 존재 여부 검증"""
        if not Product.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Product does not exist.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField()

    class Meta:
        model = Review
        fields = [
            "id",
            "product_id",
            "customer_name",
            "rating",
            "comment",
            "created_at",
            "image",
        ]
        read_only_fields = ["id", "created_at", "images"]
