"""재고에 따라 SSG 상품의 판매(전시)상태를 동기화한다.

기본은 판매중지 방향만 적용(재고 소진 → 판매중지). 재고가 확보된 상품의
판매재개는 --enable-resume 를 명시할 때만 실행한다(판매 개시 확정 후).

사용 예:
  # 재고 소진 상품만 판매중지 (재개 안 함)
  python manage.py sync_ssg_sales

  # 판매 개시 — 재고 확보 상품 판매재개까지 적용
  python manage.py sync_ssg_sales --enable-resume
"""

from django.core.management.base import BaseCommand

from phone.external_services.ssg.put_product.sync_sales_status import (
    sync_ssg_sales_status,
)


class Command(BaseCommand):
    help = "재고 기반 SSG 판매상태 동기화 (기본: 판매중지 방향만)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--enable-resume",
            action="store_true",
            help="재고 확보 상품의 판매재개까지 적용(판매 개시). 미지정 시 재개 안 함",
        )

    def handle(self, *args, **options):
        result = sync_ssg_sales_status(enable_resume=options["enable_resume"])
        self.stdout.write(
            self.style.SUCCESS(
                f"동기화 완료 — 대상 {result['checked']} / "
                f"판매중지 {result['stopped']} / 판매재개 {result['resumed']} / "
                f"재개보류 {result['skipped_resume']} / 실패 {result['failed']}"
            )
        )
        if not options["enable_resume"] and result["skipped_resume"]:
            self.stdout.write(
                f"※ 재고 확보돼 판매 가능한 {result['skipped_resume']}개는 재개 보류됨. "
                f"판매 개시하려면 --enable-resume 사용."
            )
