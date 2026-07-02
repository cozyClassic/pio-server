"""11번가 상품 전시(판매) 상태 변경 API.

- 전시중지 처리:   PUT /rest/prodstatservice/stat/stopdisplay/{prdNo}    (STAT 105)
- 전시중지 해제:   PUT /rest/prodstatservice/stat/restartdisplay/{prdNo} (STAT 103)

두 API 모두 Path Parameter만 사용하며 payload는 없다. 응답은 EUC-KR XML로
`<ClientMessage><message>...</message><resultCode>200</resultCode></ClientMessage>`
형태이며, resultCode 200이 성공이다.
"""

import requests
from lxml import etree

from phoneinone_server.settings import API_KEY_11st
from ..api import HOST_11st


def _put_display_status(action: str, om_product_id: str) -> str:
    """전시상태 변경 API를 호출하고 결과 message를 반환한다.

    action: "stopdisplay" | "restartdisplay"
    실패(HTTP 오류 또는 resultCode != 200) 시 예외를 발생시킨다.
    """
    url = f"{HOST_11st}/prodstatservice/stat/{action}/{om_product_id}"
    headers = {"openapikey": API_KEY_11st}

    response = requests.put(url, headers=headers)
    if response.status_code not in (200, 201):
        raise Exception(
            f"11번가 전시상태 변경 HTTP 실패 - action: {action}, "
            f"status: {response.status_code}, body: {response.content!r}"
        )

    root = etree.fromstring(response.content)
    result_code = root.findtext("resultCode")
    message = root.findtext("message") or ""

    if result_code != "200":
        raise Exception(
            f"11번가 전시상태 변경 실패 - action: {action}, "
            f"resultCode: {result_code}, message: {message}"
        )

    return message


def stop_display(om_product_id: str) -> str:
    """상품을 전시중지(판매중지) 처리한다. (재고 소진 시)"""
    return _put_display_status("stopdisplay", om_product_id)


def restart_display(om_product_id: str) -> str:
    """전시중지된 상품을 다시 전시(판매재개) 처리한다. (재고 확보 시)"""
    return _put_display_status("restartdisplay", om_product_id)
