import requests

from phoneinone_server.settings import API_KEY_11st
from .api import HOST_11st
from lxml import etree
from math import ceil


def _set_product_price(open_market_product_id: str, price: int):
    url = f"{HOST_11st}/product/priceCoupon/{open_market_product_id}"
    headers = {"openapikey": API_KEY_11st}
    payload = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Product>
    <selPrc>{price}</selPrc>
    <cuponcheck>N</cuponcheck>
    </Product>
"""

    response = requests.request(
        method="POST",
        url=url,
        headers=headers,
        data=payload.encode("utf-8"),
    )

    root = etree.fromstring(response.content)
    message = root.findtext("message")
    if "실패" in message:
        return int(root.findtext("preSelPrc"))

    return price


def set_product_price(open_market_product_id: str, price: int):
    count = 10
    _next_price = price

    for i in range(count):
        prev_price = _set_product_price(open_market_product_id, _next_price)

        if prev_price == price:
            break

        # 가격 설정은 10원 단위로만 가능
        _next_price = ceil(max(int(prev_price * 0.2), price) / 100) * 100

    return
