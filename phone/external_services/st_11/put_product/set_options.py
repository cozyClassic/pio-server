import requests

from django.db.models import Prefetch
from phoneinone_server.settings import API_KEY_11st
from phone.constants import CarrierChoices
from phone.models import OpenMarketProduct, OpenMarketProductOption, ProductOption
from .api import HOST_11st, CARRIER_TO_DEFAULT_PLAN_NAME


class SetOptions11ST:
    @staticmethod
    def _get_option_price(
        po: ProductOption, margin: int, commission_rate: float
    ) -> int:
        return int(round((po.final_price + margin) / (1 - commission_rate), -3))

    @staticmethod
    def _get_product_option_xml(plan_name: str, opt_price: int) -> str:
        return f"""<ProductOption>
  <useYn>Y</useYn>
  <colOptPrice>{opt_price}</colOptPrice>
  <colValue0>{plan_name}</colValue0>
  <colCount>10</colCount>
  <colSellerStockCd>CDESAD001</colSellerStockCd>
</ProductOption>
"""

    @classmethod
    def _get_carrier(cls, om_product: OpenMarketProduct) -> str:
        carriers = [
            carrier
            for carrier in CarrierChoices.VALUES
            if carrier in om_product.seller_code
        ]
        if not carriers:
            raise Exception(
                f"셀러코드에 매칭되는 통신사가 없습니다 - 셀러코드: {om_product.seller_code}"
            )
        return carriers[0]

    @classmethod
    def _get_default_option_xml(cls, carrier: str) -> str:
        plan_name = CARRIER_TO_DEFAULT_PLAN_NAME[carrier]
        return cls._get_product_option_xml(plan_name, 0)

    @classmethod
    def _get_queryset(cls, open_market_product_id_internal: int) -> OpenMarketProduct:
        om_product = (
            OpenMarketProduct.objects.select_related("open_market")
            .prefetch_related(
                Prefetch(
                    "options",
                    queryset=OpenMarketProductOption.objects.select_related(
                        "pio_product_option",
                        "pio_product_option__plan",
                        "pio_product_option__device_variant",
                    ),
                )
            )
            .filter(id=open_market_product_id_internal)
            .first()
        )

        if om_product is None:
            raise Exception(
                f"해당하는 오픈마켓 상품이 없습니다 - id: {open_market_product_id_internal}"
            )
        return om_product

    @classmethod
    def _get_available_options(
        cls, om_product: OpenMarketProduct, carrier: str, margin: int
    ) -> list[ProductOption]:
        registered_price = om_product.registered_price
        option_max_price = round(
            int(registered_price * (1 + om_product.open_market.option_max_rate / 100)),
            -3,
        )
        # 현재는 마이너스 가격의 옵션은 생성하지 않으므로, 고려하지 않는다.
        dv_id = om_product.device_variant_id
        contract_type = "번호이동" if "MNP" in om_product.seller_code else "기기변경"

        product_options = (
            ProductOption.objects.filter(
                device_variant_id=dv_id,
                contract_type=contract_type,
                discount_type="공시지원금",
                plan__carrier=carrier,
            )
            .select_related("plan")
            .order_by("plan__price")
        )

        return [
            po
            for po in product_options
            if cls._get_option_price(
                po, margin, om_product.open_market.commision_rate_default
            )
            < option_max_price
        ]

    @classmethod
    def set_om_options(cls, open_market_product_id_internal: int, margin: int):
        om_product = cls._get_queryset(open_market_product_id_internal)
        carrier = cls._get_carrier(om_product)
        open_market_product_id = om_product.om_product_id

        available_options = cls._get_available_options(om_product, carrier, margin)

        options_xml = "\n".join(
            cls._get_product_option_xml(
                po.plan.short_name,
                om_product.registered_price
                - cls._get_option_price(
                    po, margin, om_product.open_market.commision_rate_default
                ),
            )
            for po in available_options
        )

        url = f"{HOST_11st}/updateProductOption/{open_market_product_id}"
        headers = {"openapikey": API_KEY_11st}
        payload = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Product>
  <optSelectYn>Y</optSelectYn>
  <txtColCnt>1</txtColCnt>
  <colTitle>요금제</colTitle>
  <prdExposeClfCd>01</prdExposeClfCd>
  {cls._get_default_option_xml(carrier)}
  {options_xml}
</Product>
"""

        response = requests.request(
            method="POST",
            url=url,
            headers=headers,
            data=payload.encode("utf-8"),
        )

        if response.status_code not in (200, 201):
            raise Exception(
                f"11번가 옵션 업데이트 실패 - status: {response.status_code}, body: {response.content}"
            )
