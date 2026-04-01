from django.test import TestCase

from phone.models import (
    Dealership,
    Device,
    DeviceColor,
    DeviceVariant,
    Inventory,
    Plan,
    Product,
    ProductOption,
    ProductSeries,
)
from phone.serializers import ProductDetailSerializer, ProductListSerializer


class InventoryFilterMixin:
    """재고 필터링 테스트를 위한 공통 setUp"""

    def setUp(self):
        self.device = Device.objects.create(model_name="iPhone 16", brand="Apple")
        self.variant_128 = DeviceVariant.objects.create(
            device=self.device, storage_capacity="128", device_price=1200000
        )
        self.variant_256 = DeviceVariant.objects.create(
            device=self.device, storage_capacity="256", device_price=1400000
        )
        self.color = DeviceColor.objects.create(
            device=self.device, color="블랙", color_code="000000"
        )
        self.plan_sk = Plan.objects.create(
            name="5G 에센셜",
            carrier="SK",
            category_1="5G",
            category_2="기본",
            price=55000,
            data_allowance="10GB",
            call_allowance="무제한",
            sms_allowance="무제한",
        )
        self.plan_lg = Plan.objects.create(
            name="5G 스탠다드",
            carrier="LG",
            category_1="5G",
            category_2="기본",
            price=55000,
            data_allowance="10GB",
            call_allowance="무제한",
            sms_allowance="무제한",
        )
        self.series = ProductSeries.objects.create(name="아이폰 16")
        self.product = Product.objects.create(
            name="iPhone 16",
            device=self.device,
            product_series=self.series,
            is_active=True,
        )
        # SK 128GB, SK 256GB, LG 128GB, LG 256GB 옵션 생성
        self.opt_sk_128 = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant_128,
            device_price=1200000,
            plan=self.plan_sk,
            discount_type="선택약정",
            contract_type="기기변경",
            additional_discount=100000,
        )
        self.opt_sk_256 = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant_256,
            device_price=1400000,
            plan=self.plan_sk,
            discount_type="선택약정",
            contract_type="기기변경",
            additional_discount=100000,
        )
        self.opt_lg_128 = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant_128,
            device_price=1200000,
            plan=self.plan_lg,
            discount_type="선택약정",
            contract_type="기기변경",
            additional_discount=100000,
        )
        self.opt_lg_256 = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant_256,
            device_price=1400000,
            plan=self.plan_lg,
            discount_type="선택약정",
            contract_type="기기변경",
            additional_discount=100000,
        )
        # 대리점
        self.dealer_sk = Dealership.objects.create(
            name="SK 대리점", carrier="SK", contact_number="010-0000-0000"
        )
        self.dealer_lg = Dealership.objects.create(
            name="LG 대리점", carrier="LG", contact_number="010-0000-0001"
        )

    def _create_inventory(self, dealer, variant, count):
        return Inventory.objects.create(
            device_variant=variant,
            device_color=self.color,
            dealership=dealer,
            count=count,
        )

    def _get_inventories(self):
        variant_ids = [self.variant_128.id, self.variant_256.id]
        return Inventory.objects.filter(
            device_variant_id__in=variant_ids,
            device_color_id=self.color.id,
        ).select_related("dealership", "device_variant", "device_color")


