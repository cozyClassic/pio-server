import math
from django.test import TestCase, TransactionTestCase

from phone.models import (
    Device,
    DeviceColor,
    DeviceVariant,
    Plan,
    Product,
    ProductOption,
    ProductSeries,
    Order,
    CreditCheckAgreement,
    FAQ,
    Review,
    SoftDeleteModel,
    get_int_or_zero,
    Dealership,
)


class GetIntOrZeroTest(TestCase):
    def test_none_returns_zero(self):
        self.assertEqual(get_int_or_zero(None), 0)

    def test_nan_returns_zero(self):
        self.assertEqual(get_int_or_zero(float("nan")), 0)

    def test_normal_int(self):
        self.assertEqual(get_int_or_zero(1000), 1000)

    def test_float_value(self):
        self.assertEqual(get_int_or_zero(999.9), 999)

    def test_zero(self):
        self.assertEqual(get_int_or_zero(0), 0)

    def test_negative(self):
        self.assertEqual(get_int_or_zero(-500), -500)


class SoftDeleteTest(TestCase):
    def setUp(self):
        self.device = Device.objects.create(
            model_name="Galaxy S25", brand="Samsung", series="갤럭시 S"
        )

    def test_soft_delete_sets_deleted_at(self):
        self.device.delete()
        # refresh_from_db uses default manager which filters deleted records,
        # so we query the DB directly
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT deleted_at FROM phone_device WHERE id = %s",
                [self.device.id],
            )
            deleted_at = cursor.fetchone()[0]
        self.assertIsNotNone(deleted_at)

    def test_soft_deleted_not_in_default_queryset(self):
        self.device.delete()
        self.assertFalse(Device.objects.filter(id=self.device.id).exists())

    def test_hard_delete_removes_from_db(self):
        device_id = self.device.id
        self.device.hard_delete()
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM phone_device WHERE id = %s", [device_id]
            )
            count = cursor.fetchone()[0]
        self.assertEqual(count, 0)

    def test_queryset_delete_is_soft(self):
        Device.objects.filter(id=self.device.id).delete()
        # Should not appear in default manager
        self.assertFalse(Device.objects.filter(id=self.device.id).exists())
        # But should still exist in DB
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM phone_device WHERE id = %s", [self.device.id]
            )
            count = cursor.fetchone()[0]
        self.assertEqual(count, 1)


class CalculateFinalPriceTest(TestCase):
    """ProductOption.calculate_final_price 테스트"""

    def test_basic_calculation(self):
        """기본 계산: device_price - additional_discount"""
        result = ProductOption.calculate_final_price(
            device_price=1000000,
            discount_type="선택약정",
            contract_type="기기변경",
            subsidy_amount=0,
            subsidy_amount_mnp=0,
            additional_discount=100000,
        )
        self.assertEqual(result, 900000)

    def test_subsidy_discount(self):
        """공시지원금 적용"""
        result = ProductOption.calculate_final_price(
            device_price=1000000,
            discount_type="공시지원금",
            contract_type="기기변경",
            subsidy_amount=200000,
            subsidy_amount_mnp=0,
            additional_discount=100000,
        )
        self.assertEqual(result, 700000)

    def test_subsidy_with_mnp(self):
        """공시지원금 + 번호이동 추가할인"""
        result = ProductOption.calculate_final_price(
            device_price=1000000,
            discount_type="공시지원금",
            contract_type="번호이동",
            subsidy_amount=200000,
            subsidy_amount_mnp=50000,
            additional_discount=100000,
        )
        self.assertEqual(result, 650000)

    def test_mnp_only_applies_with_subsidy(self):
        """선택약정에서는 번호이동 할인 미적용"""
        result = ProductOption.calculate_final_price(
            device_price=1000000,
            discount_type="선택약정",
            contract_type="번호이동",
            subsidy_amount=200000,
            subsidy_amount_mnp=50000,
            additional_discount=100000,
        )
        self.assertEqual(result, 900000)

    def test_none_values(self):
        """None 입력 처리"""
        result = ProductOption.calculate_final_price(
            device_price=1000000,
            discount_type="공시지원금",
            contract_type="번호이동",
            subsidy_amount=None,
            subsidy_amount_mnp=None,
            additional_discount=None,
        )
        self.assertEqual(result, 1000000)

    def test_all_none(self):
        """모든 값이 None"""
        result = ProductOption.calculate_final_price(
            device_price=None,
            discount_type="선택약정",
            contract_type="기기변경",
            subsidy_amount=None,
            subsidy_amount_mnp=None,
            additional_discount=None,
        )
        self.assertEqual(result, 0)

    def test_negative_result_possible(self):
        """할인이 기기가격보다 큰 경우 음수 가능"""
        result = ProductOption.calculate_final_price(
            device_price=100000,
            discount_type="공시지원금",
            contract_type="번호이동",
            subsidy_amount=200000,
            subsidy_amount_mnp=50000,
            additional_discount=100000,
        )
        self.assertEqual(result, -250000)


