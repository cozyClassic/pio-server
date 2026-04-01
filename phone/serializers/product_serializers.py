from rest_framework import serializers

from phone.models import (
    Product,
    ProductOption,
    ProductSeries,
    DecoratorTag,
)
from phone.constants import CarrierChoices, CREDIT_CHECK_AGREE_LINK
from phoneinone_server.settings import AWS_CLOUDFRONT_DOMAIN


class ProductOptionSimpleSerializer(serializers.ModelSerializer):
    carrier = serializers.SerializerMethodField()
    is_best = serializers.BooleanField(default=False)
    device_name = serializers.SerializerMethodField()
    storage_capacity = serializers.SerializerMethodField()

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
            "monthly_payment",
            "plan_id",
            "storage_capacity",
        ]

    def get_carrier(self, obj):
        return obj.plan.carrier

    def get_device_name(self, obj):
        return obj.product.device.model_name

    def get_storage_capacity(self, obj):
        return obj.device_variant.storage_capacity


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
        return (
            {
                "name": obj.product_series.name,
                "id": obj.product_series.id,
                "sort_order": obj.product_series.sort_order,
            }
            if obj.product_series
            else None
        )

    def get_options(self, obj):
        options = obj.options.all()
        in_stock_by_device = self.context.get("in_stock_by_device", {})
        in_stock_pairs = in_stock_by_device.get(obj.device_id, set())
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
            if (
                in_stock_pairs
                and (carrier, option.device_variant.storage_capacity)
                not in in_stock_pairs
            ):
                continue

            current = best_options[carrier]

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
            ProductOptionSimpleSerializer(
                [op for op in best_options.values() if op is not None], many=True
            ).data
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    best_options = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "options",
            "device",
            "reviews",
            "images",
            "description",
            "best_options",
            "stock",
        ]

    def _get_in_stock_pairs(self):
        """재고가 있는 (carrier, storage_capacity) 조합 set을 반환"""
        inventories = self.context.get("inventories", [])
        in_stock = set()
        for inv in inventories:
            if inv.count > 0:
                in_stock.add(
                    (inv.dealership.carrier, inv.device_variant.storage_capacity)
                )
        return in_stock

    def get_options(self, obj):
        options = obj.options.all()
        device_variants = {
            dv.id: {
                "storage_capacity": dv.storage_capacity,
            }
            for dv in obj.device.variants.all()
        }
        in_stock_pairs = self._get_in_stock_pairs()
        result = {}

        for op in options:
            dv_id = op.device_variant_id
            storage_capacity = device_variants[dv_id]["storage_capacity"]
            plan = op.plan
            if (
                in_stock_pairs
                and (plan.carrier, storage_capacity) not in in_stock_pairs
            ):
                continue
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
                ] = {}
            result[storage_capacity][plan.carrier][op.contract_type][op.discount_type][
                op.plan_id
            ] = {
                "option_id": op.id,
                "device_price": op.device_price,
                "final_price": op.final_price,
                "additional_discount": op.additional_discount,
                "subsidy_amount": op.subsidy_amount,
                "subsidy_amount_mnp": op.subsidy_amount_mnp,
                "plan_id": op.plan_id,
                "name": op.plan.name,
                "price": op.plan.price,
                "data_allowance": op.plan.data_allowance,
                "call_allowance": op.plan.call_allowance,
                "sms_allowance": op.plan.sms_allowance,
                "description": op.plan.description,
                "official_contract_link": (
                    op.official_contract_link.link
                    if op.official_contract_link
                    else None
                ),
                "credit_check_agree_link": CREDIT_CHECK_AGREE_LINK[op.plan.carrier],
            }

        return result

    def get_device(self, obj):
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

        for color in obj.device.colors.all():
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

    def get_best_options(self, obj):
        result = {
            "device_price": {
                CarrierChoices.SK: None,
                CarrierChoices.KT: None,
                CarrierChoices.LG: None,
            },
            "monthly_payment": {
                CarrierChoices.SK: None,
                CarrierChoices.KT: None,
                CarrierChoices.LG: None,
            },
        }

        options = obj.options.all()
        in_stock_pairs = self._get_in_stock_pairs()
        # 통신사별 재고 있는 최저가 variant 찾기
        variants_by_price = sorted(
            obj.device.variants.all(), key=lambda x: x.device_price
        )
        carrier_target_dv_ids = {}
        if in_stock_pairs:
            for carrier in [CarrierChoices.SK, CarrierChoices.KT, CarrierChoices.LG]:
                for v in variants_by_price:
                    if (carrier, v.storage_capacity) in in_stock_pairs:
                        carrier_target_dv_ids[carrier] = v.id
                        break
        else:
            default_dv_id = variants_by_price[0].id if variants_by_price else None
            for carrier in [CarrierChoices.SK, CarrierChoices.KT, CarrierChoices.LG]:
                carrier_target_dv_ids[carrier] = default_dv_id
        for op in [
            opt
            for opt in options
            if carrier_target_dv_ids.get(opt.plan.carrier) == opt.device_variant_id
        ]:
            carrier = op.plan.carrier
            curr_device_price_option = result["device_price"][carrier]
            curr_monthly_payment_option = result["monthly_payment"][carrier]
            if (
                curr_device_price_option is None
                or op.six_month_total_gongsi
                < curr_device_price_option.six_month_total_gongsi
            ) or (
                op.six_month_total_gongsi
                == curr_device_price_option.six_month_total_gongsi
                and op.monthly_payment < curr_device_price_option.monthly_payment
            ):
                result["device_price"][carrier] = op

            if (
                curr_monthly_payment_option is None
                or op.monthly_payment < curr_monthly_payment_option.monthly_payment
            ) or (
                op.monthly_payment == curr_monthly_payment_option.monthly_payment
                and op.six_month_total_gongsi
                < curr_monthly_payment_option.six_month_total_gongsi
            ):
                result["monthly_payment"][carrier] = op

        return {
            "device_price": {
                carrier: ProductOptionSimpleSerializer(op).data
                for carrier, op in result["device_price"].items()
                if op is not None
            },
            "monthly_payment": {
                carrier: ProductOptionSimpleSerializer(op).data
                for carrier, op in result["monthly_payment"].items()
                if op is not None
            },
        }

    def get_stock(self, obj):
        LOW_STOCK_THRESHOLD = 5
        inventories = self.context.get("inventories", [])

        result = {}
        for inv in inventories:
            carrier = inv.dealership.carrier
            storage = inv.device_variant.storage_capacity
            color_code = inv.device_color.color_code

            if carrier not in result:
                result[carrier] = {}
            if storage not in result[carrier]:
                result[carrier][storage] = {}

            if inv.count <= 0:
                status = "out_of_stock"
            elif inv.count <= LOW_STOCK_THRESHOLD:
                status = "low_stock"
            else:
                status = "in_stock"

            result[carrier][storage][color_code] = status

        return result


class ProductSimpleSerializer(serializers.ModelSerializer):
    model_name = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "model_name", "thumbnail", "images"]
        read_only_fields = ["id", "model_name", "thumbnail", "images"]

    def get_model_name(self, obj):
        return obj.device.model_name

    def get_thumbnail(self, obj):
        return obj.images.all()[0].image.url if obj.images.all() else None

    def get_images(self, obj):
        return [image.image.url for image in obj.images.all()]


class ProductOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductOption
        fields = [
            "id",
            "plan_id",
            "device_variant_id",
            "contract_type",
            "discount_type",
            "additional_discount",
            "subsidy_amount",
            "subsidy_amount_mnp",
        ]
        read_only_fields = [
            "id",
            "id",
            "plan_id",
            "device_variant_id",
            "contract_type",
            "discount_type",
            "additional_discount",
            "subsidy_amount",
            "subsidy_amount_mnp",
        ]


class ProductSeriesSerializer(serializers.ModelSerializer):
    products = ProductSimpleSerializer(
        many=True, read_only=True, source="productseries"
    )

    class Meta:
        model = ProductSeries
        fields = ["id", "name", "products"]
        read_only_fields = ["id", "name", "products"]
