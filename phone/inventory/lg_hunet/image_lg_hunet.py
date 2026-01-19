import json
from google import genai

from phoneinone_server.settings import GEMINI_API_KEY
from phone.models import Inventory, Dealership
from phone.constants import CarrierChoices


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


def extract_json_from_image(file_path: str):
    client = genai.Client(api_key=GEMINI_API_KEY)
    image = client.files.upload(file=file_path)
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[
            image,
            """
[역할]: 엑셀 이미지 내 텍스트 추출 전문가
[규칙]:
1. 서론/결론 생략 (인사말, "도움이 되길 바랍니다" 등 금지).
2. JSON 형태의 답변만 반환
3. 불필요한 수식어 배제.
[출력형식]: JSON
[참고]: {"UIPA_512(아이폰 에어 512G)": [["스카이블루", 16], ["스페이스 블랙", 2], ["클라우드 화이트", 3]]} - 단말기명 row가 KEY, [색상, 수량] 형태의 리스트가 VALUE
---
[입력내용]: 주어진 이미지에서 텍스트를 추출해. 엑셀 캡쳐본이라 줄로 나뉘어 있어. 단, 규칙과 출력형식을 반드시 준수해야 하고, 다른 형식으로 답변하면 안돼.
만약 이전에 주어진 이미지가 있더라도, 오직 지금 주어진 이미지에서만 텍스트를 추출해야 해.
""",
        ],
    )
    json_data = json.loads(response.text.replace("```", "").replace("json\n", ""))
    # 단말기명에서 모든 공백 제거 필요
    # ex) "UIPA 512(아이폰 에어 512G)" -> "UIPA_512(아이폰에어512G)"
    # KEY = 단말기명_색상, VALUE = 수량
    cleaned_data = dict()
    for device_name, color_list in json_data.items():
        cleaned_device_name = device_name.replace(" ", "")
        for color_name, count in color_list:
            key = f"{cleaned_device_name}_{color_name.replace(' ', '')}"
            cleaned_data[key] = count

    return cleaned_data


def update_inventory(inventory_data: dict[str, int]):
    DEALER = Dealership.objects.get(name="엘비휴넷", carrier=CarrierChoices.LG)
    old_datas = Inventory.objects.filter(dealership=DEALER)
    inventory_name_color_to_object = dict()
    for data in old_datas:
        names = data.name_in_sheet.split(",")
        colors = data.color_in_sheet.split(",")
        for name in names:
            for color in colors:
                key = f"{name}_{color.replace(' ', '')}"
                inventory_name_color_to_object[key] = data

        data.count = 0

    not_matched = []

    for key, count in inventory_data.items():
        if key in inventory_name_color_to_object:
            inventory_obj = inventory_name_color_to_object[key]
            inventory_obj.count += count
        else:
            not_matched.append(f"{key} : {count}")

    Inventory.objects.bulk_update(old_datas, ["count"])

    return not_matched
