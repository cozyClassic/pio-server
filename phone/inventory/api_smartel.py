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

    def __str__(self):
        return f"{self.phone_name} - {self.color}"


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
                    color=item.get("color").replace(" ", ""),
                )
            )

        return result
    else:
        response.raise_for_status()


def update_inventory_counts(api_items):
    smartel_dealer = Dealership.objects.get(name="디아이")
    Inventory_objects = Inventory.objects.filter(dealership=smartel_dealer)
    update_counts = 0
    not_updated_datas = []
    db_dict = {}

    for db_item in Inventory_objects:
        db_dict[
            (
                db_item.name_in_sheet.replace(" ", ""),
                db_item.color_in_sheet.replace(" ", ""),
            )
        ] = db_item
        db_item.count = 0

    for api_item in api_items:
        api_key = (api_item.phone_name.replace(" ", ""), api_item.color)
        db_item = db_dict.get(api_key)
        if db_item:
            db_item.count = api_item.count
            update_counts += 1
        else:
            not_updated_datas.append(api_item)

    Inventory.objects.bulk_update(Inventory_objects, ["count"])
    return (not_updated_datas, update_counts)


def sync_smartel_inventory():
    inventory_items = fetch_smartel_inventory()
    return update_inventory_counts(inventory_items)
