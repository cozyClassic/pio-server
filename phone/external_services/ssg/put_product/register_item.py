"""11번가 OpenMarketProduct를 원본으로 SSG에 상품을 등록한다.

상품 단위(단말변형 × 통신사 × 계약유형), 상품명, 상세HTML을 11번가 등록분에서
재사용하고, 요금제 옵션 가격은 현행 ProductOption 기준으로 다시 계산한다.
"""

from django.utils import timezone as dj_timezone

from phone.constants import (
    CarrierChoices,
    ContractTypeChoices,
    DiscountTypeChoices,
    OpenMarketChoices,
)
from phone.models import (
    DevicesColorImage,
    OpenMarket,
    OpenMarketProduct,
    ProductOption,
)
from phone.external_services.st_11.put_product.update_detail_html import (
    get_product_detail_html,
)
from ..api import ssg_post
from .payload import (
    build_delivery,
    build_description,
    build_item_base,
    build_notification,
    build_option,
    build_registration_payload,
    calc_sell_price,
)

CARRIER_TO_MODEL_NAME_FIELD = {
    CarrierChoices.SK: "name_sk",
    CarrierChoices.KT: "name_kt",
    CarrierChoices.LG: "name_lg",
}


def _get_carrier(seller_code: str) -> str:
    carriers = [c for c in CarrierChoices.VALUES if c in (seller_code or "")]
    if not carriers:
        raise Exception(f"셀러코드에 매칭되는 통신사가 없습니다: {seller_code}")
    return carriers[0]


def _get_contract_type(seller_code: str) -> str:
    return (
        ContractTypeChoices.MNP
        if "MNP" in seller_code
        else ContractTypeChoices.CHANGE
    )


def _get_ssg_open_market() -> OpenMarket:
    open_market, _ = OpenMarket.objects.get_or_create(
        source=OpenMarketChoices.SSG,
        defaults={"commision_rate_default": 0.15},
    )
    return open_market


def _get_product_options(
    device_variant_id: int, carrier: str, contract_type: str
) -> list[ProductOption]:
    return list(
        ProductOption.objects.filter(
            device_variant_id=device_variant_id,
            contract_type=contract_type,
            discount_type=DiscountTypeChoices.SUBSIDY,
            plan__carrier=carrier,
        )
        .select_related("plan")
        .order_by("-plan__price")
    )


