import requests
from phoneinone_server.settings import SMARTEL_INVENTORY_API_KEY
from phone.models import Inventory, Dealership

REQUEST_URL = "https://api2.smartel.kr/admin/inventory"


class SmartelInventoryItem:
    def __init__(
        self,
        phone_name,
        count,
        color,
    ):
        self.phone_name = phone_name
        self.count = count
        self.color = color


def fetch_smartel_inventory():
    response = requests.get(
        REQUEST_URL, headers={"x-api-key": SMARTEL_INVENTORY_API_KEY}
    )
    result = []
    if response.status_code == 200:
        datas = response.json()
        for item in datas:
            result.append(
                SmartelInventoryItem(
                    phone_name=item.get("phoneName"),
                    count=item.get("count"),
                    color=item.get("color"),
                )
            )

        return result
    else:
        response.raise_for_status()


def update_inventory_counts(inventory_items):
    smartel_dealer = Dealership.objects.get(name="디아이")
    Inventory_objects = Inventory.objects.filter(dealership=smartel_dealer)
    inventory_dict = {
        (inv.name_in_sheet.replace(" ", ""), inv.color_in_sheet): inv
        for inv in Inventory_objects
    }

    for item in inventory_items:
        key = (item.phone_name.replace(" ", ""), item.color)
        inventory = inventory_dict.get(key)
        if inventory:
            inventory.count = item.count

    Inventory.objects.bulk_update(Inventory_objects, ["count"])


def sync_smartel_inventory():
    inventory_items = fetch_smartel_inventory()
    update_inventory_counts(inventory_items)
