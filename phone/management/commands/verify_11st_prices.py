from django.core.management.base import BaseCommand

from phone.constants import (
    CarrierChoices,
    ContractTypeChoices,
    DiscountTypeChoices,
    OpenMarketChoices,
)
from phone.models import OpenMarketProduct, ProductOption
from phone.external_services.st_11.put_product.get_product_info import (
    get_product_listed_price,
)

COMMISSION_RATE = 0.08

DB_MARGIN_BY_CARRIER = {
    CarrierChoices.SK: 60_000,
    CarrierChoices.LG: 60_000,
    CarrierChoices.KT: 80_000,
}
OM_MARGIN_BY_CARRIER = {
    CarrierChoices.SK: 10_000,
    CarrierChoices.LG: 10_000,
    CarrierChoices.KT: 30_000,
}


class Command(BaseCommand):
    help = (
        "11번가 등록 상품의 '옵션 0원' 기본 판매가가 DB의 (device_variant × carrier × "
        "contract_type × SUBSIDY) 조건 최저가 ProductOption.final_price와 일치하는지 검증한다. "
        "11번가의 기본가는 마진이 거의 없는 미끼 요금제 기준이므로, DB에는 매칭되는 동일 요금제가 "
        "없을 수 있어 'DB의 상품 최저가'와 비교한다. "
        "검증식: 11번가_판매가 * (1 - 0.08) ≈ DB_최저_final_price - (DB마진 - 11번가마진). "
        "carrier별 마진 차이는 SK/LG/KT 모두 5만원."
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
            "--tolerance",
            type=int,
            default=5_000,
            help="±tolerance 원 이내면 OK로 처리 (기본: 5000원)",
        )
        parser.add_argument(
            "--show-ok",
            action="store_true",
            help="OK 행도 상세 출력 (기본: MISMATCH만 상세 출력)",
        )

    def handle(self, *args, **opts):
        qs = (
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.ST11,
                om_product_id__isnull=False,
            )
            .exclude(om_product_id="")
            .select_related("open_market", "device_variant")
            .order_by("id")
        )

        if opts["id"] is not None:
            qs = qs.filter(id=opts["id"])
        if opts["limit"] is not None:
            qs = qs[: opts["limit"]]

        products = list(qs)
        total = len(products)
        self.stdout.write(f"검증 대상 11번가 상품 수: {total}")
        self.stdout.write(
            f"기준: commission={COMMISSION_RATE:.0%}, "
            f"db_margin={DB_MARGIN_BY_CARRIER}, om_margin={OM_MARGIN_BY_CARRIER}, "
            f"tolerance=±{opts['tolerance']:,}원\n"
        )

        counters = {"OK": 0, "MISMATCH": 0, "MISSING_DB": 0, "ERROR": 0}

        for i, om in enumerate(products, 1):
            prefix = (
                f"[{i}/{total}] id={om.id} prdNo={om.om_product_id} "
                f"seller={om.seller_code}"
            )
            try:
                result = self._verify_one(om, opts["tolerance"])
            except Exception as e:
                counters["ERROR"] += 1
                self.stderr.write(f"{prefix} ERROR: {e}")
                continue

            counters[result["status"]] += 1
            self._print_result(prefix, result, show_ok=opts["show_ok"])

        self.stdout.write(
            "\n결과 - "
            f"OK: {counters['OK']}, "
            f"MISMATCH: {counters['MISMATCH']}, "
            f"DB누락: {counters['MISSING_DB']}, "
            f"ERROR: {counters['ERROR']}"
        )

    def _verify_one(self, om: OpenMarketProduct, tolerance: int) -> dict:
        carrier = om.get_carrier()
        contract_type = self._get_contract_type(om)

        po = (
            ProductOption.objects.filter(
                device_variant_id=om.device_variant_id,
                contract_type=contract_type,
                discount_type=DiscountTypeChoices.SUBSIDY,
                plan__carrier=carrier,
            )
            .select_related("plan")
            .order_by("final_price")
            .first()
        )

        if po is None:
            return {
                "status": "MISSING_DB",
                "carrier": carrier,
                "contract_type": contract_type,
                "dv_id": om.device_variant_id,
            }

        om_price = get_product_listed_price(om.om_product_id)

        om_after_fee = om_price * (1 - COMMISSION_RATE)
        gap = po.final_price - om_after_fee
        expected_gap = DB_MARGIN_BY_CARRIER[carrier] - OM_MARGIN_BY_CARRIER[carrier]
        delta = gap - expected_gap

        status = "OK" if abs(delta) <= tolerance else "MISMATCH"

        return {
            "status": status,
            "carrier": carrier,
            "contract_type": contract_type,
            "po_id": po.id,
            "po_plan_short_name": po.plan.short_name,
            "db_final_price": po.final_price,
            "om_price": om_price,
            "om_after_fee": om_after_fee,
            "gap": gap,
            "expected_gap": expected_gap,
            "delta": delta,
        }

    @staticmethod
    def _get_contract_type(om: OpenMarketProduct) -> str:
        """set_options.py와 동일한 derivation 사용 (seller_code에 'MNP' 포함 여부)."""
        return (
            ContractTypeChoices.MNP
            if om.seller_code and "MNP" in om.seller_code
            else ContractTypeChoices.CHANGE
        )

    def _print_result(self, prefix: str, result: dict, show_ok: bool) -> None:
        status = result["status"]

        if status == "MISSING_DB":
            self.stdout.write(
                self.style.ERROR(
                    f"{prefix} MISSING_DB - DB ProductOption 없음 "
                    f"(dv={result['dv_id']}, ct={result['contract_type']}, "
                    f"carrier={result['carrier']})"
                )
            )
            return

        detail = (
            f"carrier={result['carrier']} ct={result['contract_type']} "
            f"po_id={result['po_id']} plan={result['po_plan_short_name']!r} | "
            f"DB={result['db_final_price']:,} "
            f"OM={result['om_price']:,} "
            f"OM*{1 - COMMISSION_RATE:.2f}={result['om_after_fee']:,.0f} "
            f"gap={result['gap']:,.0f} 기대={result['expected_gap']:,} "
            f"Δ={result['delta']:+,.0f}"
        )

        if status == "OK":
            if show_ok:
                self.stdout.write(self.style.SUCCESS(f"{prefix} OK  {detail}"))
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"{prefix} OK Δ={result['delta']:+,.0f}")
                )
        else:
            self.stdout.write(self.style.WARNING(f"{prefix} MISMATCH {detail}"))
