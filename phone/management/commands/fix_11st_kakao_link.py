from django.core.management.base import BaseCommand

from phone.constants import OpenMarketChoices
from phone.models import OpenMarketProduct
from phone.external_services.st_11.put_product.update_detail_html import (
    transform_and_update_product_detail_html,
)
from phone.external_services.st_11.put_product.detail_html_transforms import (
    fix_kakao_link_block,
    KAKAO_HREF,
)


class Command(BaseCommand):
    help = (
        "11번가 등록 상품들의 상세페이지에서 카카오톡 상담 이미지를 감싸는 "
        f"<a> 태그의 href를 {KAKAO_HREF} 로 일괄 강제 교정한다."
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
            help="11번가 update API는 호출하지 않고 변환 결과 요약만 출력 (GET은 호출)",
        )
        parser.add_argument(
            "--show-html",
            action="store_true",
            help="변환 후 HTML을 콘솔에 그대로 출력 (검증용, --id와 함께 사용 권장)",
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
        self.stdout.write(f"대상 11번가 상품 수: {total}")

        success_count = 0
        skip_count = 0
        fail_count = 0

        for i, om_product in enumerate(products, 1):
            prefix = (
                f"[{i}/{total}] id={om_product.id} prdNo={om_product.om_product_id}"
            )
            try:
                result = self._process_one(
                    om_product,
                    dry_run=opts["dry_run"],
                    show_html=opts["show_html"],
                )
                if result == "updated":
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"{prefix} OK"))
                elif result == "dry":
                    success_count += 1
                    self.stdout.write(f"{prefix} DRY (변환 OK, API 미호출)")
                else:
                    skip_count += 1
                    self.stdout.write(f"{prefix} SKIP (변경사항 없음)")
            except Exception as e:
                fail_count += 1
                self.stderr.write(f"{prefix} FAIL: {e}")

        self.stdout.write(
            f"\n결과 - 성공: {success_count}, 스킵: {skip_count}, 실패: {fail_count}"
        )

    def _process_one(
        self, om_product: OpenMarketProduct, dry_run: bool, show_html: bool
    ) -> str:
        before, after, counts = transform_and_update_product_detail_html(
            om_product.om_product_id,
            fix_kakao_link_block,
            dry_run=dry_run,
        )

        self.stdout.write(
            "  변환: linked_block_replaced={linked_block_replaced}, "
            "img_only_replaced={img_only_replaced}, "
            "no_match={no_match}".format(**counts)
        )

        if counts["no_match"]:
            self.stderr.write(
                "  경고: 카카오톡 상담 이미지 블록을 HTML에서 못 찾음 → 변경 없음"
            )

        if before == after:
            return "skip"

        if show_html:
            self.stdout.write("\n----- 변환 후 HTML -----")
            self.stdout.write(after)
            self.stdout.write("----- 변환 후 HTML 끝 -----\n")

        return "dry" if dry_run else "updated"
