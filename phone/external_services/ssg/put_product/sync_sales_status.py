"""재고에 따라 SSG 상품의 판매(전시)상태를 동기화한다.

재고 판정 로직은 11번가와 동일하므로 그 헬퍼를 그대로 재사용한다
(재고 = device_variant + 상품 통신사 대리점 재고 합계, 활성 모델만 판매).

**판매재개 안전장치**: 재고가 확보돼 판매 가능한 상태가 되어도, enable_resume=True로
명시 활성화하지 않으면 판매재개(start_selling)는 호출하지 않는다. 판매중지 방향
(재고 소진 → stop_selling)은 항상 적용한다. 사용자의 "아직 판매로 돌리지 말기"
지시를 코드로 보장하기 위함. 판매 개시가 확정되면 enable_resume=True로 호출한다.
"""

import logging

from phone.constants import OpenMarketChoices
from phone.external_services.channel_talk import send_open_market_update_failure_alert
from phone.external_services.st_11.put_product.sync_display_status import (
    _build_active_device_ids,
    _build_stock_map,
    _derive_carrier,
    compute_desired_stopped,
)
from phone.models import OpenMarketProduct
from .set_sales_status import start_selling, stop_selling

logger = logging.getLogger(__name__)


def sync_ssg_sales_status(enable_resume: bool = False) -> dict[str, int]:
    """전체 SSG 상품의 판매상태를 현재 재고에 맞춰 동기화한다.

    enable_resume=False(기본): 판매중지 방향만 적용, 재개는 건너뜀(집계는 skipped_resume).
    반환: {"checked", "stopped", "resumed", "skipped_resume", "failed"}
    """
    om_products = list(
        OpenMarketProduct.objects.filter(
            open_market__source=OpenMarketChoices.SSG,
            device_variant__isnull=False,
        )
        .exclude(om_product_id__isnull=True)
        .exclude(om_product_id="")
        .select_related("device_variant")
    )

    stock_map = _build_stock_map({p.device_variant_id for p in om_products})
    active_device_ids = _build_active_device_ids()

    stopped = resumed = skipped_resume = 0
    failures: list[tuple[int, str]] = []

    for product in om_products:
        carrier = _derive_carrier(product.seller_code)
        if carrier is None:
            logger.warning(
                "[ssg sales sync] OMP %s seller_code 통신사 판별 실패 (%s) - 건너뜀",
                product.id,
                product.seller_code,
            )
            continue

        stock = stock_map.get((product.device_variant_id, carrier), 0)
        device_active = product.device_variant.device_id in active_device_ids
        desired_stopped = compute_desired_stopped(stock, device_active)

        if desired_stopped == product.is_display_stopped:
            continue

        # 판매재개 방향은 명시 활성화 전까지 실제 호출하지 않는다.
        if not desired_stopped and not enable_resume:
            skipped_resume += 1
            continue

        try:
            if desired_stopped:
                stop_selling(product.om_product_id)
                stopped += 1
            else:
                start_selling(product.om_product_id)
                resumed += 1

            product.is_display_stopped = desired_stopped
            product.save(update_fields=["is_display_stopped", "updated_at"])
        except Exception as e:  # noqa: BLE001 - 개별 실패 격리
            failures.append((product.id, str(e)))
            logger.exception("[ssg sales sync] OMP %s 판매상태 변경 실패", product.id)

    if failures:
        detail = f"{len(failures)}건 실패\n" + "\n".join(
            f"- OMP {pid}: {err}" for pid, err in failures[:10]
        )
        send_open_market_update_failure_alert(
            "판매상태 동기화", 0, detail, market="SSG"
        )

    result = {
        "checked": len(om_products),
        "stopped": stopped,
        "resumed": resumed,
        "skipped_resume": skipped_resume,
        "failed": len(failures),
    }
    logger.info("[ssg sales sync] 완료 - %s", result)
    return result
