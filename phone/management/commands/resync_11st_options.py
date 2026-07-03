from django.core.management.base import BaseCommand

from phone.constants import OpenMarketChoices
from phone.models import OpenMarketProduct
from phone.external_services.st_11.api import OM_MARGIN_BY_CARRIER
from phone.external_services.st_11.put_product.set_options import SetOptions11ST


class Command(BaseCommand):
    help = (
        "11번가 등록 상품들의 옵션(요금제)을 DB Plan.name 기준으로 재구성해 재push한다. "
        "요금제명 변경분을 기존 상품에 반영하기 위한 커맨드이며, 옵션 목록/가격 계산은 현행 로직 "
        "그대로이고 표기 이름만 최신 name으로 갱신된다. 통신사별 마진은 api.OM_MARGIN_BY_CARRIER "
        "표준값을 사용한다."
    )

    def add_arguments(self, parser):
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
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="11번가 update API는 호출하지 않고 전송될 옵션명/가격만 출력",
        )
        parser.add_argument(
            "--om-margin",
            type=int,
            default=None,
            help="통신사별 표준 마진 대신 지정 마진(원)으로 전 상품 통일 (검증/실험용)",
        )

    def handle(self, *args, **opts):
        qs = (
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.ST11,
                om_product_id__isnull=False,
            )
            .exclude(om_product_id="")
            .order_by("id")
        )

        if opts["id"] is not None:
            qs = qs.filter(id=opts["id"])
        if opts["limit"] is not None:
            qs = qs[: opts["limit"]]

        products = list(qs)
        total = len(products)
        mode = "DRY (API 미호출)" if opts["dry_run"] else "PUSH"
        self.stdout.write(f"[{mode}] 대상 11번가 상품 수: {total}")

        success_count = 0
        fail_count = 0

        for i, om in enumerate(products, 1):
            prefix = f"[{i}/{total}] id={om.id} prdNo={om.om_product_id}"
            try:
                carrier = om.get_carrier()
                margin = (
                    opts["om_margin"]
                    if opts["om_margin"] is not None
                    else OM_MARGIN_BY_CARRIER[carrier]
                )
                summary = SetOptions11ST.set_om_options(
                    om.id, margin=margin, dry_run=opts["dry_run"]
                )
                self._print_summary(prefix, summary, margin, dry_run=opts["dry_run"])
                success_count += 1
            except Exception as e:
                fail_count += 1
                self.stderr.write(f"{prefix} FAIL: {e}")

        self.stdout.write(
            f"\n[{mode}] 결과 - 성공: {success_count}, 실패: {fail_count}"
        )

    def _print_summary(
        self, prefix: str, summary: dict, margin: int, dry_run: bool
    ) -> None:
        tag = "DRY" if dry_run else "OK"
        carrier = summary["carrier"]
        default_name = summary["default_plan_name"]
        options = summary["options"]

        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix} [{carrier}] {tag} margin={margin:,} "
                f"기본옵션(0원)={default_name!r} 유료옵션 {len(options)}개"
            )
        )
        for name, opt_price in options:
            self.stdout.write(f"    - {name!r}  (+{opt_price:,})")
