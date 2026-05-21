"""11번가 상품 상세 HTML 변환 함수 모음.

각 함수는 `(html: str) -> tuple[str, info]` 시그니처를 따른다.
`update_detail_html.transform_and_update_product_detail_html`와 함께 사용한다.
"""

import re
from typing import Callable

# ===== 신규 이미지 URL (2026-05-21 갱신) =====

NEW_HONEST_URL = (
    "https://d1a9hcae9rlwaq.cloudfront.net/images/"
    "%E1%84%8C%E1%85%A5%E1%86%BC%E1%84%8C%E1%85%B5%E1%86%A8%E1%84%8C%E1%85%A9%E1%84%80%E1%85%A5%E1%86%AB_2-20260521023554201929.webp"
)
NEW_PURCHASE_NOTICE_URL = (
    "https://d1a9hcae9rlwaq.cloudfront.net/images/"
    "%E1%84%80%E1%85%AE%E1%84%86%E1%85%A2%E1%84%8C%E1%85%A5%E1%86%AB%E1%84%92%E1%85%AA%E1%86%A8%E1%84%8B%E1%85%B5%E1%86%AB_2-20260521023601069217.webp"
)
NEW_RETURN_URL = (
    "https://d1a9hcae9rlwaq.cloudfront.net/images/"
    "%E1%84%80%E1%85%AD%E1%84%92%E1%85%AA%E1%86%AB%E1%84%87%E1%85%A1%E1%86%AB%E1%84%91%E1%85%AE%E1%86%B7%E1%84%8B%E1%85%A1%E1%86%AB%E1%84%82%E1%85%A2_2-20260521023607212571.webp"
)
NEW_HOOKING_URL = (
    "https://d1a9hcae9rlwaq.cloudfront.net/images/"
    "%E1%84%92%E1%85%AE%E1%84%8F%E1%85%B5%E1%86%BC-20260521023621193142.webp"
)

# ===== 공통 이미지 교체 변환 =====
# 11번가 원본 URL과 어제(2026-05-20) 갱신 URL 모두 오늘자 URL로 매핑한다.

IMAGE_URL_REPLACEMENTS = {
    # 카톡 상담 (오늘 변경 없음 — 어제 URL 유지)
    "https://d1a9hcae9rlwaq.cloudfront.net/images/%EC%83%81%EB%8B%B4%EC%9B%90_%EB%AC%B8%EC%9D%98-20260209020445793985.png": "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16195-20260520080934288892.webp",
    # 정직한 조건
    "https://store.img11.co.kr/76294482/4e51f4e4-7a6a-41f8-be5c-888647045100_1770856168511.png": NEW_HONEST_URL,
    "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_84-20260520080948528407.webp": NEW_HONEST_URL,
    # 구매 전 확인사항
    "https://store.img11.co.kr/76294482/84d81f17-f8aa-471f-a6b9-24c03977bebc_1770856168671.png": NEW_PURCHASE_NOTICE_URL,
    "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16196-20260520081026539282.webp": NEW_PURCHASE_NOTICE_URL,
    # 교환/반품 안내
    "https://store.img11.co.kr/76294482/efce4d00-d29e-4b06-8bb5-da701d2d1c56_1770869244145.png": NEW_RETURN_URL,
    "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16197-20260520081242171493.png": NEW_RETURN_URL,
}

FAQ_URL_FRAGMENT = "21a9c880-854b-4ef4-b79f-779b59fad311"
FAQ_IMG_PATTERN = re.compile(
    r"<img\b[^>]*?" + re.escape(FAQ_URL_FRAGMENT) + r"[^>]*?>",
    re.DOTALL,
)

PURCHASE_NOTICE_IMG_TAG = (
    '<img style="display: block" '
    f'src="{NEW_PURCHASE_NOTICE_URL}" '
    'alt="구매전 확인사항" />'
)

HOOKING_IMG_TAG = (
    '<img style="display: block" ' f'src="{NEW_HOOKING_URL}" ' 'alt="후킹" />'
)

# 정직한조건(신규 URL) <img>를 앵커로 삼아 그 앞/뒤에 후킹/구매전확인 이미지를 삽입한다.
NEW_HONEST_URL_FRAGMENT = "20260521023554201929"
HONEST_IMG_PATTERN = re.compile(
    r"<img\b[^>]*?" + re.escape(NEW_HONEST_URL_FRAGMENT) + r"[^>]*?>",
    re.DOTALL,
)


# ===== 통신사별 VIP 혜택 이미지/링크 (요금제표) =====

CARRIER_VIP_IMG = {
    "KT": "https://store.img11.co.kr/76294482/e08bb6d1-4c28-488b-8854-039471fd4af8_1770964486404.png",
    "LG": "https://store.img11.co.kr/76294482/2dff4aae-f23c-437c-a680-91f8a33be6eb_1770964486623.png",
    "SK": "https://store.img11.co.kr/76294482/d3edf438-e1ef-4e63-8a21-ae1a65a8eb73_1770964486810.png",
}
CARRIER_VIP_LINK = {
    "KT": "https://m.membership.kt.com/vip/choice/s_VvipChoiceInfo.do",
    "SK": "https://m.tworld.co.kr/membership/benefit/brand",
    "LG": "https://m.lguplus.com/benefit-membership?urcMbspDivsCd=01&urcMbspBnftDivsCd=02",
}

