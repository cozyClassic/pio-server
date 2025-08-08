from rest_framework import serializers

from .models import *


class ProductListSerializer(serializers.ModelSerializer):
    best_price_option = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "image_main", "best_price_option"]

    def get_best_price_option(self, obj):
        option = {
            "device_price": obj.best_price_option.device_variant.price,
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

    class Meta:
        model = Product
        fields = [
            "options",
            "device",
            "reviews",
        ]

    def get_options(self, obj):
        options = obj.options.all()
        device_variants = {
            dv.id: {
                "capacity": dv.capacity,
            }
            for dv in obj.device.variants.all()
        }
        result = {}

        for op in options:
            dv_id = op.device_variant_id
            capacity = device_variants[dv_id]["capacity"]
            plan = op.plan
            if capacity not in result:
                result[capacity] = {}
            if plan.carrier not in result[capacity]:
                result[capacity][plan.carrier] = {}
            if op.contract_type not in result[capacity][plan.carrier]:
                result[capacity][plan.carrier][op.contract_type] = {}
            if op.discount_type not in result[capacity][plan.carrier][op.contract_type]:
                result[capacity][plan.carrier][op.contract_type][op.discount_type] = []
            result[capacity][plan.carrier][op.contract_type][op.discount_type].append(
                {
                    "option_id": op.id,
                    "final_price": op.final_price,
                    "plan_id": plan.id,
                    "plan_name": plan.name,
                    "subsidy_standard": op.subsidy_amount_standard,
                    "subsidy_mnp": op.subsidy_amount_mnp,
                    "additional_discount": op.additional_discount,
                }
            )

        return result

    def get_device(self, obj):
        # device_varaints: [capacity, price]
        # device_colors: {color_name, color_code, [device_color_images]}
        result = {"device_variants": [], "device_colors": []}
        for dv in obj.device.variants.all():
            result["device_variants"].append(
                {
                    "capacity": dv.capacity,
                    "price": dv.price,
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
