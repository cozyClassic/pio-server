"""SSG 주문 → 공식신청서 안내 알림톡 트리거.

11번가와 동일한 흐름(유저 업서트 → Order 이벤트 발사 → 채널톡 자동화가 알림톡
발송)을 SSG 주문에도 적용한다. 11번가의 범용 헬퍼를 재사용하되, 차이는 두 가지:
- SSG 옵션명(uitemNm)은 이미 Plan.name 그대로라 별도 추출이 필요 없다.
- 상품 조회 source가 SSG다(_find_official_contract_link에 source 전달).
"""

from phone.constants import OpenMarketChoices
from phone.external_services.channel_talk import send_order_event, upsert_user
from phone.external_services.st_11.check_order.official_contract_kakao import (
    _clean_phone,
    _find_official_contract_link,
    _split_link,
)


def build_order_event(order: dict[str, str]) -> dict:
    """SSG 주문 1건에서 채널톡 유저 정보와 Order 이벤트 property를 구성한다.

    매핑 실패(상품/옵션/링크 없음) 시 예외를 던진다. 발송은 하지 않는다.
    """
    plan_name = (order.get("plan_name") or "").strip()
    if not plan_name:
        raise Exception(f"주문 옵션명(요금제)이 비어 있습니다: {order.get('order_no')}")

    link = _find_official_contract_link(
        order["product_no"], plan_name, source=OpenMarketChoices.SSG
    )
    host, queries = _split_link(link)

    phone = _clean_phone(order["customer_phone"])
    customer_name = order["customer_name"]

    property = {
        "customerName": customer_name,
        "deviceName": order["product_name"],
        "phone": phone,
        "officialContracthost": host,
        **queries,
    }
    if (order.get("order_no") or "").isdigit():
        property["orderId"] = int(order["order_no"])

    return {
        "member_id": f"{phone}_{customer_name}",
        "name": customer_name,
        "mobile_number": "+82" + phone[1:],
        "property": property,
    }


def send_official_contract_kakao(order: dict[str, str]) -> None:
    """SSG 주문 1건에 대해 공식신청서 안내 알림톡을 트리거한다."""
    event = build_order_event(order)
    user_id = upsert_user(
        member_id=event["member_id"],
        name=event["name"],
        mobile_number=event["mobile_number"],
    )
    send_order_event(user_id, event["property"])
