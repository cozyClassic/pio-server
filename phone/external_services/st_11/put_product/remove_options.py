import requests

from .api import HOST_11st
from phoneinone_server.settings import API_KEY_11st
from phone.constants import CarrierChoices

CARRIER_TO_PLAN_NAME = {
    CarrierChoices.SK: "플래티넘",
    CarrierChoices.KT: "초이스 프리미엄",
    CarrierChoices.LG: "프리미어 시그니처",
}


def remove_options_except_default(carrier: str, open_market_product_id: str):
    url = f"{HOST_11st}/updateProductOption/{open_market_product_id}"
    plan_name = CARRIER_TO_PLAN_NAME[carrier]

    if plan_name is None:
        raise Exception(f"입력된 통신사가 올바르지 않습니다: {carrier}")

    headers = {
        "openapikey": API_KEY_11st,
    }
    payload = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Product>
  <optSelectYn>Y</optSelectYn>
  <txtColCnt>1</txtColCnt>
  <colTitle>요금제</colTitle>
  <prdExposeClfCd>01</prdExposeClfCd>
<ProductOption>
  <useYn>Y</useYn>
  <colOptPrice>0</colOptPrice>
  <colValue0>{plan_name}</colValue0>
  <colCount>10</colCount>
  <colSellerStockCd>CDESAD001</colSellerStockCd>
  </ProductOption>
</Product>
"""

    response = requests.request(
        method="POST",
        url=url,
        headers=headers,
        data=payload.encode("utf-8"),
    )

    if response.status_code not in (200, 201):
        print(response.status_code)
        print(response.raw)
        print(response.content)
        raise Exception(f"요청이 실패했습니다")

    return


remove_options_except_default(CarrierChoices.SK, 9105055842)
