from typing import Callable, TypeVar

import requests
from lxml import etree

from phoneinone_server.settings import API_KEY_11st
from ..api import HOST_11st

T = TypeVar("T")


def get_product_detail_html(om_product_id: str) -> str:
    url = f"{HOST_11st}/prodservices/getProductDetailCont/{om_product_id}"
    headers = {"openapikey": API_KEY_11st}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"11번가 상세조회 HTTP 실패 - status: {response.status_code}, body: {response.content!r}"
        )

    root = etree.fromstring(response.content)

    if root.tag == "Products":
        message = root.findtext("message") or ""
        raise Exception(f"11번가 상세조회 실패 - {message}")

    html = root.findtext("prdDescContClob")
    if html is None:
        raise Exception(f"prdDescContClob 필드 없음 - response: {response.content!r}")
    return html


def update_product_detail_html(om_product_id: str, html_content: str) -> None:
    url = f"{HOST_11st}/prodservices/updateProductDetailCont/{om_product_id}"
    headers = {"openapikey": API_KEY_11st}

    payload = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<ProductDetailCont>\n"
        f"  <prdDescContClob><![CDATA[{html_content}]]></prdDescContClob>\n"
        "</ProductDetailCont>\n"
    )

    response = requests.request(
        method="POST",
        url=url,
        headers=headers,
        data=payload.encode("utf-8"),
    )

    if response.status_code not in (200, 201):
        raise Exception(
            f"11번가 상세수정 HTTP 실패 - status: {response.status_code}, body: {response.content!r}"
        )

    root = etree.fromstring(response.content)
    if root.tag == "Products":
        message = root.findtext("message") or ""
        raise Exception(f"11번가 상세수정 실패 - {message}")


def transform_and_update_product_detail_html(
    om_product_id: str,
    transformer: Callable[[str], tuple[str, T]],
    *,
    dry_run: bool = False,
) -> tuple[str, str, T]:
    """현재 HTML을 GET → transformer 적용 → 변경되었으면 PUT.

    transformer는 (new_html, info)를 반환한다. info는 변환 부산물(카운트/로그 등)이며
    호출자에게 그대로 전달된다. 부산물이 필요 없는 변환은 (new_html, None)을 반환하면 된다.

    Returns: (before_html, after_html, transformer_info). before == after면 update 호출 안 함.
    """
    before = get_product_detail_html(om_product_id)
    after, info = transformer(before)

    if before != after and not dry_run:
        update_product_detail_html(om_product_id, after)

    return before, after, info
