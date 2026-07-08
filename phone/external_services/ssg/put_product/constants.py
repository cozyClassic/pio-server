"""SSG 상품등록에 필요한 계약/카테고리/배송 상수.

값들은 벤더 API로 실조회한 계약 정보 기준 (2026-07):
- 표준카테고리: venInfo/0.2/listStdCtgKeyPath (계약 카테고리 목록)
- 전시카테고리: common/0.1/displayCategory (siteNo 6005/6004 휴대폰 트리)
- 브랜드: venInfo/0.1/listBrand
- 배송/고시: 기존 수동 등록 상품(itemId 1000793710193)에서 검증된 값 재사용
"""

from phone.constants import CarrierChoices, ContractTypeChoices

# 판매 사이트 (itemBase.sites)
SITE_EMART = 6001
SITE_SHINSEGAE = 6004
# 전시카테고리 전용 사이트
SITE_SSGCOM = 6005
SITE_GROCERY = 7018  # 이마트몰(6001) 등록 시 그로서리몰 전시카테고리 필수

# 완납가입 표준카테고리 (컴퓨터/디지털 > 휴대폰 > {통신사} > {통신사} 완납가입)
STD_CTG_FULL_PAYMENT = {
    CarrierChoices.SK: 1000034434,
    CarrierChoices.KT: 1000034436,
    CarrierChoices.LG: 1000034438,
}

BRAND_ID = {
    "삼성": 2000015365,
    "애플": 2000000375,
}

# 전시카테고리: {siteNo: {carrier: {contract_type: dispCtgId}}}
# 6005(SSG.COM)는 필수. 6004(신세계몰)는 매핑룰이 없는 조합이 있어 명시 등록.
# 7018(그로서리몰)은 스마트폰 단일 카테고리.
DISP_CTG = {
    SITE_SSGCOM: {
        CarrierChoices.SK: {
            ContractTypeChoices.NEW: 6000208968,
            ContractTypeChoices.MNP: 6000208971,
            ContractTypeChoices.CHANGE: 6000208974,
        },
        CarrierChoices.KT: {
            ContractTypeChoices.NEW: 6000208967,
            ContractTypeChoices.MNP: 6000208970,
            ContractTypeChoices.CHANGE: 6000208973,
        },
        CarrierChoices.LG: {
            ContractTypeChoices.NEW: 6000208969,
            ContractTypeChoices.MNP: 6000208972,
            ContractTypeChoices.CHANGE: 6000208975,
        },
    },
    SITE_SHINSEGAE: {
        CarrierChoices.SK: {
            ContractTypeChoices.NEW: 6000209541,
            ContractTypeChoices.MNP: 6000209544,
            ContractTypeChoices.CHANGE: 6000209547,
        },
        CarrierChoices.KT: {
            ContractTypeChoices.NEW: 6000209540,
            ContractTypeChoices.MNP: 6000209543,
            ContractTypeChoices.CHANGE: 6000209546,
        },
        CarrierChoices.LG: {
            ContractTypeChoices.NEW: 6000209542,
            ContractTypeChoices.MNP: 6000209545,
            ContractTypeChoices.CHANGE: 6000209548,
        },
    },
}
GROCERY_DISP_CTG_ID = 6000214796  # 디지털/가전/렌탈 > 휴대폰/액세서리 > 스마트폰

# 배송 정보 — 판매자센터에 등록된 배송비정책/출고지/반품지 ID (기존 상품 검증값)
DELIVERY_SHIPPING_METHODS = {
    "shppMainCd": 41,
    "shppMthdCd": 20,
    "shppItemDivCd": "01",
    "hcallOperTypeCd": "00",
    "shppRqrmDcnt": 2,
    "tdShppPsblYn": "N",
    "whoutShppcstId": "0083130705",
    "retShppcstId": "0083130706",
    "whoutAddrId": "0102344275",
    "snbkAddrId": "0102344275",
    "mareaShppYn": "N",
    "jejuShppDisabYn": "N",
    "ismtarShppDisabYn": "N",
}

# 상품정보고시 — 기존 상품이 승인받은 클래스/속성 구성 재사용.
# {model_spec}에 "품명/모델코드" 등 기기 가변값이 들어간다.
NOTIFICATION_CLASS_ID = "0000000012"
NOTIFICATION_PROP_NAME_MODEL = "0000000022"  # 품명 및 모델명
NOTIFICATION_PROP_KC_CERT = "0000000416"  # KC 인증정보
NOTIFICATION_PROP_RELEASE_YM = "0000000032"  # 동일모델의 출시년월 (YYMMDD/YYMM)
NOTIFICATION_PROP_SIZE_WEIGHT = "0000000037"  # 크기, 무게
NOTIFICATION_PROP_MANUFACTURER = "0000000007"  # 제조사
NOTIFICATION_PROP_IMPORTER = "0000000009"  # 수입자
NOTIFICATION_STATIC_PROPS = [
    {"itemMngPropId": "0000000038", "itemMngCntt": "해당없음"},  # 수입신고 관련
    {"itemMngPropId": "0000000008", "itemMngCntt": "Y"},  # 수입여부
    {"itemMngPropId": "0000000020", "itemMngCntt": "상세페이지 참조"},  # 제품주요사양
    {
        "itemMngPropId": "0000000006",
        "itemMngCntt": "관련 법 및 소비자 분쟁해결 규정에 따름",
    },  # 품질보증기준
    {"itemMngPropId": "0000000012", "itemMngCntt": "상세페이지 참조"},  # A/S 책임자
    {"itemMngPropId": "0000000011", "itemMngCntt": 1000000005},  # 제조국(코드)
]

# device_id -> SSG 대표이미지 소스 폴더 (BASE_DIR 기준 상대경로).
# 폴더 이미지는 고해상도(1200+) 원본. 매핑에 없는 기기(예: S25/S25Ultra)는
# 기존 DevicesColorImage로 폴백한다. 폴더 파일명 정렬 순서 = 노출 순서.
DEVICE_IMAGE_DIRS = {
    5: "temp/zflip7",  # 갤럭시 Z 플립7
    26: "temp/s26",  # 갤럭시 S26
    27: "temp/s26_plus",  # 갤럭시 S26+
    28: "temp/s26_ultra",  # 갤럭시 S26 Ultra
    20: "temp/iphone17",  # 아이폰17
    22: "temp/iphone17_pro",  # 아이폰17 Pro
    21: "temp/iphone_air",  # 아이폰 Air
}

# 옵션(요금제) 관련
OPTION_TYPE_NAME = "요금제"
OPTION_STOCK_QTY = 10  # 11번가 colCount=10과 동일한 상시 재고값
# SSG는 옵션가 0원이 불가해 최상위 요금제(최저가 옵션)도 최소가로 등록한다.
MIN_SELL_PRICE = 100
