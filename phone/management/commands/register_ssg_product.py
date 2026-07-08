"""11번가 등록분을 원본으로 SSG(신세계)에 상품을 등록한다.

사용 예:
  # payload 미리보기 (API 호출 없음)
  python manage.py register_ssg_product --st11-id 210 --dry-run

  # 실제 등록
  python manage.py register_ssg_product --st11-id 210

  # 11번가 상품 목록에서 내부 ID 확인
  python manage.py register_ssg_product --list
"""

import json

from django.core.management.base import BaseCommand

from phone.constants import OpenMarketChoices
from phone.models import OpenMarketProduct


class Command(BaseCommand):
    help = "11번가 OpenMarketProduct를 원본으로 SSG에 상품 등록"

    def add_arguments(self, parser):
        parser.add_argument(
            "--st11-id",
            type=int,
            help="원본 11번가 OpenMarketProduct 내부 ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="payload만 출력하고 API는 호출하지 않음",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="등록 가능한 11번가 상품 목록 출력",
        )
        parser.add_argument(
            "--on-sale",
            action="store_true",
            help="판매중(20) 상태로 등록. 기본은 일시중지(80)로 등록 후 검수·재개",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="판매중(재고有+활성) 미등록 11번가 상품 전체를 3초 간격 등록",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="--all 등록 최대 개수 (테스트용)",
        )

    def handle(self, *args, **options):
        if options["list"]:
            self._print_st11_products()
            return

        if options["all"]:
            self._register_all(options)
            return

        st11_id = options["st11_id"]
        if not st11_id:
            self.stderr.write("--st11-id 또는 --list 를 지정하세요.")
            return

        if options["dry_run"]:
            from phone.external_services.ssg.put_product.register_item import (
                build_ssg_registration_from_11st,
            )

            context = build_ssg_registration_from_11st(
                st11_id, on_sale=options["on_sale"]
            )
            self.stdout.write(
                f"원본: [{context['st11_product'].id}] {context['st11_product'].name}"
            )
            self.stdout.write(
                f"통신사: {context['carrier']} / 계약: {context['contract_type']}"
                f" / 마진: {context['margin']:,}원"
                f" / 수수료: {context['ssg_market'].commision_rate_default:.0%}"
            )
            self.stdout.write(f"대표가(최저 옵션가): {context['registered_price']:,}원")
            self.stdout.write("--- payload ---")
            self.stdout.write(
                json.dumps(context["payload"], ensure_ascii=False, indent=2)
            )
            return

        from phone.external_services.ssg.put_product.register_item import (
            register_ssg_item,
        )

        ssg_product = register_ssg_item(st11_id, on_sale=options["on_sale"])
        self.stdout.write(
            self.style.SUCCESS(
                f"SSG 등록 완료 - itemId: {ssg_product.om_product_id}, "
                f"내부 ID: {ssg_product.id}, 대표가: {ssg_product.registered_price:,}원"
            )
        )

    def _register_all(self, options):
        import time

        from phone.external_services.ssg.put_product.register_item import (
            register_ssg_item,
        )

        registered = set(
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.SSG
            ).values_list("seller_code", flat=True)
        )
        targets = (
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.ST11,
                is_display_stopped=False,
                device_variant__isnull=False,
            )
            .select_related("device_variant__device")
            .order_by("id")
        )
        pending = [
            p
            for p in targets
            if (p.seller_code or "").replace("11ST", "SSG") not in registered
        ]
        if options["limit"]:
            pending = pending[: options["limit"]]

        self.stdout.write(f"등록 대상: {len(pending)}개 (판매중 · SSG 미등록)")
        for p in pending:
            self.stdout.write(f"  [{p.id}] {p.seller_code} — {p.name}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("dry-run — 실제 등록 안 함"))
            return

        ok, fail = 0, 0
        for i, p in enumerate(pending):
            if i > 0:
                time.sleep(3)  # SSG 연속 호출 3초 간격 제한
            try:
                ssg = register_ssg_item(p.id, on_sale=options["on_sale"])
                ok += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{i + 1}/{len(pending)}] OK {p.seller_code} "
                        f"-> itemId {ssg.om_product_id}"
                    )
                )
            except Exception as e:
                fail += 1
                self.stderr.write(
                    f"[{i + 1}/{len(pending)}] 실패 {p.seller_code}: {str(e)[:200]}"
                )
        self.stdout.write(self.style.SUCCESS(f"완료 — 성공 {ok}, 실패 {fail}"))

    def _print_st11_products(self):
        ssg_seller_codes = set(
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.SSG
            ).values_list("seller_code", flat=True)
        )
        products = OpenMarketProduct.objects.filter(
            open_market__source=OpenMarketChoices.ST11
        ).order_by("id")
        for p in products:
            ssg_code = (p.seller_code or "").replace("11ST", "SSG")
            mark = " [SSG 등록됨]" if ssg_code in ssg_seller_codes else ""
            self.stdout.write(f"{p.id}\t{p.seller_code}\t{p.name}{mark}")