def _upload_dir_images(device_id: int, folder: str) -> list[str]:
    """폴더의 고해상도 이미지를 1200 정사각 JPG로 정규화해 S3에 올리고 URL 반환.

    파일명 정렬 순서 = 노출 순서. dev{device_id}_ prefix로 기기별 유일 경로.
    """
    from pathlib import Path

    from django.conf import settings

    from .image_conversion import IMAGE_EXTS, prepare_square_jpg, upload_ssg_image

    base = Path(settings.BASE_DIR) / folder
    if not base.is_dir():
        raise Exception(f"SSG 이미지 폴더가 없습니다: {base}")

    paths = sorted(p for p in base.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not paths:
        raise Exception(f"SSG 이미지 폴더가 비어 있습니다: {base}")

    urls = []
    for i, p in enumerate(paths[:10]):
        content = prepare_square_jpg(p.read_bytes())
        urls.append(upload_ssg_image(content, f"dev{device_id}_{i:02d}_{p.name}"))
    return urls


def _get_main_image_urls(device_id: int) -> list[str]:
    from .constants import DEVICE_IMAGE_DIRS
    from .image_conversion import ensure_jpg_url

    # 고해상도 소스 폴더가 매핑된 기기는 그 폴더를 우선 사용하고,
    # 매핑에 없는 기기(예: S25/S25Ultra)는 기존 DevicesColorImage로 폴백한다.
    folder = DEVICE_IMAGE_DIRS.get(device_id)
    if folder:
        return _upload_dir_images(device_id, folder)

    images = (
        DevicesColorImage.objects.filter(device_color__device_id=device_id)
        .order_by("device_color__sort_order", "id")
        .all()[:10]
    )
    # SSG 대표이미지 검증이 webp를 거부하므로 JPG 변환본 URL을 사용한다.
    return [ensure_jpg_url(img.image) for img in images if img.image]


def build_ssg_registration_from_11st(
    st11_om_product_id: int, on_sale: bool = False
) -> dict:
    """11번가 OpenMarketProduct 내부 ID로 SSG 등록 payload와 컨텍스트를 만든다.

    on_sale=False(기본)면 상품 판매상태 80(일시중지)으로 등록 — 검수 후 판매재개.
    """
    st11_product = (
        OpenMarketProduct.objects.select_related(
            "open_market", "device_variant", "device_variant__device"
        )
        .filter(id=st11_om_product_id, open_market__source=OpenMarketChoices.ST11)
        .first()
    )
    if st11_product is None:
        raise Exception(f"11번가 상품이 없습니다 - 내부 ID: {st11_om_product_id}")

    variant = st11_product.device_variant
    if variant is None:
        raise Exception(f"단말변형이 연결되지 않은 상품입니다: {st11_product.id}")

    device = variant.device
    carrier = _get_carrier(st11_product.seller_code)
    contract_type = _get_contract_type(st11_product.seller_code)

    ssg_market = _get_ssg_open_market()
    commission_rate = ssg_market.commision_rate_default

    from phone.external_services.st_11.api import OM_MARGIN_BY_CARRIER

    margin = OM_MARGIN_BY_CARRIER[carrier]

    product_options = _get_product_options(variant.id, carrier, contract_type)
    if not product_options:
        raise Exception(
            f"등록할 ProductOption이 없습니다 - dv:{variant.id} {carrier} {contract_type}"
        )

    model_code = getattr(variant, CARRIER_TO_MODEL_NAME_FIELD[carrier], "") or ""
    model_spec = f"{device.model_name} {variant.storage_capacity}"
    if model_code:
        model_spec += f" / {model_code}"

    # 상세HTML은 DB가 아닌 11번가 등록분에서 실시간 조회해 재사용
    detail_html = get_product_detail_html(st11_product.om_product_id)
    if not detail_html.strip():
        raise Exception(
            f"11번가 상세HTML이 비어 있습니다 - om_product_id: {st11_product.om_product_id}"
        )

    payload = build_registration_payload(
        item_base=build_item_base(
            item_name=st11_product.name,
            carrier=carrier,
            contract_type=contract_type,
            brand=device.brand,
            model_code=model_code or device.model_name,
            sell_stat_cd=20 if on_sale else 80,
        ),
        delivery=build_delivery(),
        description=build_description(
            detail_html=detail_html,
            main_image_urls=_get_main_image_urls(device.id),
        ),
        notification=build_notification(
            model_spec=model_spec,
            manufacturer="삼성전자" if device.brand == "삼성" else "Apple",
        ),
        option=build_option(
            product_options=product_options,
            margin=margin,
            commission_rate=commission_rate,
            sell_stat_cd=20 if on_sale else 80,
        ),
    )

    # 대표가(등록가) = 최상위 요금제 옵션 판매가 (SSG는 옵션 최저가를 자동 적용)
    registered_price = min(
        calc_sell_price(po.final_price, margin, commission_rate)
        for po in product_options
    )

    return {
        "payload": payload,
        "detail_html": detail_html,
        "st11_product": st11_product,
        "ssg_market": ssg_market,
        "carrier": carrier,
        "contract_type": contract_type,
        "margin": margin,
        "registered_price": registered_price,
    }


def register_ssg_item(
    st11_om_product_id: int, on_sale: bool = False
) -> OpenMarketProduct:
    """SSG에 상품을 등록하고 OpenMarketProduct(source=SSG) 레코드를 생성한다."""
    context = build_ssg_registration_from_11st(st11_om_product_id, on_sale=on_sale)
    st11_product = context["st11_product"]

    seller_code = (st11_product.seller_code or "").replace("11ST", "SSG")
    existing = OpenMarketProduct.objects.filter(
        open_market=context["ssg_market"], seller_code=seller_code
    ).first()
    if existing is not None:
        raise Exception(
            f"이미 등록된 SSG 상품이 있습니다 - 내부 ID: {existing.id}, "
            f"itemId: {existing.om_product_id}"
        )

    data = ssg_post("/item/0.1/online", context["payload"], action="상품등록")
    item_id = data.get("result", {}).get("itemId")
    if not item_id:
        raise Exception(f"상품등록 응답에 itemId가 없습니다: {data}")

    return OpenMarketProduct.objects.create(
        open_market=context["ssg_market"],
        device_variant=st11_product.device_variant,
        om_product_id=str(item_id),
        seller_code=seller_code,
        name=st11_product.name,
        registered_price=context["registered_price"],
        detail_page_html=context["detail_html"],
        last_price_updated_at=dj_timezone.now(),
        # 판매상태 추적 캐시(재고 동기화용). 검수 전 기본 등록은 판매중지 상태.
        is_display_stopped=not on_sale,
    )
