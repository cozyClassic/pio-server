from celery import shared_task
from django.utils import timezone

from phone.models import OpenMarketProduct
from phone.constants import CarrierChoices
from phone.external_services.channel_talk import ChannelTalkAPI
from phone.external_services.st_11.put_product.remove_options import (
    remove_options_except_default,
)
from phone.external_services.st_11.put_product.set_price import set_product_price
from phone.external_services.st_11.put_product.set_options import SetOptions11ST

MARGIN_11ST = 30_000  # 수수료 제외 후 남길 마진 (1만원)


def _get_carrier(seller_code: str) -> str:
    carriers = [c for c in CarrierChoices.VALUES if c in (seller_code or "")]
    if not carriers:
        raise Exception(f"셀러코드에 매칭되는 통신사가 없습니다: {seller_code}")
    return carriers[0]


def _send_failure_alert(task_name: str, om_product_id: int, detail: str):
    ChannelTalkAPI.post(
        path=f"/open/v5/groups/{ChannelTalkAPI.ORDER_ALERT_GROUP_ID}/messages",
        json={
            "blocks": [
                {
                    "type": "text",
                    "value": (
                        f"[11번가 {task_name} 실패]\n"
                        f"내부 ID: {om_product_id}\n"
                        f"상세: {detail}"
                    ),
                }
            ]
        },
    )


@shared_task
def task_a_remove_options(om_product_id_internal: int, target_price: int):
    """기본 옵션(가격 0원)만 남기고 나머지 제거 후 Task B 체이닝."""
    try:
        om_product = OpenMarketProduct.objects.get(id=om_product_id_internal)
        carrier = _get_carrier(om_product.seller_code)
        remove_options_except_default(carrier, om_product.om_product_id)
        task_b_set_price.delay(
            om_product_id_internal=om_product_id_internal,
            current_price=om_product.registered_price,
            target_price=target_price,
        )
    except Exception as e:
        _send_failure_alert("Task A (옵션 정리)", om_product_id_internal, str(e))
        raise


@shared_task
def task_b_set_price(
    om_product_id_internal: int, current_price: int, target_price: int
):
    """판매가를 목표가로 단계적 인하. 성공 시 DB 갱신 후 Task C 체이닝.

    current_price: 트리거 시점 DB registered_price (동기화 오류 추적용)
    target_price:  어드민 트리거 시점에 계산된 목표 판매가
    """
    try:
        om_product = OpenMarketProduct.objects.get(id=om_product_id_internal)
        set_product_price(om_product.om_product_id, target_price)

        # API 성공 직후 DB 갱신 (atomic 처리)
        om_product.registered_price = target_price
        om_product.last_price_updated_at = timezone.now()
        om_product.save(update_fields=["registered_price", "last_price_updated_at"])

        task_c_set_options.delay(om_product_id_internal=om_product_id_internal)
    except Exception as e:
        _send_failure_alert(
            f"Task B (가격 인하, current={current_price}, target={target_price})",
            om_product_id_internal,
            str(e),
        )
        raise


@shared_task
def task_c_set_options(om_product_id_internal: int):
    """option rate limit 이내의 하위 요금제 옵션 추가."""
    try:
        SetOptions11ST.set_om_options(om_product_id_internal, margin=MARGIN_11ST)
    except Exception as e:
        _send_failure_alert("Task C (옵션 추가)", om_product_id_internal, str(e))
        raise
