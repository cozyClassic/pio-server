import openpyxl
from phone.models import Inventory, Dealership
from phone.constants import CarrierChoices
from traceback import print_exc, format_exc


"""엑셀 양식
row3 - (헤더)
row4 - (데이터 시작)
(단말기명, 색상명, 개수)
단말기명> - AIP16-128BE 처럼 모델명-용량-색상코드 형태
NSO같이 유통향 말고 직구모델이 있는데, 퍼스트는 직구모델이 거의 없어서 일단 제외함 - 이런 직구모델을 추가하려면 DB에 쉼표로 추가하기.

단말기명이 비어있는 row가 있으면 중지하고 그 전까지의 데이터만 읽음
또, 단말기명이 있고 개수가 0이 아닌데 DB의 데이터와 매칭이 안되는 경우에는
따로 필드명을 저장해서 admin에 message로 띄워줘야 함
"""

"""연동 방법
(Phone.Inventory 테이블 필드) <-> (엑셀 필드명)
(name_in_sheet) = (단말기명)
(color_in_sheet) = (색상명)
(count) = (개수)
만약 엑셀에 없으면, 해당 dealer의 나머지 재고를 모두 0으로 세팅해야 함.
"""


def read_inventory_excel(file_path):
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active

    inventory_data = []

    for row in sheet.iter_rows(min_row=4, values_only=True):
        device_name = row[0]  # 단말기명
        color_name = row[1]  # 색상명
        count = row[2]  # 개수

        if (
            device_name is None
            or color_name is None
            or color_name.strip() == ""
            or device_name.strip() == ""
            or device_name == "총합계"
        ):
            continue

        inventory_data.append(
            {
                "name_in_sheet": device_name,
                "color_in_sheet": color_name,
                "count": count if count is not None else 0,
            }
        )

    return inventory_data


def update_inventory(dealer, inventory_data):
    DEALER = Dealership.objects.get(name="퍼스트", carrier=CarrierChoices.KT)
    old_datas = Inventory.objects.filter(dealership=DEALER)
    inventory_name_color_to_object = dict()
    for data in old_datas:
        names = data.name_in_sheet.split(",")
        colors = data.color_in_sheet.split(",")
        for name in names:
            for color in colors:
                key = name + "_" + color
                inventory_name_color_to_object[key] = data

        data.count = 0

    not_matched = []

    for item in inventory_data:
        key = item["name_in_sheet"] + "_" + item["color_in_sheet"]
        if key in inventory_name_color_to_object:
            inventory_obj = inventory_name_color_to_object[key]
            inventory_obj.count += item["count"]

        else:
            not_matched.append(
                f"{item['name_in_sheet']} - {item['color_in_sheet']} : {item['count']}"
            )

    Inventory.objects.bulk_update(old_datas, ["count"])

    return not_matched
