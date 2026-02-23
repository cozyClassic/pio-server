import requests

from phoneinone_server.settings import API_KEY_11st
from .api import HOST_11st, CARRIER_TO_DEFAULT_PLAN_NAME


def remove_options_except_default(carrier: str, open_market_product_id: str):
    plan_name = CARRIER_TO_DEFAULT_PLAN_NAME.get(carrier)
    if plan_name is None:
        raise Exception(f"입력된 통신사가 올바르지 않습니다: {carrier}")

    url = f"{HOST_11st}/updateProductOption/{open_market_product_id}"
    headers = {"openapikey": API_KEY_11st}
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
        raise Exception(
            f"11번가 옵션 제거 실패 - status: {response.status_code}, body: {response.content}"
        )
