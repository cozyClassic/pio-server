from django.core.management.base import BaseCommand

from phone.models import Device, DeviceVariant

# model_name(Device.model_name과 정확히 일치) → {storage_capacity: gtin}
# 아이폰 Air, 그 외 미제공 기기는 GTIN 없음 — 추후 확보 시 이 맵에 추가.
# GTIN 값은 실물 박스 대조 권장(특히 웹검색으로 수집한 값).
GTIN_MAP = {
    "갤럭시S26": {"256": "8806097835578", "512": "8806097835882"},
    "갤럭시S26+": {"256": "8806097836803", "512": "8806097836742"},
    "갤럭시S26 Ultra": {"256": "8806097829119"},
    "갤럭시S25": {"256": "8806095848433"},
    "갤럭시S25 Ultra": {"256": "8806095822709"},
    "갤럭시 Z 플립7": {"256": "8806097448266", "512": "8806097492146"},
    "아이폰17 Pro": {"256": "195950627138", "512": "195950627732"},
    "아이폰17": {"256": "195950622591", "512": "195950623796"},
    "아이폰16": {"128": "195949822049", "256": "195949822940"},
}


class Command(BaseCommand):
    help = (
        "GTIN_MAP에 정의된 매핑대로 DeviceVariant.gtin을 채운다. "
        "재실행 가능(멱등): 이미 gtin 값이 있는 variant는 admin 입력을 존중해 건너뛴다. "
        "--dry-run으로 실제 저장 없이 변경 예정 내역만 확인할 수 있다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 저장하지 않고 변경 예정 내역만 출력",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        set_count = 0
        skip_count = 0
        missing_count = 0

        for model_name, storage_gtin_map in GTIN_MAP.items():
            devices = list(
                Device.objects.filter(
                    model_name=model_name, deleted_at__isnull=True
                )
            )

            if not devices:
                self.stdout.write(
                    self.style.WARNING(
                        f"[매칭 실패] Device 없음: model_name={model_name!r}"
                    )
                )
                missing_count += len(storage_gtin_map)
                continue

            for device in devices:
                for storage_capacity, gtin in storage_gtin_map.items():
                    variant = (
                        DeviceVariant.objects.filter(
                            device=device,
                            storage_capacity=storage_capacity,
                            deleted_at__isnull=True,
                        )
                        .first()
                    )

                    if variant is None:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[매칭 실패] DeviceVariant 없음: "
                                f"model_name={model_name!r} storage={storage_capacity!r}"
                            )
                        )
                        missing_count += 1
                        continue

                    if variant.gtin:
                        self.stdout.write(
                            f"[스킵] 이미 값 있음: model_name={model_name!r} "
                            f"storage={storage_capacity!r} "
                            f"variant_id={variant.id} 기존 gtin={variant.gtin!r}"
                        )
                        skip_count += 1
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"[변경 예정] model_name={model_name!r} "
                            f"storage={storage_capacity!r} "
                            f"variant_id={variant.id} gtin={gtin!r}"
                        )
                    else:
                        # variant.save() 대신 queryset .update() 사용:
                        # DeviceVariant.save() 오버라이드가 연결된 ProductOption들의
                        # final_price 재계산·저장(→ 시그널 → best_price_option 갱신)이라는
                        # 무거운 사이드이펙트를 유발함. GTIN만 채우는 데 가격 재계산이
                        # 도는 것은 불필요하고, Merchant 가격 정합상 피해야 한다.
                        DeviceVariant.objects.filter(id=variant.id).update(gtin=gtin)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[설정] model_name={model_name!r} "
                                f"storage={storage_capacity!r} "
                                f"variant_id={variant.id} gtin={gtin!r}"
                            )
                        )
                    set_count += 1

        self.stdout.write("")
        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}요약 - 설정 {set_count}건 / "
                f"스킵(이미 값 있음) {skip_count}건 / "
                f"매칭 실패(기기·변형 없음) {missing_count}건"
            )
        )
