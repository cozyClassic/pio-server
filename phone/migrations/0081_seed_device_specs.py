# Generated data migration: 기기 주요 사양(스펙) 12종 시드
#
# 소스: pio-web lib/device-specs.ts 의 DEVICE_SPECS (제조사 공식 사양, 검증 2026-07).
# 마이그레이션은 서버에서 실행되므로 프론트 TS를 런타임에 읽을 수 없어
# 아래 DEVICE_SPECS 파이썬 리스트에 label/value/순서를 그대로 임베드한다.
from django.db import migrations

# (model_name, [(label, value), ...])  — items 순서가 곧 sort_order.
DEVICE_SPECS = [
    (
        "아이폰16",
        [
            ("디스플레이", "6.1형 Super Retina XDR OLED"),
            ("칩셋", "A18"),
            ("저장 용량", "128 / 256 / 512GB"),
            ("후면 카메라", "48MP 메인 + 12MP 초광각"),
            ("전면 카메라", "12MP"),
            ("방수·방진", "IP68"),
            ("운영체제", "iOS"),
            ("출시", "2024년 9월"),
        ],
    ),
    (
        "아이폰16 Pro",
        [
            ("디스플레이", "6.3형 Super Retina XDR OLED, ProMotion 120Hz"),
            ("칩셋", "A18 Pro"),
            ("저장 용량", "128 / 256 / 512GB / 1TB"),
            ("후면 카메라", "48MP 메인 + 48MP 초광각 + 12MP 망원(5배)"),
            ("전면 카메라", "12MP"),
            ("소재", "티타늄"),
            ("방수·방진", "IP68"),
            ("운영체제", "iOS"),
            ("출시", "2024년 9월"),
        ],
    ),
    (
        "아이폰16 Pro Max",
        [
            ("디스플레이", "6.9형 Super Retina XDR OLED, ProMotion 120Hz"),
            ("칩셋", "A18 Pro"),
            ("저장 용량", "256 / 512GB / 1TB"),
            ("후면 카메라", "48MP 메인 + 48MP 초광각 + 12MP 망원(5배)"),
            ("전면 카메라", "12MP"),
            ("소재", "티타늄"),
            ("방수·방진", "IP68"),
            ("운영체제", "iOS"),
            ("출시", "2024년 9월"),
        ],
    ),
    (
        "아이폰17",
        [
            ("디스플레이", "6.3형 Super Retina XDR OLED, ProMotion 120Hz"),
            ("칩셋", "A19"),
            ("저장 용량", "256 / 512GB"),
            ("후면 카메라", "48MP 메인 + 48MP 초광각"),
            ("전면 카메라", "18MP (Center Stage)"),
            ("방수·방진", "IP68"),
            ("운영체제", "iOS"),
            ("출시", "2025년 9월"),
        ],
    ),
    (
        "아이폰17 Pro",
        [
            ("디스플레이", "6.3형 Super Retina XDR OLED, ProMotion 120Hz"),
            ("칩셋", "A19 Pro"),
            ("저장 용량", "256 / 512GB / 1TB"),
            ("후면 카메라", "48MP 메인 + 48MP 초광각 + 48MP 망원(4배, 광학 수준 8배 줌)"),
            ("전면 카메라", "18MP (Center Stage)"),
            ("소재", "알루미늄"),
            ("방수·방진", "IP68"),
            ("운영체제", "iOS"),
            ("출시", "2025년 9월"),
        ],
    ),
    (
        "아이폰 Air",
        [
            ("디스플레이", "6.5형 Super Retina XDR OLED, ProMotion 120Hz"),
            ("칩셋", "A19 Pro"),
            ("저장 용량", "256 / 512GB / 1TB"),
            ("후면 카메라", "48MP 메인 단일 렌즈 (광학 수준 2배 망원 크롭 지원)"),
            ("전면 카메라", "18MP (Center Stage)"),
            ("소재", "티타늄"),
            ("방수·방진", "IP68"),
            ("운영체제", "iOS"),
            ("출시", "2025년 9월"),
        ],
    ),
    (
        "갤럭시S25",
        [
            ("디스플레이", "6.2형 Dynamic AMOLED 2X, 120Hz"),
            ("칩셋", "스냅드래곤 8 Elite for Galaxy"),
            ("메모리·저장", "12GB RAM / 128·256·512GB"),
            ("후면 카메라", "50MP 메인 + 12MP 초광각 + 10MP 망원(3배)"),
            ("전면 카메라", "12MP"),
            ("배터리", "4,000mAh"),
            ("방수·방진", "IP68"),
            ("운영체제", "안드로이드 (One UI)"),
            ("출시", "2025년 1월"),
        ],
    ),
    (
        "갤럭시S25 Ultra",
        [
            ("디스플레이", "6.9형 Dynamic AMOLED 2X, 120Hz"),
            ("칩셋", "스냅드래곤 8 Elite for Galaxy"),
            ("메모리·저장", "12GB RAM / 256·512GB·1TB"),
            (
                "후면 카메라",
                "200MP 메인 + 50MP 초광각 + 50MP 망원(5배) + 10MP 망원(3배)",
            ),
            ("전면 카메라", "12MP"),
            ("배터리", "5,000mAh"),
            ("입력", "S펜 내장"),
            ("방수·방진", "IP68"),
            ("운영체제", "안드로이드 (One UI)"),
            ("출시", "2025년 1월"),
        ],
    ),
    (
        "갤럭시S26",
        [
            ("디스플레이", "6.3형 Dynamic AMOLED 2X, 120Hz"),
            ("칩셋", "엑시노스 2600"),
            ("메모리·저장", "12GB RAM / 256·512GB"),
            ("후면 카메라", "50MP 메인 + 12MP 초광각 + 10MP 망원(3배)"),
            ("전면 카메라", "12MP"),
            ("배터리", "4,300mAh"),
            ("방수·방진", "IP68"),
            ("운영체제", "안드로이드 (One UI)"),
            ("출시", "2026년 2월"),
        ],
    ),
    (
        "갤럭시S26+",
        [
            ("디스플레이", "6.7형 Dynamic AMOLED 2X, 120Hz"),
            ("칩셋", "엑시노스 2600"),
            ("메모리·저장", "12GB RAM / 256·512GB"),
            ("후면 카메라", "50MP 메인 + 12MP 초광각 + 10MP 망원(3배)"),
            ("전면 카메라", "12MP"),
            ("배터리", "4,900mAh"),
            ("방수·방진", "IP68"),
            ("운영체제", "안드로이드 (One UI)"),
            ("출시", "2026년 2월"),
        ],
    ),
    (
        "갤럭시S26 Ultra",
        [
            ("디스플레이", "6.9형 Dynamic AMOLED 2X, 120Hz"),
            ("칩셋", "스냅드래곤 8 Elite Gen 5 for Galaxy"),
            ("메모리·저장", "12·16GB RAM / 256·512GB·1TB"),
            (
                "후면 카메라",
                "200MP 메인 + 50MP 초광각 + 50MP 망원(5배) + 10MP 망원(3배)",
            ),
            ("전면 카메라", "12MP"),
            ("배터리", "5,000mAh"),
            ("입력", "S펜 내장"),
            ("방수·방진", "IP68"),
            ("운영체제", "안드로이드 (One UI)"),
            ("출시", "2026년 2월"),
        ],
    ),
    (
        "갤럭시 Z 플립7",
        [
            (
                "디스플레이",
                "6.9형 Dynamic AMOLED 2X 120Hz(메인) + 4.1형 커버 디스플레이(플렉스윈도우)",
            ),
            ("칩셋", "엑시노스 2500"),
            ("메모리·저장", "12GB RAM / 256·512GB"),
            ("후면 카메라", "50MP 메인 + 12MP 초광각"),
            ("전면 카메라", "10MP"),
            ("배터리", "4,300mAh"),
            ("방수·방진", "IP48"),
            ("운영체제", "안드로이드 (One UI)"),
            ("출시", "2025년 7월"),
        ],
    ),
]


