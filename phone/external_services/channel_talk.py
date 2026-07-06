import requests
from phoneinone_server.settings import (
    CHANENLTALK_ACCESS_KEY,
    CHANENLTALK_ACCESS_SECRET,
    DEBUG,
)


class ChannelTalkAPI:
    CHANNELTALK_HEADERS = {
        "Content-Type": "application/json",
        "x-access-key": CHANENLTALK_ACCESS_KEY,
        "x-access-secret": CHANENLTALK_ACCESS_SECRET,
    }
    ORDER_ALERT_GROUP_ID = "501418" if DEBUG else "501406"
    OPEN_MARKET_ERROR_ALERT_GROUP_ID = "545526"
    OPEN_MARKET_ORDER_GROUP_ID = "545602"

    @staticmethod
    def post(path: str, json: dict) -> dict[str, str]:
        response = requests.post(
            url="https://api.channel.io" + path,
            json=json,
            headers=ChannelTalkAPI.CHANNELTALK_HEADERS,
        )
        return response.json()

    @staticmethod
    def get(path: str, params: dict = {}) -> dict:
        response = requests.get(
            url="https://api.channel.io" + path,
            params=params,
            headers=ChannelTalkAPI.CHANNELTALK_HEADERS,
        )
        if response.status_code != 200:
            raise Exception(f"Failed to get data: {response.text}")
        return response.json()


def send_order_alert(
    order_id: str, customer_name: str, customer_phone: str
) -> dict[str, str]:
    """Send a message to the team via Channel Talk."""
    # Implementation for sending message via Channel Talk
    response = ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": f"주문 알림: {order_id}, {customer_name}, {customer_phone}",
                },
            ]
        },
    )
    return response


def send_inquiry_alert(
    customer_name: str,
    customer_phone: str,
    device_name: str,
    internet_new: bool,
    card: bool,
    gift: bool,
) -> dict[str, str]:
    """Send a message to the team via Channel Talk."""
    response = ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": f"가격문의: {customer_name}, {customer_phone}, {device_name}, 인터넷가입: {internet_new}, 카드: {card}, 워치: {gift}",
                },
            ]
        },
    )
    return response


def send_calculator_lead_alert(
    *,
    session_id: str,
    contact_channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    device_name: str | None,
    pio_total: int,
    total_saving: int,
    funnel_variant: str,
) -> dict[str, str]:
    """Calculator 세션 lead 결정 (PATCH 첫 적용) 시 운영팀 채널 알림."""
    if contact_channel == "phone":
        header = f"📞 전화요청 (calculator): {customer_name or '-'} / {customer_phone or '-'}"
    elif contact_channel == "kakao":
        header = "💬 카톡상담 (calculator)"
    else:
        header = f"🔔 calculator lead ({contact_channel})"

    body = (
        f"단말: {device_name or '-'}\n"
        f"pio 총액: {pio_total:,}원 / 절약: {total_saving:,}원\n"
        f"funnel: {funnel_variant}\n"
        f"session: {session_id}"
    )

    response = ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {"type": "text", "value": f"{header}\n{body}"},
            ]
        },
    )
    return response


def send_open_market_order_alert(source: str, orders: list[dict[str, str]]):
    """
    orders = [{
        "order_no": "",
        "customer_name": "",
        "customer_phone": "",
        "product_name": "",
        "plan_name": "",
        "sell_price": "",
    }]
    """

    order_text = "\n\n".join(
        [(f"{o['customer_name']} / {o['product_name']}") for o in orders]
    )

    response = ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.OPEN_MARKET_ORDER_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": f"새 주문 알림({source}) \n {order_text}",
                },
            ]
        },
    )
    return response


def send_credit_check_alert(
    order_id: str, customer_name: str, customer_phone: str
) -> dict[str, str]:
    """Send a credit check alert to the team via Channel Talk."""
    response = ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": f"신용 조회 동의 알림: {order_id}, {customer_name}, {customer_phone}",
                },
            ]
        },
    )
    return response


def get_user_id_by_member_id(member_id: str) -> str | None:
    """Get a user from Channel Talk by member ID."""
    # member_id = "01012345678_홍길동"
    response = ChannelTalkAPI.get(
        path=f"/open/v5/members/@{member_id}",
    )

    user = response.get("user", None)
    if user is not None:
        return user.get("id", None)

    return None


def send_shipping_noti_to_customer(
    customer_name: str,
    channeltalk_user_id: str,
    customer_phone: str,
    shipping_method: str,
    shipping_number: str,
    device_name: str,
):
    response = ChannelTalkAPI.post(
        path=f"/open/v5/users/{channeltalk_user_id}/events",
        json={
            "name": "shipping_notification",
            "property": {
                "customerName": customer_name,
                "customerPhone": customer_phone,
                "shippinghost": (
                    f"m.epost.go.kr/postal/mobile/mobile.trace.RetrieveDomRigiTraceList.comm"
                    if shipping_method == "우체국"
                    # 로젠
                    else f"www.ilogen.com/m/personal/trace/{shipping_number}"
                ),
                "sid1": shipping_number,
                "deviceName": device_name,
            },
        },
    )

    return response


def send_open_market_update_failure_alert(
    task_name: str, om_product_id: int, detail: str, market: str = "11번가"
):
    # om_product_id=0 은 특정 상품이 아닌 태스크 전체 실패 → ID 줄 생략
    id_line = f"내부 ID: {om_product_id}\n" if om_product_id else ""
    ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.OPEN_MARKET_ERROR_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": (
                        f"[{market} {task_name} 실패]\n"
                        f"{id_line}"
                        f"상세: {detail}"
                    ),
                }
            ]
        },
    )


def send_marketplace_sync_failure_alert(stage: str, carrier: str, reason: str):
    """정책 엑셀 업로드 후처리(마켓플레이스 동기화) 단계 실패 알림."""
    ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.OPEN_MARKET_ERROR_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": (
                        f"[정책 엑셀 후처리 실패]\n"
                        f"단계: {stage}\n"
                        f"통신사: {carrier}\n"
                        f"사유: {reason}\n"
                        f"엑셀 재업로드로 재시도하세요."
                    ),
                }
            ]
        },
    )
