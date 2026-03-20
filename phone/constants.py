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
