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
    def post(url: str, json: dict) -> dict:
        response = requests.post(
            url=url,
            json=json,
            headers=ChannelTalkAPI.CHANNELTALK_HEADERS,
        )
        return response.json()

    @staticmethod
    def get(url: str, params: dict = None) -> dict:
        response = requests.get(
            url=url,
            params=params,
            headers=ChannelTalkAPI.CHANNELTALK_HEADERS,
        )
        return response.json()


def send_order_alert(order_id: str, customer_name: str, customer_phone: str) -> None:
    """Send a message to the team via Channel Talk."""
    # Implementation for sending message via Channel Talk
    response = ChannelTalkAPI.post(
        url=f"https://api.channel.io/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
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
        url=f"https://api.channel.io/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
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
