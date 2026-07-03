"""Google Merchant API로 활성 상품을 등록/갱신한다.

사용 예:
    # 크리덴셜/패키지 없이 페이로드만 검증 (권장 첫 단계)
    python manage.py push_google_merchant --dry-run --limit 3

    # 실제 전송
    python manage.py push_google_merchant
"""

from django.core.management.base import BaseCommand

from phone.external_services.google_merchant.sync import push


class Command(BaseCommand):
    help = "Google Merchant API로 활성 상품을 등록/갱신한다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="API를 호출하지 않고 페이로드만 출력(패키지/크리덴셜 불필요).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="처리할 최대 상품 수(검증용).",
        )

    def handle(self, *args, **options):
        summary = push(
            dry_run=options["dry_run"],
            limit=options["limit"],
            stdout=self.stdout,
        )
        style = self.style.SUCCESS if summary["failed"] == 0 else self.style.WARNING
        self.stdout.write(
            style(
                f"완료 — ok={summary['ok']} skipped={summary['skipped']} "
                f"failed={summary['failed']}"
            )
        )
        for err in summary["errors"]:
            self.stdout.write(
                self.style.ERROR(f"  product={err['product_id']}: {err['error']}")
            )
