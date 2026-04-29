class DiscountTypeChoices(object):
    SUBSIDY = "공시지원금"
    SELECTION = "선택약정"
    CHOICES = [
        (SUBSIDY, "공시지원금"),
        (SELECTION, "선택약정"),
    ]


class CarrierChoices(object):
    SK = "SK"
    KT = "KT"
    LG = "LG"
    MVNO = "알뜰폰"
    CHOICES = [
        (SK, "SK"),
        (KT, "KT"),
        (LG, "LG"),
        (MVNO, "알뜰폰"),
    ]
    VALUES = [SK, KT, LG, MVNO]


class ContractTypeChoices(object):
    NEW = "신규"
    MNP = "번호이동"
    CHANGE = "기기변경"
    CHOICES = [
        (NEW, "신규"),
        (MNP, "번호이동"),
        (CHANGE, "기기변경"),
    ]
    VALUES = [NEW, MNP, CHANGE]


CREDIT_CHECK_AGREE_LINK = {
    "SK": "",
    "KT": "https://www.kt.com/creditCheck/creditCheckMain.kt",
    "LG": "https://www.lguplus.co.kr/creditCheck/creditCheckMain.lguplus",
}


class CardSlotChoices(object):
    INSTALLMENT = "할부"
    WIRELESS_BILLING = "무선청구"
    WIRED_BILLING = "유선청구"
    CHOICES = [
        (INSTALLMENT, "할부"),
        (WIRELESS_BILLING, "무선청구"),
        (WIRED_BILLING, "유선청구"),
    ]
    VALUES = [INSTALLMENT, WIRELESS_BILLING, WIRED_BILLING]


class FunnelVariantChoices(object):
    CONTROL = "control"
    V1 = "v1"
    V3 = "v3"
    CHOICES = [
        (CONTROL, "control"),
        (V1, "v1"),
        (V3, "v3"),
    ]
    VALUES = [CONTROL, V1, V3]


class ContactChannelChoices(object):
    PHONE = "phone"
    KAKAO = "kakao"
    CHOICES = [
        (PHONE, "phone"),
        (KAKAO, "kakao"),
    ]
    VALUES = [PHONE, KAKAO]


class WinnerChoices(object):
    PIO = "pio"
    SELFBUY = "selfBuy"
    OFFICIAL = "official"
    CHOICES = [
        (PIO, "pio"),
        (SELFBUY, "selfBuy"),
        (OFFICIAL, "official"),
    ]
    VALUES = [PIO, SELFBUY, OFFICIAL]


class IdentitySourceChoices(object):
    NAME_PHONE = "name_phone"
    NAVER_OAUTH = "naver_oauth"
    KAKAO_OAUTH = "kakao_oauth"
    CHOICES = [
        (NAME_PHONE, "name_phone"),
        (NAVER_OAUTH, "naver_oauth"),
        (KAKAO_OAUTH, "kakao_oauth"),
    ]
    VALUES = [NAME_PHONE, NAVER_OAUTH, KAKAO_OAUTH]


class OpenMarketChoices(object):
    ST11 = "11번가"
    GMK = "G마켓 옥션"
    SSG = "SSG"
    LTON = "롯데ON"
    N_COMP = "네이버 가격비교"
    Choices = [
        (ST11, "11번가"),
        (GMK, "G마켓 옥션"),
        (SSG, "SSG"),
        (LTON, "롯데ON"),
        (N_COMP, "네이버 가격비교"),
    ]

    VALUES = [ST11, GMK, SSG, LTON]
