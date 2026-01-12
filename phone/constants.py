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
