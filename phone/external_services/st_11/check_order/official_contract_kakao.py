"""11번가 주문 → 공식신청서 안내 알림톡 트리거.

자사몰 주문은 프론트(OrderForm.tsx)가 채널톡 유저 프로필을 갱신한 뒤
커스텀 이벤트 "Order"를 쏘고, 채널톡 마케팅 자동화가 알림톡을 발송한다.
11번가 주문은 프론트를 거치지 않으므로 백엔드에서 같은 흐름을 재현한다:
유저 업서트(전화번호 포함) → Order 이벤트 발사 → 자동화가 알림톡 발송.

알림톡 템플릿이 참조하는 변수:
    https://#{officialContracthost}?p=#{p}&formId=#{formId}&agentId=#{agentId}
        &openmktCd=#{openmktCd}&prdcID=#{prdcID}
    + customerName, deviceName, phone
쿼리 파라미터(p, formId, ...)는 공식신청서 링크 URL에서 그대로 풀어서 담는다.
"""

import re

from phone.constants import DiscountTypeChoices, OpenMarketChoices
from phone.models import OpenMarketProduct, ProductOption
from phone.external_services.channel_talk import send_order_event, upsert_user

# 11번가 주문의 옵션명 형식: "요금제:프리미어 시그니처-1개" → Plan.name 추출
_PLAN_OPTION_PATTERN = re.compile(r"^요금제:(?P<plan_name>.+)-\d+개$")


def _extract_plan_name(option_text: str) -> str:
    matched = _PLAN_OPTION_PATTERN.match(option_text or "")
    if not matched:
        raise Exception(f"옵션명에서 요금제명을 추출할 수 없습니다: {option_text!r}")
    return matched.group("plan_name").strip()


def _clean_phone(phone: str) -> str:
    digits = re.sub(r"[^0-9]", "", phone or "")
    if len(digits) < 10:
        raise Exception(f"주문자 연락처가 올바르지 않습니다: {phone!r}")
    return digits


def _find_official_contract_link(product_no: str, plan_name: str) -> str:
    om_product = OpenMarketProduct.objects.filter(
        open_market__source=OpenMarketChoices.ST11,
        om_product_id=product_no,
    ).first()
    if om_product is None:
        raise Exception(f"11번가 상품번호에 해당하는 상품이 없습니다: {product_no}")

    product_option = (
        ProductOption.objects.filter(
            device_variant_id=om_product.device_variant_id,
            contract_type=om_product.get_contract_type(),
            discount_type=DiscountTypeChoices.SUBSIDY,
            plan__carrier=om_product.get_carrier(),
            plan__name=plan_name,
        )
        .select_related("official_contract_link")
        .first()
    )
    if product_option is None:
        raise Exception(
            f"매칭되는 상품옵션이 없습니다 - 상품: {om_product.name}, 요금제: {plan_name}"
        )
    if product_option.official_contract_link is None:
        raise Exception(
            f"공식신청서 링크가 등록되지 않은 옵션입니다 - "
            f"상품: {om_product.name}, 요금제: {plan_name}"
        )

    return product_option.official_contract_link.link


def _split_link(link: str) -> tuple[str, dict[str, str]]:
    """공식신청서 링크를 호스트와 쿼리 dict로 분리 (프론트 OrderForm.tsx와 동일 규칙)."""
    stripped = link.replace("https://", "").replace("http://", "")
    host, _, query_string = stripped.partition("?")

    queries = {}
    for pair in query_string.split("&"):
        if not pair:
            continue
        key, _, value = pair.partition("=")
        queries[key] = value

    return host, queries


def build_order_event(order: dict[str, str]) -> dict:
    """주문 1건에서 채널톡 유저 정보와 Order 이벤트 property를 구성한다.

    매핑 실패(상품/옵션/링크 없음) 시 예외를 던진다. 발송은 하지 않는다.
    """
    plan_name = _extract_plan_name(order["plan_name"])
    link = _find_official_contract_link(order["product_no"], plan_name)
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
        # 자사몰 상담톡 통합과 같은 컨벤션 (get_user_id_by_member_id 참고)
        "member_id": f"{phone}_{customer_name}",
        "name": customer_name,
        "mobile_number": "+82" + phone[1:],
        "property": property,
    }


def send_official_contract_kakao(order: dict[str, str]) -> None:
    """11번가 주문 1건에 대해 공식신청서 안내 알림톡을 트리거한다."""
    event = build_order_event(order)
    user_id = upsert_user(
        member_id=event["member_id"],
        name=event["name"],
        mobile_number=event["mobile_number"],
    )
    send_order_event(user_id, event["property"])
