"""SSG 신규 주문(배송지시 목록) 조회.

listShppDirection = 주문완료 시 생성되는 배송지시 목록. 결제완료된 신규 주문을
여기서 감지한다(11번가 ordservices/complete 대응). 주문상품(아이템) 단위 row라
한 주문에 복수 row가 올 수 있으며, 알림 중복 방지는 주문번호(ordNo)로 한다.
"""

from datetime import datetime, timedelta, timezone

from ..api import ssg_post

# 배송지시 목록 조회 기간. 6시간 주기 폴링 + OpenMarketOrder 중복방지 전제로
# 넉넉히 최근 3일을 조회한다(최대 180일까지 가능).
ORDER_LOOKBACK_DAYS = 3

KST = timezone(timedelta(hours=9))


def _format_date(t: datetime) -> str:
    return t.strftime("%Y%m%d")


def _extract_directions(result: dict) -> list[dict]:
    """shppDirections 리스트에서 주문상품 dict만 추출.

    SSG 리스트 응답은 [{"shppDirection": {...}}] 또는 [{...}] 형태일 수 있고,
    빈 목록은 [""]로 온다. 두 형태를 모두 방어적으로 처리한다.
    """
    raw = result.get("shppDirections") or []
    if isinstance(raw, dict):
        raw = [raw]

    directions = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        d = item.get("shppDirection", item)
        if isinstance(d, dict) and d.get("ordNo"):
            directions.append(d)
    return directions


def _parse_order(d: dict) -> dict:
    return {
        "order_no": d.get("ordNo"),
        "orig_order_no": d.get("orordNo"),
        "customer_name": d.get("ordpeNm"),
        "customer_phone": d.get("ordpeHpno"),
        "product_name": d.get("itemNm"),
        "product_no": d.get("itemId"),  # 공식신청서 링크 매핑용(SSG itemId)
        "plan_name": d.get("uitemNm"),  # SSG 옵션명 = Plan.name 그대로
        "sell_price": d.get("sellprc"),
        "site_no": d.get("siteNo"),
    }


def get_recent_ssg_orders() -> list[dict]:
    """최근 ORDER_LOOKBACK_DAYS일 주문완료(배송지시) 목록을 조회해 파싱한다."""
    today = datetime.now(KST)
    start = today - timedelta(days=ORDER_LOOKBACK_DAYS)

    body = {
        "requestShppDirection": {
            "perdType": "02",  # 주문완료일 기준
            "perdStrDts": _format_date(start),
            "perdEndDts": _format_date(today),
        }
    }
    data = ssg_post("/api/pd/1/listShppDirection.ssg", body, action="주문목록조회")
    directions = _extract_directions(data.get("result", {}))
    return [_parse_order(d) for d in directions]
