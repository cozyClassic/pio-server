import requests
from lxml import etree

from phoneinone_server.settings import API_KEY_11st
from ..api import HOST_11st


def get_product_listed_price(om_product_id: str) -> int:
    """11번가에 등록된 상품의 현재 판매가(selPrc)를 조회한다.

    옵션이 있는 상품의 경우 selPrc는 "옵션 0원"에 해당하는 기본 판매가이다.
    """
    url = f"{HOST_11st}/prodmarketservice/prodmarket/{om_product_id}"
    headers = {"openapikey": API_KEY_11st}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"11번가 상품조회 HTTP 실패 - status: {response.status_code}, body: {response.content!r}"
        )

    root = etree.fromstring(response.content)
    if root.tag == "Products":
        message = root.findtext("message") or ""
        raise Exception(f"11번가 상품조회 실패 - {message}")

    sel_prc = root.findtext("selPrc")
    if sel_prc is None:
        raise Exception(f"selPrc 필드 없음 - response: {response.content!r}")
    return int(sel_prc)


def get_display_status_code(om_product_id: str) -> str:
    """11번가에 등록된 상품의 현재 판매상태 코드(selStatCd)를 조회한다.

    주요 코드: 103=판매중, 104=품절, 105=전시중지중, 106/107=판매종료.
    전시중지 처리(stopdisplay) 상태가 105이다.
    """
    url = f"{HOST_11st}/prodmarketservice/prodmarket/{om_product_id}"
    headers = {"openapikey": API_KEY_11st}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(
            f"11번가 상품조회 HTTP 실패 - status: {response.status_code}, body: {response.content!r}"
        )

    root = etree.fromstring(response.content)
    if root.tag == "Products":
        message = root.findtext("message") or ""
        raise Exception(f"11번가 상품조회 실패 - {message}")

    status_code = root.findtext("selStatCd")
    if status_code is None:
        raise Exception(f"selStatCd 필드 없음 - response: {response.content!r}")
    return status_code