class ProductOptionSaveTest(TestCase):
    """ProductOption.save() 시 final_price 자동 계산 테스트"""

    def setUp(self):
        self.device = Device.objects.create(model_name="Galaxy S25", brand="Samsung")
        self.variant = DeviceVariant.objects.create(
            device=self.device,
            storage_capacity="256GB",
            device_price=1200000,
        )
        self.plan = Plan.objects.create(
            name="5G 프리미어 에센셜",
            carrier="SK",
            category_1="5G",
            category_2="5GX",
            price=69000,
            data_allowance="무제한",
            call_allowance="무제한",
            sms_allowance="무제한",
        )
        self.series = ProductSeries.objects.create(name="갤럭시 S")
        self.product = Product.objects.create(
            name="갤럭시 S25 256GB",
            device=self.device,
            product_series=self.series,
        )

    def test_final_price_calculated_on_save(self):
        option = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1200000,
            plan=self.plan,
            discount_type="공시지원금",
            contract_type="번호이동",
            subsidy_amount=300000,
            subsidy_amount_mnp=50000,
            additional_discount=100000,
        )
        self.assertEqual(option.final_price, 750000)

    def test_monthly_payment_with_subsidy(self):
        """공시지원금 월 할부금 계산"""
        option = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1200000,
            plan=self.plan,
            discount_type="공시지원금",
            contract_type="기기변경",
            subsidy_amount=300000,
            additional_discount=100000,
        )
        # final_price = 1200000 - 100000 - 300000 = 800000
        # monthly = 800000 * 1.0625 / 24 + 69000
        expected = int(800000 * (1.0625 / 24) + 69000)
        self.assertEqual(option.monthly_payment, expected)

    def test_monthly_payment_with_optional_discount(self):
        """선택약정 월 할부금 계산 (요금제 25% 할인)"""
        option = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1200000,
            plan=self.plan,
            discount_type="선택약정",
            contract_type="기기변경",
            additional_discount=100000,
        )
        # final_price = 1200000 - 100000 = 1100000
        # monthly = 1100000 * 1.0625 / 24 + 69000 * 0.75
        expected = int(1100000 * (1.0625 / 24) + 69000 * 0.75)
        self.assertEqual(option.monthly_payment, expected)


class ProductBestOptionTest(TransactionTestCase):
    """Product.best_price_option 자동 갱신 테스트 (TransactionTestCase for on_commit)"""

    def setUp(self):
        self.device = Device.objects.create(model_name="iPhone 16", brand="Apple")
        self.variant = DeviceVariant.objects.create(
            device=self.device,
            storage_capacity="256GB",
            device_price=1400000,
        )
        self.plan_cheap = Plan.objects.create(
            name="LTE 베이직",
            carrier="KT",
            category_1="LTE",
            category_2="기본",
            price=35000,
            data_allowance="6GB",
            call_allowance="무제한",
            sms_allowance="무제한",
        )
        self.plan_expensive = Plan.objects.create(
            name="5G 슈퍼플랜",
            carrier="KT",
            category_1="5G",
            category_2="프리미엄",
            price=89000,
            data_allowance="무제한",
            call_allowance="무제한",
            sms_allowance="무제한",
        )
        self.product = Product.objects.create(
            name="iPhone 16 256GB",
            device=self.device,
        )

    def test_best_option_updated_on_option_create(self):
        """옵션 생성 시 best_price_option 갱신"""
        option = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1400000,
            plan=self.plan_cheap,
            discount_type="선택약정",
            contract_type="기기변경",
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.best_price_option, option)

    def test_best_option_picks_cheapest(self):
        """여러 옵션 중 최저가 선택"""
        expensive_option = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1400000,
            plan=self.plan_expensive,
            discount_type="선택약정",
            contract_type="기기변경",
        )
        cheap_option = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1400000,
            plan=self.plan_cheap,
            discount_type="공시지원금",
            contract_type="번호이동",
            subsidy_amount=500000,
            subsidy_amount_mnp=100000,
            additional_discount=200000,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.best_price_option, cheap_option)

    def test_best_option_updated_on_option_delete(self):
        """옵션 삭제 시 best_price_option 갱신"""
        option1 = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1400000,
            plan=self.plan_cheap,
            discount_type="공시지원금",
            contract_type="번호이동",
            subsidy_amount=500000,
            additional_discount=200000,
        )
        option2 = ProductOption.objects.create(
            product=self.product,
            device_variant=self.variant,
            device_price=1400000,
            plan=self.plan_expensive,
            discount_type="선택약정",
            contract_type="기기변경",
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.best_price_option, option1)

        # 최저가 옵션 삭제
        option1.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.best_price_option, option2)
