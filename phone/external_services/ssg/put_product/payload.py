"""SSG 상품등록(POST /item/0.1/online) payload 도메인 빌더.

기존 승인 상품(itemId 1000793710193)의 구조를 기준으로 조립한다.
가격 공식은 11번가와 동일: 판매가 = (final_price + margin) / (1 - 수수료), 천원 반올림.
"""

from datetime import datetime, timezone, timedelta

from phone.models import ProductOption
from .constants import (
    SITE_EMART,
    SITE_SHINSEGAE,
    SITE_SSGCOM,
    SITE_GROCERY,
    STD_CTG_FULL_PAYMENT,
    BRAND_ID,
    DISP_CTG,
    GROCERY_DISP_CTG_ID,
    DELIVERY_SHIPPING_METHODS,
    NOTIFICATION_CLASS_ID,
    NOTIFICATION_PROP_NAME_MODEL,
    NOTIFICATION_PROP_KC_CERT,
    NOTIFICATION_PROP_RELEASE_YM,
    NOTIFICATION_PROP_SIZE_WEIGHT,
    NOTIFICATION_PROP_MANUFACTURER,
    NOTIFICATION_PROP_IMPORTER,
    NOTIFICATION_STATIC_PROPS,
    OPTION_TYPE_NAME,
    OPTION_STOCK_QTY,
    MIN_SELL_PRICE,
)

KST = timezone(timedelta(hours=9))


def calc_sell_price(final_price: int, margin: int, commission_rate: float) -> int:
    """고객 판매가. 수수료를 제하고 (final_price + margin)이 남도록 역산."""
    return max(
        int(round((final_price + margin) / (1 - commission_rate), -3)),
        MIN_SELL_PRICE,
    )


def _calc_supply_price(sell_price: int, commission_rate: float) -> int:
    """공급가(부가세 제외). prcMngMthdCd=1이면 SSG가 자동계산하지만 방어적으로 채운다."""
    return int(sell_price * (1 - commission_rate) / 1.1)


def _now_kst_str() -> str:
    return datetime.now(KST).strftime("%Y/%m/%d %H:%M:%S")


def _item_prices(sell_price: int, commission_rate: float) -> dict:
    return {
        "aplStrtDt": _now_kst_str(),
        "splprc": _calc_supply_price(sell_price, commission_rate),
        "sellprc": sell_price,
        "mrgrt": round(commission_rate * 100, 2),
    }


def build_item_base(
    *,
    item_name: str,
    carrier: str,
    contract_type: str,
    brand: str,
    model_code: str,
) -> dict:
    if carrier not in STD_CTG_FULL_PAYMENT:
        raise Exception(f"SSG 표준카테고리가 없는 통신사입니다: {carrier}")
    if brand not in BRAND_ID:
        raise Exception(f"SSG 브랜드 ID가 없는 브랜드입니다: {brand}")

    main_display_categories = [
        {
            "siteNo": SITE_SSGCOM,
            "dispCtgId": DISP_CTG[SITE_SSGCOM][carrier][contract_type],
        },
        {
            "siteNo": SITE_SHINSEGAE,
            "dispCtgId": DISP_CTG[SITE_SHINSEGAE][carrier][contract_type],
        },
        {"siteNo": SITE_GROCERY, "dispCtgId": GROCERY_DISP_CTG_ID},
    ]

    return {
        "itemNm": item_name,
        "txnDivCd": 10,  # 과세
        "buyFrmCd": 60,  # 위수탁
        "stdCtgId": STD_CTG_FULL_PAYMENT[carrier],
        "sites": [
            {"siteNo": SITE_EMART, "sellStatCd": 20},
            {"siteNo": SITE_SHINSEGAE, "sellStatCd": 20},
        ],
        "mainDisplayCategories": main_display_categories,
        "srchPsblYn": "Y",
        "b2cAplRngCd": 10,
        "b2eAplRngCd": 10,
        "b2bAplRngCd": 10,
        "brandId": BRAND_ID[brand],
        "mdlNm": model_code,
        "itemChrctDivCd": 10,  # 일반 (기존 승인 상품과 동일)
        "itemChrctDtlCd": 10,
        "exusItemDivCd": 10,
        "exusItemDtlCd": 10,
        "adultItemTypeCd": 90,
        "itemStatTypeCd": 10,  # 새상품
        "itemSellWayCd": 10,
        "palimpItemYn": "N",
        "giftPsblYn": "Y",
        "whinNotiYn": "Y",
        "minOnetOrdPsblQty": 1,
        "maxOnetOrdPsblQty": 20,
        "max1dyOrdPsblQty": 20,
        "b2bMaxOnetOrdPsblQty": 20,
        "b2bMax1dyOrdPsblQty": 20,
        "itemTotWgt": 1000,
        "qualGantYn": "N",
    }


