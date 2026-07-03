"""활성 상품을 Google Merchant API로 등록/갱신하는 오케스트레이터.

네이버 EP 제너레이터와 같은 위치/패턴. 상품당 오퍼 1개를 ``productInputs.insert``
로 upsert 한다(같은 offerId 재전송 = 갱신). 상품은 최소 30일 내 refresh 필요하므로
Celery 스케줄로 주기 실행하는 것을 전제로 한다.
"""

import logging

from django.db.models import Prefetch

from phone.models import (
    Product,
    Inventory,
    DeviceColor,
)
from . import product_builder as builder
from .client import product_inputs_client, account_name, datasource_name

logger = logging.getLogger(__name__)


def _products_qs():
    return (
        Product.objects.filter(is_active=True, deleted_at__isnull=True)
        .select_related("device")
        .prefetch_related(
            "options",
            "options__plan",
            "options__device_variant",
            "options__product__device",
            "device__variants",
            Prefetch(
                "device__colors",
                queryset=DeviceColor.objects.order_by("sort_order"),
            ),
            "device__colors__images",
        )
        .order_by("id")
    )


def _inventories_for(product):
    """상세 뷰와 동일한 방식으로 상품별 재고를 조회한다."""
    variant_ids = [v.id for v in product.device.variants.all()]
    color_ids = [c.id for c in product.device.colors.all()]
    return list(
        Inventory.objects.filter(
            device_variant_id__in=variant_ids,
            device_color_id__in=color_ids,
        ).select_related("dealership", "device_variant", "device_color")
    )


def push(dry_run: bool = False, limit: int | None = None, stdout=None):
    """활성 상품을 Merchant에 등록/갱신한다.

    dry_run=True 이면 API를 호출하지 않고 페이로드만 집계/출력한다
    (google 라이브러리·크리덴셜 없이도 실행 가능).

    반환: 요약 dict {"ok", "skipped", "failed", "errors"}.
    """

    def _emit(msg):
        if stdout is not None:
            stdout.write(msg)
        else:
            logger.info(msg)

    summary = {"ok": 0, "skipped": 0, "failed": 0, "errors": []}

    client = None
    parent = ds_name = None
    mp = None
    if not dry_run:
        # google 라이브러리 지연 임포트 — dry_run 이면 패키지 없이도 동작해야 하므로
        # 이 블록(실전 전송 경로)에서만 임포트한다.
        from google.shopping import merchant_products_v1 as mp

        # 크리덴셜/설정이 없으면 여기서 명확히 실패한다.
        client = product_inputs_client()
        parent = account_name()
        ds_name = datasource_name()

    count = 0
    for product in _products_qs():
        if limit is not None and count >= limit:
            break
        count += 1

        try:
            payload = builder.assemble(product, _inventories_for(product))
        except Exception as e:  # 페이로드 생성 실패는 격리
            summary["failed"] += 1
            summary["errors"].append({"product_id": product.id, "error": str(e)})
            _emit(f"[FAIL/build] product={product.id}: {e}")
            continue

        if payload is None:
            summary["skipped"] += 1
            _emit(f"[skip] product={product.id} (무재고/가격없음)")
            continue

        if dry_run:
            summary["ok"] += 1
            _emit(
                f"[dry-run] product={product.id} "
                f"offerId={payload['offer_id']} "
                f"price={payload['price_krw']:,}원 "
                f"title={payload['title']!r} link={payload['link']}"
            )
            continue

        try:
            request = mp.InsertProductInputRequest(
                parent=parent,
                data_source=ds_name,
                product_input=builder.to_product_input(payload),
            )
            client.insert_product_input(request=request)
            summary["ok"] += 1
            _emit(f"[ok] product={product.id} price={payload['price_krw']:,}원")
        except Exception as e:  # 개별 상품 실패는 격리하고 계속
            summary["failed"] += 1
            summary["errors"].append({"product_id": product.id, "error": str(e)})
            _emit(f"[FAIL/send] product={product.id}: {e}")

    _emit(
        f"요약: ok={summary['ok']} skipped={summary['skipped']} "
        f"failed={summary['failed']}"
    )
    return summary
