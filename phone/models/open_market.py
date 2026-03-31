from django.db import models
from tinymce import models as tinymce_models

from phone.constants import CarrierChoices, ContractTypeChoices, OpenMarketChoices

from .base import SoftDeleteModel
from .device import DeviceVariant
from .product import ProductOption
from .inventory import Inventory


class OpenMarket(SoftDeleteModel):
    source = models.CharField(
        "오픈마켓업체",
        choices=OpenMarketChoices.Choices,
        null=False,
        blank=False,
        default=OpenMarketChoices.ST11,
        max_length=20,
    )
    option_min_rate = models.IntegerField(default=0)
    option_max_rate = models.IntegerField(default=0)
    commision_rate_default = models.FloatField(default=0.08)
    commision_rate_compare_platform = models.FloatField(default=0.02)
    api_key = models.CharField(max_length=255, default="", blank=True)

    def __str__(self):
        return self.source


class OpenMarketProduct(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    open_market = models.ForeignKey(
        OpenMarket, on_delete=models.CASCADE, related_name="products"
    )
    device_variant = models.ForeignKey(
        DeviceVariant,
        on_delete=models.SET_NULL,
        related_name="open_market_product",
        null=True,
        default=None,
    )
    om_product_id = models.CharField(
        max_length=100, blank=True, null=True, default=None
    )
    seller_code = models.CharField(max_length=100, blank=True, null=True, default=None)
    name = models.CharField(max_length=255, default="", blank=True)
    registered_price = models.PositiveIntegerField(default=10000)
    detail_page_html = tinymce_models.HTMLField(default="", blank=True)
    last_price_updated_at = models.DateTimeField(default=None, null=True)

    def __str__(self):
        return self.name

    def get_carrier(self):
        if hasattr(self, "carrier") and self.carrier:
            return self.carrier

        if CarrierChoices.KT in self.seller_code:
            carrier = CarrierChoices.KT
        elif CarrierChoices.LG in self.seller_code:
            carrier = CarrierChoices.LG
        elif CarrierChoices.SK in self.seller_code:
            carrier = CarrierChoices.SK
        else:
            raise Exception(
                f"판매자 코드에서 통신사 정보를 찾을 수 없습니다: {self.seller_code}"
            )

        self.carrier = carrier
        return carrier

    def get_contract_type(self):
        if hasattr(self, "contract_type") and self.contract_type:
            return self.contract_type

        contract_type = (
            ContractTypeChoices.CHANGE
            if "DEVICE" in self.seller_code
            else ContractTypeChoices.MNP
        )

        self.contract_type = contract_type
        return contract_type

    def get_capacity(self):
        if hasattr(self, "capacity") and self.capacity:
            return self.capacity

        for capacity in ["1024", "512", "256", "128", "64", "32"]:
            if capacity in self.seller_code:
                self.capacity = capacity
                return capacity

        raise Exception(f"코드에서 용량 정보를 찾을 수 없습니다: {self.seller_code}")


class OpenMarketProductOption(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    open_market_product = models.ForeignKey(
        OpenMarketProduct, on_delete=models.CASCADE, related_name="options"
    )
    pio_product_option = models.ForeignKey(
        ProductOption, on_delete=models.CASCADE, related_name="open_market_options"
    )
    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="open_market_options",
    )
    om_id = models.CharField(max_length=255, default="", blank=True)
    option_name = models.CharField(max_length=255, default="", blank=True)
    price = models.IntegerField(default=0)

    def _assert_relations_cached_for_validate_name(self):
        if not all(
            (key in self.__dict__ for key in ("pio_product_option", "open_market"))
        ):
            raise RuntimeError("N+1 방지: select_related 누락")

        if not all(
            (
                key in self.__dict__["pio_product_option"].__dict__
                for key in ("plan", "device_variant")
            )
        ):
            raise RuntimeError("N+1 방지: select_related 누락")

    def validate_product_name(self):
        self._assert_relations_cached_for_validate_name()

        om_product_name = self.open_market_product.name
        pio_product_option = self.pio_product_option
        carrier = pio_product_option.plan.carrier
        contract_type = pio_product_option.contract_type
        discount_type = pio_product_option.discount_type
        capacity = pio_product_option.device_variant.storage_capacity

        error_list = []

        if carrier not in om_product_name:
            error_list.append(("통신사명", carrier))

        if contract_type not in om_product_name:
            error_list.append(("가입유형", contract_type))

        discount_type_keywords = {
            "공시지원금": ("공시", "공통", "단말"),
            "선택약정": ("선약", "선택약정", "요금"),
        }
        if discount_type in discount_type_keywords:
            keywords = discount_type_keywords[discount_type]
            if not any(key in om_product_name for key in keywords):
                error_list.append(("할인유형", discount_type))

        if str(capacity) not in om_product_name:
            error_list.append(("저장용량", capacity))

        return error_list

    def validate_price(self):
        product = self.open_market_product
        open_market = product.open_market

        if (self.price / product.registered_price) * 100 > open_market.option_max_rate:
            raise Exception("")
        if (self.price / product.registered_price) * 100 < open_market.option_min_rate:
            raise Exception("")

    def validate_plan(self):
        plan = self.pio_product_option.plan
        name_split = plan.split(" ")
        if name_split[-1] in self.option_name:
            return
        raise Exception("옵션명 요금제명 확인 필요")


class OpenMarketOrder(models.Model):
    """오픈마켓 주문 알림 중복 방지용 - 알림을 보낸 주문 ID 저장"""

    id = models.AutoField(primary_key=True)
    source = models.CharField(
        "오픈마켓",
        choices=OpenMarketChoices.Choices,
        max_length=20,
    )
    order_no = models.CharField("주문번호", max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("source", "order_no")
