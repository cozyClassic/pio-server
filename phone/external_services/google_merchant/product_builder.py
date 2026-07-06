"""Product → Google Merchant ``ProductInput`` 페이로드 빌더.

가격 정합(중요)
---------------
피드 가격이 랜딩 페이지(JSON-LD)와 어긋나면 GMC '가격 불일치'가 재발한다.
그래서 offer 가격은 프론트가 쓰는 것과 **동일한** ``ProductDetailSerializer``
경로(``get_best_options``)에서 파생한다 — 드리프트 0.

현재 배포된 랜딩 페이지 JSON-LD는 상품당 단일 Offer(전 통신사 최저 **완납가**)를
노출한다. 따라서 여기서도 상품당 오퍼 1개, ``price = 최저 완납가``로 매핑한다.
(프론트를 통신사별 AggregateOffer로 배포하게 되면, 이 매핑도 통신사별 오퍼로
확장해야 정합이 유지된다.)

2단계 빌드
---------
- ``assemble(product, inventories)`` : google 라이브러리 없이 순수 dict를 만든다.
  ``--dry-run`` 검증이 패키지/크리덴셜 없이도 가능하도록 하기 위함.
- ``to_product_input(payload)`` : dict → proto(``ProductInput``). 실제 전송 시 사용.
"""

from django.conf import settings

GOOGLE_PRODUCT_CATEGORY_MOBILE = (
    "Electronics > Communications > Telephony > Mobile Phones"
)
FALLBACK_IMAGE = "https://www.phoneinone.com/og/og_introduction.webp"


def _first_image(device_data: dict) -> str:
    for color in device_data.get("device_colors", []):
        images = color.get("images") or []
        if images:
            return images[0]
    return FALLBACK_IMAGE


def assemble(product, inventories) -> dict | None:
    """상품 1개의 Merchant 페이로드(dict)를 만든다.

    가격을 낼 수 없거나(가격 대상 통신사 없음) 재고가 전혀 없으면 None을 반환한다
    (네이버 EP와 동일하게 무재고 상품은 노출하지 않는다).
    """
    # 재고 판단은 페이로드 생성 전에 (무재고면 아예 건너뜀)
    in_stock = any(getattr(inv, "count", 0) > 0 for inv in inventories)
    if not in_stock:
        return None

    # 랜딩 페이지와 '같은' 경로로 best_options 계산 → 가격 드리프트 방지
    from phone.serializers.product_serializers import ProductDetailSerializer

    serializer = ProductDetailSerializer(context={"inventories": list(inventories)})
    best = (serializer.get_best_options(product) or {}).get("device_price", {})
    if not best:
        return None

    # 단일 Offer(전 통신사 최저 완납가) = 프론트 ProductSEOScript의 bestOption.final_price
    offer_price = min(bo["final_price"] for bo in best.values())
    device_data = serializer.get_device(product)

    brand = device_data.get("brand", "")
    model_name = device_data.get("model_name", "")
    title = f"{brand} {model_name}".strip()

    return {
        "offer_id": str(product.id),
        "title": title,
        "description": (
            f"{title} 공시지원금 최대 적용가. "
            "부가서비스·기기반납 조건 없이 익일배송."
        ),
        "link": (
            f"{settings.GOOGLE_MERCHANT_SITE_URL}"
            f"/mobile/detail/{product.id}/v2/mvno"
        ),
        "image_link": _first_image(device_data),
        "brand": brand,
        "price_krw": int(offer_price),
        "in_stock": True,
    }


def to_product_input(payload: dict):
    """dict 페이로드를 Merchant API ``ProductInput`` proto로 변환한다.

    필드/enum 명칭은 공식 Python 샘플을 따른다:
    https://developers.google.com/merchant/api/samples/insert-product-input
    (설치된 ``google-shopping-merchant-products`` 버전에 맞는지 dry-run 후 확인 권장)
    """
    from google.shopping import merchant_products_v1 as mp
    from google.shopping.type import Price

    attributes = mp.ProductAttributes(
        title=payload["title"],
        description=payload["description"],
        link=payload["link"],
        image_link=payload["image_link"],
        brand=payload["brand"],
        google_product_category=GOOGLE_PRODUCT_CATEGORY_MOBILE,
        condition=mp.Condition.NEW,
        availability=(
            mp.Availability.IN_STOCK
            if payload["in_stock"]
            else mp.Availability.OUT_OF_STOCK
        ),
        price=Price(
            amount_micros=int(payload["price_krw"]) * 1_000_000,
            currency_code="KRW",
        ),
    )

    return mp.ProductInput(
        offer_id=payload["offer_id"],
        content_language=settings.GOOGLE_MERCHANT_CONTENT_LANGUAGE,
        feed_label=settings.GOOGLE_MERCHANT_FEED_LABEL,
        product_attributes=attributes,
    )
