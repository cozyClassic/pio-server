# pyright: reportAttributeAccessIssue=false
"""11번가 상품 전시(판매)중지/재개 상태를 재고에 맞춰 일괄 정합한다.

배경
----
`OpenMarketProduct.is_display_stopped` 필드가 마이그레이션 기본값(False)으로
시드되어 11번가 실제 상태(전시중지)와 어긋난 '초기 드리프트'가 발생하면,
필드 기반 자동 sync(`sync_11st_display_status`)는 "이미 판매중"으로 착각해
전시재개 API를 호출하지 않는다.

이 커맨드는 필드 대신 **11번가 실제 상태(selStatCd)** 를 기준으로 비교하므로
드리프트에 영향을 받지 않는다. 각 상품에 대해:
  1) 통신사 일치 대리점 재고 합계로 목표 상태(desired) 계산
  2) 11번가 현재 상태(selStatCd) 조회
  3) 현재 != 목표 이면 stopdisplay/restartdisplay 호출
  4) is_display_stopped 필드를 목표 상태로 정합

사용 예:
    python manage.py sync_11st_display --dry-run          # 조회만, 변경 없음
    python manage.py sync_11st_display                    # 실제 반영
    python manage.py sync_11st_display --carrier SK       # SK만
    python manage.py sync_11st_display --id 120           # 특정 상품만
"""

from django.core.management.base import BaseCommand

from phone.constants import CarrierChoices, OpenMarketChoices
from phone.models import OpenMarketProduct
from phone.external_services.st_11.put_product.get_product_info import (
    get_display_status_code,
)
from phone.external_services.st_11.put_product.set_display_status import (
    restart_display,
    stop_display,
)
from phone.external_services.st_11.put_product.sync_display_status import (
    STOPPED_STATUS_CODE,
    _build_active_device_ids,
    _build_stock_map,
    _derive_carrier,
    compute_desired_stopped,
)


class Command(BaseCommand):
    help = (
        "11번가 상품의 전시(판매)중지/재개 상태를 재고에 맞춰 일괄 정합한다. "
        "11번가 실제 상태(selStatCd)를 기준으로 비교하므로 is_display_stopped 필드 "
        "드리프트에 영향받지 않는다. --dry-run 으로 먼저 영향 범위를 확인할 것."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="11번가/DB를 변경하지 않고 조회·판정 결과만 출력",
        )
        parser.add_argument(
            "--carrier",
            choices=[CarrierChoices.SK, CarrierChoices.KT, CarrierChoices.LG],
            default=None,
            help="특정 통신사 상품만 처리 (seller_code 기준)",
        )
        parser.add_argument(
            "--id",
            type=int,
            default=None,
            help="특정 OpenMarketProduct 내부 ID 하나만 처리",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="처음 N개만 처리 (기본: 전체)",
        )

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]

        qs = (
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.ST11,
                device_variant__isnull=False,
                om_product_id__isnull=False,
            )
            .exclude(om_product_id="")
            .select_related("device_variant__device")
            .order_by("id")
        )
        if opts["carrier"]:
            qs = qs.filter(seller_code__contains=opts["carrier"])
        if opts["id"] is not None:
            qs = qs.filter(id=opts["id"])

        products = list(qs)
        if opts["limit"] is not None:
            products = products[: opts["limit"]]

        stock_map = _build_stock_map({p.device_variant_id for p in products})
        active_device_ids = _build_active_device_ids()

        total = len(products)
        mode = "DRY-RUN (변경 없음)" if dry_run else "APPLY (실제 반영)"
        self.stdout.write(f"[{mode}] 대상 11번가 상품 수: {total}\n")

        counters = {
            "RESTARTED": 0,  # 전시중지 -> 재개
            "STOPPED": 0,  # 판매중 -> 전시중지
            "ALREADY_OK": 0,  # 이미 목표 상태
            "SKIP_NO_CARRIER": 0,
            "ERROR": 0,
        }

        for i, p in enumerate(products, 1):
            prefix = f"[{i}/{total}] id={p.id} prdNo={p.om_product_id} {p.name}"
            carrier = _derive_carrier(p.seller_code)
            if carrier is None:
                counters["SKIP_NO_CARRIER"] += 1
                self.stderr.write(
                    f"{prefix} SKIP 통신사판별불가 seller_code={p.seller_code!r}"
                )
                continue

            stock = stock_map.get((p.device_variant_id, carrier), 0)
            device_active = p.device_variant.device_id in active_device_ids
            desired_stopped = compute_desired_stopped(stock, device_active)

            try:
                actual_code = get_display_status_code(p.om_product_id)
            except Exception as e:
                counters["ERROR"] += 1
                self.stderr.write(f"{prefix} ERROR 상태조회실패: {e}")
                continue

            actual_stopped = actual_code == STOPPED_STATUS_CODE
            tag = (
                f"{carrier} 재고={stock} 활성={'Y' if device_active else 'N'} "
                f"11st상태={actual_code} 목표={'중지' if desired_stopped else '판매'}"
            )

            if actual_stopped == desired_stopped:
                counters["ALREADY_OK"] += 1
                # 필드가 실제와 어긋나 있으면 조용히 정합
                if not dry_run and p.is_display_stopped != desired_stopped:
                    p.is_display_stopped = desired_stopped
                    p.save(update_fields=["is_display_stopped", "updated_at"])
                self.stdout.write(f"{prefix} OK {tag}")
                continue

            action = "RESTARTED" if not desired_stopped else "STOPPED"
            if dry_run:
                counters[action] += 1
                self.stdout.write(
                    self.style.WARNING(f"{prefix} 변경예정→{action} {tag}")
                )
                continue

            try:
                if desired_stopped:
                    stop_display(p.om_product_id)
                else:
                    restart_display(p.om_product_id)
                p.is_display_stopped = desired_stopped
                p.save(update_fields=["is_display_stopped", "updated_at"])
                counters[action] += 1
                self.stdout.write(self.style.SUCCESS(f"{prefix} {action} {tag}"))
            except Exception as e:
                counters["ERROR"] += 1
                self.stderr.write(f"{prefix} ERROR {action} 실패: {e}")

        self.stdout.write(
            "\n결과 - "
            f"재개: {counters['RESTARTED']}, "
            f"중지: {counters['STOPPED']}, "
            f"이미정상: {counters['ALREADY_OK']}, "
            f"통신사판별불가: {counters['SKIP_NO_CARRIER']}, "
            f"에러: {counters['ERROR']}"
        )
