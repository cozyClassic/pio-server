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


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ["id", "image"]
        read_only_fields = ["id", "image"]


class ProductDetailSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "options",
            "device",
            "reviews",
            "images",
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
                    "plan_id": plan.id,
                    "plan_name": plan.name,
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
                "images": [
                    {
                        "id": img.id,
                        "image": img.image.url,
                        "description": img.description,
                    }
                    for img in review.images.all()
                ],
            }
            for review in reviews
        ]

    def get_images(self, obj):
        imgs = obj.images.all().order_by("sort_order")
        return [img.image.url for img in imgs]


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
            "password",
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
        fields = ["id", "title", "image", "created_at"]
        read_only_fields = ["id", "title", "image", "created_at"]


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ["id", "image"]


class ReviewSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    image_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True)
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
            "images",
            "image_ids",
        ]
        read_only_fields = ["id", "created_at", "images"]

    def create(self, validated_data):
        validated_data.pop("images", None)
        review_image_ids = validated_data.pop("image_ids", [])
        review = super().create(validated_data)
        ReviewImage.objects.filter(id__in=review_image_ids).update(review=review)
        return review

    def get_images(self, obj):
        return [{"id": img.id, "url": img.image.url} for img in obj.images.all()]
