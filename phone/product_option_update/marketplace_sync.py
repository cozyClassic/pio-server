# pyright: reportAttributeAccessIssue=false
"""정책 엑셀 업로드 후처리 - 11번가/네이버/Next.js 캐시 동기화 헬퍼.

엑셀 import로 ProductOption.final_price가 갱신된 직후 호출되어:
  1) 11번가 가격 업데이트 Task 큐잉 (해당 통신사 OMP만)
  2) 네이버 가격비교 EP 재생성 Task 큐잉
  3) Next.js ISR 캐시 무효화 (제품 태그)
4단계 모두 단계별 try/except로 격리되어 한 단계 실패가 다음 단계를 막지 않는다.
실패는 채널톡으로 알림 후 그 단계만 포기.
"""

import logging
from collections import defaultdict

from phone.constants import (
    CarrierChoices,
    ContractTypeChoices,
    DiscountTypeChoices,
    OpenMarketChoices,
)
from phone.external_services.channel_talk import (
    send_marketplace_sync_failure_alert,
)
from phone.models import OpenMarketProduct, ProductOption
from phone.revalidate import revalidate_products
from phone.tasks import task_a_remove_options, task_generate_naver_compare_ep

logger = logging.getLogger(__name__)


BAIT_MARGIN = 10_000  # 미끼 상품 고정 마진


def trigger_marketplace_sync(carrier: str, margin: int, om_margin: int) -> None:
    """정책 엑셀 업로드 후 마켓플레이스 동기화를 시작한다.

    각 단계는 독립적으로 try/except 처리되며, 실패 시 채널톡 알림만 보내고
    다음 단계로 진행한다. admin view에 예외를 raise 하지 않는다.
    """

    # 단계 1 — 11번가 큐잉
    try:
        om_products = list(
            OpenMarketProduct.objects.filter(
                open_market__source=OpenMarketChoices.ST11,
                deleted_at__isnull=True,
                seller_code__contains=carrier,
            ).select_related("open_market")
        )

        device_variant_ids = [
            p.device_variant_id for p in om_products if p.device_variant_id
        ]
        all_product_options = list(
            ProductOption.objects.filter(
                device_variant_id__in=device_variant_ids,
                discount_type=DiscountTypeChoices.SUBSIDY,
            )
            .select_related("plan")
            .order_by("-plan__price")
        )

        po_by_dv = defaultdict(list)
        for po in all_product_options:
            po_by_dv[po.device_variant_id].append(po)

        for om_product in om_products:
            seller_code = om_product.seller_code or ""
            contract_type = (
                ContractTypeChoices.MNP
                if "MNP" in seller_code
                else ContractTypeChoices.CHANGE
            )
            matching_pos = [
                po
                for po in po_by_dv.get(om_product.device_variant_id, [])
                if po.plan.carrier == carrier and po.contract_type == contract_type
            ]
            if not matching_pos:
                logger.warning(
                    f"[marketplace_sync] OMP {om_product.id} ({om_product.name}) "
                    f"매칭 ProductOption 없음 — 건너뜀 "
                    f"(carrier={carrier}, contract_type={contract_type})"
                )
                continue

            bait_base = min(po.final_price for po in matching_pos) - margin
            commission_rate = om_product.open_market.commision_rate_default
            target_price = int(
                round((bait_base + BAIT_MARGIN) / (1 - commission_rate), -3)
            )
            target_price = max(target_price, 1000)

            task_a_remove_options.delay(
                om_product_id_internal=om_product.id,
                target_price=target_price,
                om_margin=om_margin,
            )
    except Exception as e:
        send_marketplace_sync_failure_alert("11번가 큐잉", carrier, str(e))

    # 단계 1.5 — SSG 가격/옵션 업데이트 큐잉 (해당 통신사 상품만)
    try:
        from phone.tasks import task_update_ssg_prices

        ssg_products = OpenMarketProduct.objects.filter(
            open_market__source=OpenMarketChoices.SSG,
            deleted_at__isnull=True,
            seller_code__contains=carrier,
        ).exclude(om_product_id__isnull=True).exclude(om_product_id="")

        for ssg_product in ssg_products:
            task_update_ssg_prices.delay(ssg_product.id)
    except Exception as e:
        send_marketplace_sync_failure_alert("SSG 큐잉", carrier, str(e))

    # 단계 2 — 네이버 EP 재생성 큐잉
    try:
        task_generate_naver_compare_ep.delay()
    except Exception as e:
        send_marketplace_sync_failure_alert("네이버 EP 큐잉", carrier, str(e))

    # 단계 3 — Next.js ISR 캐시 무효화
    try:
        revalidate_products()
    except Exception as e:
        send_marketplace_sync_failure_alert("ISR revalidate", carrier, str(e))
