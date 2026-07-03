from phone.constants import CarrierChoices

HOST_11st = "https://api.11st.co.kr/rest"

# 기본 옵션(0원) = 상품 등록 기준이 되는 각 통신사 최상위 요금제.
# 옵션명은 DB Plan.name(현행 요금제명)과 표기를 맞춘다.
CARRIER_TO_DEFAULT_PLAN_NAME = {
    CarrierChoices.SK: "베스트 Max",
    CarrierChoices.KT: "초이스 130",
    CarrierChoices.LG: "플러스플랜 130",
}

# 11번가 옵션 push 시 사용하는 통신사별 마진(원). 상품 등록/동기화 표준값.
# 옵션 목록/가격 계산(SetOptions11ST)의 기준이 되므로, 재push 시에도 동일 값을 사용해야
# 기존 옵션 구성이 그대로 유지된다.
OM_MARGIN_BY_CARRIER = {
    CarrierChoices.SK: 10_000,
    CarrierChoices.LG: 10_000,
    CarrierChoices.KT: 30_000,
}