def build_delivery() -> dict:
    # 개통 상품 특성상 반품/교환 배송 불가(N) — 기존 승인 상품과 동일
    return {
        "retExchPsblYn": "N",
        "perdcShppTgtYn": "N",
        "shippingMethods": dict(DELIVERY_SHIPPING_METHODS),
    }


def build_description(*, detail_html: str, main_image_urls: list[str]) -> dict:
    if not main_image_urls:
        raise Exception("대표이미지가 최소 1장 필요합니다.")

    return {
        "itemDescriptions": [{"itemDescDivCd": 10, "htmlCntt": detail_html}],
        "itemImages": [
            {
                "dataSeq": i + 1,
                "dataFileNm": url,
                "rplcTextNm": f"상품이미지{i + 1}",
            }
            for i, url in enumerate(main_image_urls[:10])
        ],
    }


def build_notification(
    *,
    model_spec: str,
    manufacturer: str,
    kc_cert: str = "상세페이지 참조",
    release_ym: str = "상세페이지 참조",
    size_weight: str = "상세페이지 참조",
) -> dict:
    props = [
        {"itemMngPropId": NOTIFICATION_PROP_NAME_MODEL, "itemMngCntt": model_spec},
        {"itemMngPropId": NOTIFICATION_PROP_KC_CERT, "itemMngCntt": kc_cert},
        {"itemMngPropId": NOTIFICATION_PROP_RELEASE_YM, "itemMngCntt": release_ym},
        {"itemMngPropId": NOTIFICATION_PROP_SIZE_WEIGHT, "itemMngCntt": size_weight},
        {"itemMngPropId": NOTIFICATION_PROP_MANUFACTURER, "itemMngCntt": manufacturer},
        {"itemMngPropId": NOTIFICATION_PROP_IMPORTER, "itemMngCntt": manufacturer},
        *[dict(p) for p in NOTIFICATION_STATIC_PROPS],
    ]
    return {"itemMngPropClsId": NOTIFICATION_CLASS_ID, "notificationProps": props}


def build_option(
    *,
    product_options: list[ProductOption],
    margin: int,
    commission_rate: float,
    sell_stat_cd: int = 80,
) -> dict:
    """요금제를 옵션으로 구성. 각 옵션은 독립 판매가(완납가)를 갖는다.

    product_options는 요금제 가격 내림차순(최상위 요금제 = 최저 완납가) 정렬 전제.
    sell_stat_cd는 상품 단위 판매상태(20 판매중 / 80 일시중지). 기본은 80으로
    등록해 검수 후 판매재개하는 흐름을 전제한다. 개별 옵션은 항상 20으로 두고
    상품 단위 상태로만 제어한다(기존 승인 상품과 동일 구조).
    """
    if not product_options:
        raise Exception("등록할 요금제 옵션이 없습니다.")

    option_rows = []
    for po in product_options:
        sell_price = calc_sell_price(po.final_price, margin, commission_rate)
        option_rows.append(
            {
                "uitemOptnNm1": po.plan.name,
                "useYn": "Y",
                "sellStatCd": 20,
                "itemPrices": _item_prices(sell_price, commission_rate),
                "usablInvQty": OPTION_STOCK_QTY,
            }
        )

    return {
        "sellStatCd": sell_stat_cd,
        "itemSellTypeCd": 20,  # 옵션형
        "invMngYn": "Y",
        "invQtyMarkgYn": "N",
        "uitemOptnChoiTypeCd1": 10,  # 드롭다운
        "uitemOptnExpsrTypeCd1": 10,  # 텍스트
        "uitemOptnTypeNm1": OPTION_TYPE_NAME,
        "optionNms": option_rows,
        "uitemCacOptnYn": "N",
    }


def build_registration_payload(
    *,
    item_base: dict,
    delivery: dict,
    description: dict,
    notification: dict,
    option: dict,
) -> dict:
    return {
        "online_registration": {
            "itemBase": item_base,
            "delivery": delivery,
            "description": description,
            "notification": notification,
            "option": option,
        }
    }
