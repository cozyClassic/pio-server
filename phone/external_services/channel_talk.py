import requests
from phoneinone_server.settings import (
    CHANENLTALK_ACCESS_KEY,
    CHANENLTALK_ACCESS_SECRET,
    DEBUG,
)


def send_order_alert(order_id: str, customer_name: str, customer_phone: str) -> None:
    """Send a message to the team via Channel Talk."""
    # Implementation for sending message via Channel Talk
    ORDER_ALERT_GROUP_ID = "501418" if DEBUG else "501406"
    response = requests.post(
        url=f"https://api.channel.io/open/v5/groups/{ORDER_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": f"주문 알림: {order_id}, {customer_name}, {customer_phone}",
                },
            ]
        },
        headers={
            "Content-Type": "application/json",
            "x-access-key": CHANENLTALK_ACCESS_KEY,
            "x-access-secret": CHANENLTALK_ACCESS_SECRET,
        },
    )
    return response.json()
