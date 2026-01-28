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

    @staticmethod
    def post(path: str, json: dict) -> dict:
        response = requests.post(
            url="https://api.channel.io" + path,
            json=json,
            headers=ChannelTalkAPI.CHANNELTALK_HEADERS,
        )
        return response.json()

    @staticmethod
    def get(path: str, params: dict = None) -> dict:
        response = requests.get(
            url="https://api.channel.io" + path,
            params=params,
            headers=ChannelTalkAPI.CHANNELTALK_HEADERS,
        )
        if response.status_code != 200:
            raise Exception(f"Failed to get data: {response.text}")
        return response.json()


def send_order_alert(order_id: str, customer_name: str, customer_phone: str) -> None:
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


def send_credit_check_alert(
    order_id: str, customer_name: str, customer_phone: str
) -> None:
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