class ProductDetailInventoryFilterTest(InventoryFilterMixin, TestCase):
    """ProductDetailSerializer 재고 필터링 테스트"""

    def _serialize(self):
        product = (
            Product.objects.filter(id=self.product.id)
            .select_related("device")
            .prefetch_related(
                "device__variants",
                "device__colors",
                "device__colors__images",
                "options__plan",
                "options__device_variant",
                "options__official_contract_link",
                "images",
            )
            .first()
        )
        inventories = self._get_inventories()
        return ProductDetailSerializer(
            product, context={"inventories": inventories}
        ).data

    def test_options_exclude_out_of_stock_carrier_storage(self):
        """재고 없는 (carrier, storage) 조합은 options에서 제거"""
        # SK 128만 재고, LG 256만 재고
        self._create_inventory(self.dealer_sk, self.variant_128, 5)
        self._create_inventory(self.dealer_lg, self.variant_256, 3)

        data = self._serialize()
        options = data["options"]
        # SK는 128만, LG는 256만 있어야 함
        self.assertIn("128", options)
        self.assertIn("SK", options["128"])
        self.assertNotIn("LG", options.get("128", {}))
        self.assertIn("256", options)
        self.assertIn("LG", options["256"])
        self.assertNotIn("SK", options.get("256", {}))

    def test_best_options_per_carrier_variant(self):
        """best_options는 통신사별로 재고 있는 최저가 variant 사용"""
        # SK는 128 재고 있음 → 128 사용, LG는 256만 재고 → 256 사용
        self._create_inventory(self.dealer_sk, self.variant_128, 5)
        self._create_inventory(self.dealer_lg, self.variant_256, 3)

        data = self._serialize()
        best = data["best_options"]
        # SK best는 128GB (device_price=1200000)
        self.assertIn("SK", best["device_price"])
        self.assertEqual(best["device_price"]["SK"]["device_price"], 1200000)
        # LG best는 256GB (device_price=1400000)
        self.assertIn("LG", best["device_price"])
        self.assertEqual(best["device_price"]["LG"]["device_price"], 1400000)

    def test_best_options_excludes_no_stock_carrier(self):
        """전체 용량에 재고가 없는 통신사는 best_options에서 제외"""
        # SK만 재고
        self._create_inventory(self.dealer_sk, self.variant_128, 5)

        data = self._serialize()
        best = data["best_options"]
        self.assertIn("SK", best["device_price"])
        self.assertNotIn("LG", best["device_price"])

    def test_no_inventory_shows_all_options(self):
        """inventory 데이터가 없으면 모든 옵션 표시"""
        data = self._serialize()
        options = data["options"]
        # 모든 조합 존재
        self.assertIn("128", options)
        self.assertIn("256", options)
        self.assertIn("SK", options["128"])
        self.assertIn("LG", options["128"])


class ProductListInventoryFilterTest(InventoryFilterMixin, TestCase):
    """ProductListSerializer 재고 필터링 테스트"""

    def _serialize(self, in_stock_by_device=None):
        product = (
            Product.objects.filter(id=self.product.id)
            .select_related("device", "product_series")
            .prefetch_related(
                "options__plan",
                "options__device_variant",
                "images",
                "tags",
            )
            .first()
        )
        context = {"in_stock_by_device": in_stock_by_device or {}}
        return ProductListSerializer(product, context=context).data

    def _build_in_stock_by_device(self):
        """inventory에서 in_stock_by_device 구축"""
        in_stock = {}
        for inv in self._get_inventories():
            if inv.count > 0:
                did = inv.device_variant.device_id
                if did not in in_stock:
                    in_stock[did] = set()
                in_stock[did].add(
                    (inv.dealership.carrier, inv.device_variant.storage_capacity)
                )
        return in_stock

    def test_list_excludes_no_stock_carrier(self):
        """재고 없는 통신사 옵션은 목록에서 제거"""
        # LG 256만 재고
        self._create_inventory(self.dealer_lg, self.variant_256, 3)
        in_stock = self._build_in_stock_by_device()

        data = self._serialize(in_stock)
        carriers = {opt["carrier"] for opt in data["options"]}
        self.assertIn("LG", carriers)
        self.assertNotIn("SK", carriers)

    def test_list_no_none_options(self):
        """None 옵션이 리스트에 포함되지 않음"""
        self._create_inventory(self.dealer_sk, self.variant_128, 1)
        in_stock = self._build_in_stock_by_device()

        data = self._serialize(in_stock)
        for opt in data["options"]:
            self.assertIsNotNone(opt["final_price"])

    def test_list_no_inventory_shows_all(self):
        """inventory 데이터 없으면 모든 통신사 표시"""
        data = self._serialize()
        carriers = {opt["carrier"] for opt in data["options"]}
        self.assertIn("SK", carriers)
        self.assertIn("LG", carriers)
