"""SSG 상품 옵션(요금제) 재구성 및 가격 갱신.

현재 DB의 ProductOption(요금제별 완납가)을 기준으로 SSG 옵션을 재구성한다:
- 요금제명(uitemOptnNm1 = Plan.name)이 이미 있으면 uitemId를 유지하고 가격만 갱신
- DB에 새로 생긴 요금제는 uitemId 없이 신규 추가
- DB에서 사라진 요금제는 useYn=N으로 비활성

정책 엑셀 업로드로 final_price가 바뀌면 이 함수로 SSG 가격을 다시 맞춘다.
같은 DB 상태로 재실행하면 같은 가격이 계산되어 idempotent하다.
"""

from ..api import ssg_get, ssg_post
from .constants import OPTION_STOCK_QTY, OPTION_TYPE_NAME
from .payload import _item_prices, calc_sell_price


def _get_current_option(item_id: str) -> dict:
    data = ssg_get(f"/item/0.1/online/{item_id}/option", action="옵션조회")
    option = data.get("result", {}).get("option")
    if not option:
        raise Exception(f"옵션 정보를 찾을 수 없습니다 - itemId: {item_id}")
    return option


def _build_option_rows(
    current_option: dict, product_options: list, margin: int, commission_rate: float
) -> list[dict]:
    existing = {
        o.get("uitemOptnNm1"): o
        for o in (current_option.get("optionNms") or [])
        if o.get("uitemOptnNm1")
    }

    db_names: set[str] = set()
    rows: list[dict] = []
    for po in product_options:  # plan.price 내림차순 전제
        name = po.plan.name
        db_names.add(name)
        sell_price = calc_sell_price(po.final_price, margin, commission_rate)
        row = {
            "uitemOptnNm1": name,
            "useYn": "Y",
            "sellStatCd": 20,
            "itemPrices": _item_prices(sell_price, commission_rate),
            "usablInvQty": OPTION_STOCK_QTY,
        }
        prev = existing.get(name)
        if prev and prev.get("uitemId"):
            row["uitemId"] = prev["uitemId"]  # 기존 옵션 유지(요금제명 동일)
        rows.append(row)

    # DB에서 사라진 요금제는 비활성 처리
    for name, prev in existing.items():
        if name not in db_names:
            rows.append(
                {
                    "uitemId": prev.get("uitemId"),
                    "uitemOptnNm1": name,
                    "useYn": "N",
                    "sellStatCd": prev.get("sellStatCd", 20),
                    "itemPrices": prev.get("itemPrices"),
                    "usablInvQty": 0,
                }
            )
    return rows


def update_ssg_options(
    ssg_item_id: str, product_options: list, margin: int, commission_rate: float
) -> list[dict]:
    """SSG 상품 옵션을 현재 DB 기준으로 재구성하고 가격을 갱신한다."""
    if not product_options:
        raise Exception("갱신할 요금제 옵션이 없습니다.")

    current = _get_current_option(ssg_item_id)
    option_rows = _build_option_rows(
        current, product_options, margin, commission_rate
    )

    payload = {
        "online_updateOption": {
            "option": {
                "sellStatCd": current.get("sellStatCd", 20),
                "itemSellTypeCd": 20,
                "invMngYn": current.get("invMngYn", "Y"),
                "invQtyMarkgYn": current.get("invQtyMarkgYn", "N"),
                "uitemOptnChoiTypeCd1": 10,
                "uitemOptnExpsrTypeCd1": 10,
                "uitemOptnTypeNm1": OPTION_TYPE_NAME,
                "optionNms": option_rows,
                "uitemCacOptnYn": "N",
            }
        }
    }
    ssg_post(
        f"/item/0.1/online/{ssg_item_id}/option", payload, action="옵션 업데이트"
    )
    return option_rows