# VIP 이미지의 유니크 fragment (UUID 부분)
CARRIER_VIP_IMG_FRAGMENT = {
    "KT": "e08bb6d1-4c28-488b-8854-039471fd4af8",
    "LG": "2dff4aae-f23c-437c-a680-91f8a33be6eb",
    "SK": "d3edf438-e1ef-4e63-8a21-ae1a65a8eb73",
}

_VIP_IMG_FRAGMENT_ALT = "|".join(
    re.escape(f) for f in CARRIER_VIP_IMG_FRAGMENT.values()
)

# <a>로 감싸진 VIP 블록: <a ...><img ...VIP_IMG...></a>
VIP_LINKED_BLOCK_PATTERN = re.compile(
    r"<a\b[^>]*?>\s*"
    r"<img\b[^>]*?(?:" + _VIP_IMG_FRAGMENT_ALT + r")[^>]*?>"
    r"\s*</a>",
    re.DOTALL,
)
# <a>가 없는 단독 VIP <img>
VIP_IMG_ONLY_PATTERN = re.compile(
    r"<img\b[^>]*?(?:" + _VIP_IMG_FRAGMENT_ALT + r")[^>]*?>",
    re.DOTALL,
)


def _build_vip_block(carrier: str) -> str:
    return (
        f'<a target="_blank" href="{CARRIER_VIP_LINK[carrier]}">'
        f'<img src="{CARRIER_VIP_IMG[carrier]}" alt="plan_{carrier}_1.png" />'
        f"</a>"
    )


def fix_carrier_vip_block(carrier: str) -> Callable[[str], tuple[str, dict]]:
    """HTML 안의 VIP 이미지 블록(어느 통신사든, <a> 래퍼 유무 무관)을
    인자로 받은 carrier(SK/KT/LG)의 <a><img></a> 블록으로 통일한다.

    같은 블록이 여러 번 등장하면 모두 교체한다.
    """
    if carrier not in CARRIER_VIP_IMG:
        raise ValueError(f"지원하지 않는 통신사: {carrier!r}")

    new_block = _build_vip_block(carrier)
    placeholder = "<<<__VIP_BLOCK_PLACEHOLDER__>>>"

    def _transform(html: str) -> tuple[str, dict]:
        counts = {
            "linked_block_replaced": 0,
            "img_only_replaced": 0,
            "no_match": 0,
        }

        # 먼저 <a><img></a> 형태를 placeholder로 치환 (이중 매칭 방지)
        html, n1 = VIP_LINKED_BLOCK_PATTERN.subn(placeholder, html)
        # 남은 <img> 단독을 placeholder로 치환
        html, n2 = VIP_IMG_ONLY_PATTERN.subn(placeholder, html)
        # placeholder를 최종 블록으로 일괄 치환
        html = html.replace(placeholder, new_block)

        counts["linked_block_replaced"] = n1
        counts["img_only_replaced"] = n2
        if n1 == 0 and n2 == 0:
            counts["no_match"] = 1

        return html, counts

    return _transform


def replace_common_images(html: str) -> tuple[str, dict]:
    """공통 이미지 URL 일괄 교체 + FAQ 제거 + 후킹/구매전확인사항 이미지 보장."""
    counts = {
        "url_replaced": 0,
        "faq_removed": 0,
        "purchase_notice_inserted": 0,
        "purchase_notice_anchor_missing": 0,
        "hooking_inserted": 0,
        "hooking_anchor_missing": 0,
    }

    for old_url, new_url in IMAGE_URL_REPLACEMENTS.items():
        if old_url in html:
            html = html.replace(old_url, new_url)
            counts["url_replaced"] += 1

    html, n_faq = FAQ_IMG_PATTERN.subn("", html)
    counts["faq_removed"] = n_faq

    if NEW_HOOKING_URL not in html:
        html, n_hook = HONEST_IMG_PATTERN.subn(
            lambda m: HOOKING_IMG_TAG + "\n" + m.group(0),
            html,
            count=1,
        )
        if n_hook == 0:
            counts["hooking_anchor_missing"] = 1
        else:
            counts["hooking_inserted"] = n_hook

    if NEW_PURCHASE_NOTICE_URL not in html:
        html, n_ins = HONEST_IMG_PATTERN.subn(
            lambda m: m.group(0) + "\n" + PURCHASE_NOTICE_IMG_TAG,
            html,
            count=1,
        )
        if n_ins == 0:
            counts["purchase_notice_anchor_missing"] = 1
        else:
            counts["purchase_notice_inserted"] = n_ins

    return html, counts
