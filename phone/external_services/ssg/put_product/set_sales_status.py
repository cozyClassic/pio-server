"""SSG 상품 판매상태(전시) 변경.

판매상태 도메인(sales-status)의 sellStatCd로 상품 노출을 제어한다.
- 20: 판매중(노출), 80: 판매중지(미노출)

옵션 상품은 대표 재고수량(usablInvQty)을 보내면 거부되므로, GET 응답에서
스칼라 필수 필드(sellFrmCd/invMngYn/전시기간)만 반향해 상태만 바꾼다.
"""

from ..api import ssg_get, ssg_post

SELL_STATUS_ON = 20
SELL_STATUS_OFF = 80


def get_sales_status(item_id: str) -> dict:
    data = ssg_get(f"/item/0.1/online/{item_id}/sales-status", action="판매상태조회")
    status = data.get("result", {}).get("salesStatus")
    if not status:
        raise Exception(f"판매상태를 찾을 수 없습니다 - itemId: {item_id}")
    return status


def set_sales_status(item_id: str, sell_stat_cd: int) -> None:
    current = get_sales_status(item_id)
    payload = {
        "online_updateSalesStatus": {
            "salesStatus": {
                "sellStatCd": sell_stat_cd,
                "sellFrmCd": current.get("sellFrmCd", 10),
                "invMngYn": current.get("invMngYn", "Y"),
                "invQtyMarkgYn": current.get("invQtyMarkgYn", "N"),
                "dispStrtDt": current.get("dispStrtDt"),
                "dispEndDt": current.get("dispEndDt"),
            }
        }
    }
    ssg_post(
        f"/item/0.1/online/{item_id}/sales-status",
        payload,
        action=f"판매상태 변경({sell_stat_cd})",
    )


def stop_selling(item_id: str) -> None:
    """판매중지(80) — 상품을 노출에서 내린다."""
    set_sales_status(item_id, SELL_STATUS_OFF)


def start_selling(item_id: str) -> None:
    """판매재개(20) — 상품을 노출한다.

    주의: 실제 판매 개시를 의미한다. 재고 동기화의 자동 재개는 명시적 활성화
    전까지 호출하지 않는다([[ssg-integration-specs]]).
    """
    set_sales_status(item_id, SELL_STATUS_ON)