def seed_device_specs(apps, schema_editor):
    Device = apps.get_model("phone", "Device")
    DeviceSpecItem = apps.get_model("phone", "DeviceSpecItem")

    for model_name, items in DEVICE_SPECS:
        devices = Device.objects.filter(
            model_name=model_name, deleted_at__isnull=True
        )
        for device in devices:
            # 재실행 안전: 해당 device에 spec이 하나도 없을 때만 시드한다.
            if DeviceSpecItem.objects.filter(device=device).exists():
                continue
            for sort_order, (label, value) in enumerate(items):
                DeviceSpecItem.objects.create(
                    device=device,
                    label=label,
                    value=value,
                    sort_order=sort_order,
                )


def unseed_device_specs(apps, schema_editor):
    Device = apps.get_model("phone", "Device")
    DeviceSpecItem = apps.get_model("phone", "DeviceSpecItem")

    model_names = [model_name for model_name, _ in DEVICE_SPECS]
    device_ids = Device.objects.filter(model_name__in=model_names).values_list(
        "id", flat=True
    )
    DeviceSpecItem.objects.filter(device_id__in=list(device_ids)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("phone", "0080_devicespecitem"),
    ]

    operations = [
        migrations.RunPython(seed_device_specs, unseed_device_specs),
    ]
