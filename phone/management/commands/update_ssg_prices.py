"""SSG 상품 옵션(요금제) 가격을 현재 DB 기준으로 재동기화한다.

정책 엑셀 업로드 시 marketplace_sync가 자동으로 큐잉하지만, 이 커맨드로 수동
강제 재동기화도 가능하다(전체/통신사별/단건).

사용 예:
  python manage.py update_ssg_prices --dry-run          # 전체 미리보기
  python manage.py update_ssg_prices --carrier SK       # SK 상품만 갱신
  python manage.py update_ssg_prices --ssg-id 908       # 단건 갱신
"""

import time

from django.core.management.base import BaseCommand

from phone.constants import CarrierChoices, OpenMarketChoices
from phone.external_services.ssg.put_product.payload import calc_sell_price
from phone.external_services.ssg.put_product.register_item import (
    _get_carrier,
    _get_contract_type,
    _get_product_options,
    _get_ssg_open_market,
)
from phone.external_services.ssg.put_product.update_options import update_ssg_options
from phone.external_services.st_11.api import OM_MARGIN_BY_CARRIER
from phone.models import OpenMarketProduct


class Command(BaseCommand):
    help = "SSG 상품 옵션 가격을 현재 DB(ProductOption) 기준으로 재동기화"

    def add_arguments(self, parser):
        parser.add_argument("--carrier", choices=CarrierChoices.VALUES)
        parser.add_argument("--ssg-id", type=int, help="SSG OpenMarketProduct 내부 ID")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        qs = (
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.SSG,
                device_variant__isnull=False,
            )
            .exclude(om_product_id__isnull=True)
            .exclude(om_product_id="")
            .select_related("device_variant")
            .order_by("id")
        )
        if options["ssg_id"]:
            qs = qs.filter(id=options["ssg_id"])
        if options["carrier"]:
            qs = qs.filter(seller_code__contains=options["carrier"])

        products = list(qs)
        self.stdout.write(f"대상 {len(products)}개")

        commission_rate = _get_ssg_open_market().commision_rate_default
        ok = fail = 0
        for i, p in enumerate(products):
            try:
                carrier = _get_carrier(p.seller_code)
                contract = _get_contract_type(p.seller_code)
                pos = _get_product_options(p.device_variant_id, carrier, contract)
                if not pos:
                    self.stdout.write(f"  [{p.id}] {p.seller_code} — 요금제 없음, 건너뜀")
                    continue
                margin = OM_MARGIN_BY_CARRIER[carrier]

                if options["dry_run"]:
                    prices = [
                        (po.plan.name, calc_sell_price(po.final_price, margin, commission_rate))
                        for po in pos
                    ]
                    self.stdout.write(f"  [{p.id}] {p.seller_code}: {prices}")
                    continue

                if i > 0:
                    time.sleep(1)
                update_ssg_options(p.om_product_id, pos, margin, commission_rate)
                ok += 1
                self.stdout.write(f"  [{p.id}] {p.seller_code} — 갱신 OK")
            except Exception as e:
                fail += 1
                self.stderr.write(f"  [{p.id}] {p.seller_code} — 실패: {str(e)[:150]}")

        if not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"완료 — 성공 {ok} / 실패 {fail}"))
