"""등록된 SSG 상품의 대표이미지 교체.

description 도메인은 itemDescriptions(상세HTML)가 필수라, 현재 값을 GET으로
받아 그대로 유지하면서 itemImages만 교체해 POST한다.
"""

from ..api import ssg_get, ssg_post


def _current_description(ssg_item_id: str) -> dict:
    data = ssg_get(f"/item/0.1/online/{ssg_item_id}/description", action="상세조회")
    description = data.get("result", {}).get("description")
    if not description:
        raise Exception(f"상세 정보를 찾을 수 없습니다 - itemId: {ssg_item_id}")
    return description


def update_item_main_images(ssg_item_id: str, image_urls: list[str]) -> list[dict]:
    """대표이미지를 image_urls(최대 10장)로 전면 교체한다."""
    if not image_urls:
        raise Exception("교체할 이미지가 없습니다.")

    current = _current_description(ssg_item_id)

    item_descriptions = current.get("itemDescriptions") or []
    if isinstance(item_descriptions, dict):
        item_descriptions = [item_descriptions]
    # htmlCntt 없는 빈 항목(사이즈표 등 미사용 슬롯)은 되돌려보내지 않는다
    item_descriptions = [d for d in item_descriptions if d.get("htmlCntt")]
    if not item_descriptions:
        raise Exception(f"기존 상세HTML이 없습니다 - itemId: {ssg_item_id}")

    new_urls = image_urls[:10]
    item_images = [
        {
            "dataSeq": i + 1,
            "dataFileNm": url,
            "rplcTextNm": f"상품이미지{i + 1}",
        }
        for i, url in enumerate(new_urls)
    ]

    # SSG 대표이미지는 dataSeq 기준 병합이라, 새 이미지보다 뒤에 남는 기존 슬롯을
    # delYn=Y로 명시 삭제하지 않으면 이전 저해상도 이미지가 잔존한다.
    existing_images = current.get("itemImages") or []
    if isinstance(existing_images, dict):
        existing_images = [existing_images]
    # 삭제 슬롯은 dataSeq + delYn만 보낸다. 기존 dataFileNm(SSG 내부 CDN URL)을
    # 되돌려보내면 "내부 파일 업로드 불가"로 거부되기 때문.
    for im in existing_images:
        seq = int(im.get("dataSeq") or 0)
        if seq > len(new_urls):
            item_images.append({"dataSeq": seq, "delYn": "Y"})

    ssg_post(
        f"/item/0.1/online/{ssg_item_id}/description",
        {
            "online_updateDescription": {
                "description": {
                    "itemDescriptions": item_descriptions,
                    "itemImages": item_images,
                }
            }
        },
        action="대표이미지 교체",
    )
    return item_images
