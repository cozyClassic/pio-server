import openpyxl
import io
from ..models import DeviceVariant, OfficialContractLink, Delearship
from phone.constants import ContractTypeChoices
from django.utils import timezone


HEADERS = {
    "dv_id": "Device Variant ID",
    "model_name": "Model Name",
    "용량": "Capacity",
    "SK_기변": "디아이 기변 공식링크",
    "SK_번이": "디아이 번이 공식링크",
    "KT_기변": "퍼스트 기변 공식링크",
    "KT_번이": "퍼스트 번이 공식링크",
    "LG_기변": "휴넷 기변 공식링크",
    "LG_번이": "휴넷 번이 공식링크",
}


def update_official_contract_link(fileName: str) -> None:
    """기능
    1. 엑셀 파일을 읽어온다.
    2. 각 행을 읽어와서 device_variant_id로 DeviceVariant를 찾는다.
    3. OfficialContractLink가 존재하면 업데이트, 없으면 생성한다.
    """

    dealers = Delearship.objects.all()
    sk = dealers.filter(carrier="SK").first()  # 디아이
    kt = dealers.filter(carrier="KT").first()  # 퍼스트
    lg = dealers.filter(carrier="LG").first()  # 휴넷

    wb = openpyxl.load_workbook(fileName, data_only=True)
    ws = wb.active

    for row in ws.iter_rows(min_row=2):  # 헤더 행 제외
        dv_id = row[0].value
        sk_change_link = row[3].value
        sk_mnp_link = row[4].value
        kt_change_link = row[5].value
        kt_mnp_link = row[6].value
        lg_change_link = row[7].value
        lg_mnp_link = row[8].value

        try:
            device_variant = DeviceVariant.objects.get(id=dv_id)
        except DeviceVariant.DoesNotExist:
            continue  # DeviceVariant가 없으면 건너뜀

        # default: device_variant, delear, contract_type
        # update_or_create: link
        if sk_change_link:
            OfficialContractLink.objects.update_or_create(
                device_variant=device_variant,
                delear=sk,
                contract_type=ContractTypeChoices.CHANGE,
                defaults={"link": sk_change_link, "updated_at": timezone.now()},
            )
        if sk_mnp_link:
            OfficialContractLink.objects.update_or_create(
                device_variant=device_variant,
                delear=sk,
                contract_type=ContractTypeChoices.MNP,
                defaults={"link": sk_mnp_link, "updated_at": timezone.now()},
            )
        if kt_change_link:
            OfficialContractLink.objects.update_or_create(
                device_variant=device_variant,
                delear=kt,
                contract_type=ContractTypeChoices.CHANGE,
                defaults={"link": kt_change_link, "updated_at": timezone.now()},
            )
        if kt_mnp_link:
            OfficialContractLink.objects.update_or_create(
                device_variant=device_variant,
                delear=kt,
                contract_type=ContractTypeChoices.MNP,
                defaults={"link": kt_mnp_link, "updated_at": timezone.now()},
            )
        if lg_change_link:
            OfficialContractLink.objects.update_or_create(
                device_variant=device_variant,
                delear=lg,
                contract_type=ContractTypeChoices.CHANGE,
                defaults={"link": lg_change_link, "updated_at": timezone.now()},
            )
        if lg_mnp_link:
            OfficialContractLink.objects.update_or_create(
                device_variant=device_variant,
                delear=lg,
                contract_type=ContractTypeChoices.MNP,
                defaults={"link": lg_mnp_link, "updated_at": timezone.now()},
            )
    wb.close()
    return
