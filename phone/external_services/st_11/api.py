from phone.constants import CarrierChoices

HOST_11st = "https://api.11st.co.kr/rest"

CARRIER_TO_DEFAULT_PLAN_NAME = {
    CarrierChoices.SK: "플래티넘",
    CarrierChoices.KT: "초이스 프리미엄",
    CarrierChoices.LG: "프리미어 시그니처",
}
