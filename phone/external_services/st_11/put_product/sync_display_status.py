# pyright: reportAttributeAccessIssue=false
"""재고 상태에 따라 11번가 상품의 전시(판매)중지/재개를 동기화한다.

판정 기준
---------
- 하나의 `OpenMarketProduct`(11번가 상품)는 `device_variant` 하나와,
  `seller_code`에 인코딩된 통신사(SK/KT/LG)에 대응한다.
- 대리점(`Dealership`)은 통신사와 1:1 (디아이=SK, 퍼스트=KT, 엘비휴넷=LG).
- 따라서 상품의 재고 = 해당 `device_variant`이면서 상품 통신사와 같은 통신사의
  대리점 재고(모든 색상) 합계.
- 합계가 0이면 전시중지(stopdisplay), 0보다 크면 전시재개(restartdisplay).

중복 호출 방지
--------------
- `OpenMarketProduct.is_display_stopped` 필드에 현재 전시상태를 저장한다.
- 원하는 상태(desired)와 저장된 상태가 다른 상품만 11번가 API를 호출한다.
- API 성공 시에만 필드를 갱신하여, 실패한 상품은 다음 동기화 때 재시도된다.
"""

import logging

from django.db.models import Sum

from phone.constants import CarrierChoices, OpenMarketChoices
from phone.external_services.channel_talk import (
    send_open_market_update_failure_alert,
)
from phone.external_services.st_11.put_product.set_display_status import (
    restart_display,
    stop_display,
)
from phone.models import Inventory, OpenMarketProduct

logger = logging.getLogger(__name__)

# seller_code에서 통신사를 판별할 때 검사할 순서 (모델 get_carrier와 동일 우선순위)
_CARRIER_CANDIDATES = (CarrierChoices.KT, CarrierChoices.LG, CarrierChoices.SK)


def _derive_carrier(seller_code: str | None) -> str | None:
    """seller_code(예: 'IP17A_256_LG_MNP_11ST')에서 통신사를 추출한다."""
    if not seller_code:
        return None
    for carrier in _CARRIER_CANDIDATES:
        if carrier in seller_code:
            return carrier
    return None


def _build_stock_map(device_variant_ids: set[int]) -> dict[tuple[int, str], int]:
    """(device_variant_id, 대리점 통신사) -> 재고 합계 딕셔너리."""
    if not device_variant_ids:
        return {}

    rows = (
        Inventory.objects.filter(device_variant_id__in=device_variant_ids)
        .values("device_variant_id", "dealership__carrier")
        .annotate(total=Sum("count"))
    )
    return {
        (row["device_variant_id"], row["dealership__carrier"]): row["total"] or 0
        for row in rows
    }


def sync_11st_display_status() -> dict[str, int]:
    """전체 11번가 상품의 전시상태를 현재 재고에 맞춰 동기화한다.

    반환: {"checked": 대상 수, "updated": 상태 변경 성공 수, "failed": 실패 수}
    """
    om_products = list(
        OpenMarketProduct.objects.filter(
            open_market__source=OpenMarketChoices.ST11,
            device_variant__isnull=False,
        )
        .exclude(om_product_id__isnull=True)
        .exclude(om_product_id="")
    )

    device_variant_ids = {p.device_variant_id for p in om_products}
    stock_map = _build_stock_map(device_variant_ids)

    updated = 0
    failures: list[tuple[int, str]] = []

    for product in om_products:
        carrier = _derive_carrier(product.seller_code)
        if carrier is None:
            logger.warning(
                "[11st display sync] OMP %s(%s) seller_code에서 통신사 판별 실패 - 건너뜀 "
                "(seller_code=%s)",
                product.id,
                product.name,
                product.seller_code,
            )
            continue

        stock = stock_map.get((product.device_variant_id, carrier), 0)
        desired_stopped = stock <= 0

        if desired_stopped == product.is_display_stopped:
            continue

        try:
            if desired_stopped:
                stop_display(product.om_product_id)
            else:
                restart_display(product.om_product_id)

            product.is_display_stopped = desired_stopped
            product.save(update_fields=["is_display_stopped", "updated_at"])
            updated += 1
        except Exception as e:  # noqa: BLE001 - 개별 상품 실패는 격리하고 계속 진행
            failures.append((product.id, str(e)))
            logger.exception(
                "[11st display sync] OMP %s 전시상태 변경 실패", product.id
            )

    if failures:
        detail = f"{len(failures)}건 실패\n" + "\n".join(
            f"- OMP {pid}: {err}" for pid, err in failures[:10]
        )
        send_open_market_update_failure_alert("전시상태 동기화", 0, detail)

    logger.info(
        "[11st display sync] 완료 - 대상 %s / 변경 %s / 실패 %s",
        len(om_products),
        updated,
        len(failures),
    )
    return {"checked": len(om_products), "updated": updated, "failed": len(failures)}
