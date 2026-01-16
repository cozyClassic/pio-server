import requests
from phoneinone_server.settings import SMARTEL_INVENTORY_API_KEY

REQUEST_URL = "https://api2.smartel.kr/admin/inventory"


class SmartelInventoryItem:
    def __init__(
        self,
        id,
        model_name,
        phone_name,
        count,
        color,
    ):
        self.id = id
        self.model_name = model_name
        self.phone_name = phone_name
        self.count = count
        self.color = color


def fetch_smartel_inventory():
    response = requests.get(
        REQUEST_URL, headers={"x-api-key": SMARTEL_INVENTORY_API_KEY}
    )
    if response.status_code == 200:
        return response.json()

    else:
        response.raise_for_status()


def parse_smartel_inventory(soup):
    inventory_items = []
    items = soup.find_all("ul", class_="py-2")
