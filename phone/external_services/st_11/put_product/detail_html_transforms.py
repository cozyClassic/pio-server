"""11번가 상품 상세 HTML 변환 함수 모음.

각 함수는 `(html: str) -> tuple[str, info]` 시그니처를 따른다.
`update_detail_html.transform_and_update_product_detail_html`와 함께 사용한다.
"""

import re

# ===== 공통 이미지 교체 변환 =====

IMAGE_URL_REPLACEMENTS = {
    # 카톡 상담
    "https://d1a9hcae9rlwaq.cloudfront.net/images/%EC%83%81%EB%8B%B4%EC%9B%90_%EB%AC%B8%EC%9D%98-20260209020445793985.png": "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16195-20260520080934288892.webp",
    # 정직한 조건 (추가조건 없음)
    "https://store.img11.co.kr/76294482/4e51f4e4-7a6a-41f8-be5c-888647045100_1770856168511.png": "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_84-20260520080948528407.webp",
    # 구매 전 확인사항
    "https://store.img11.co.kr/76294482/84d81f17-f8aa-471f-a6b9-24c03977bebc_1770856168671.png": "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16196-20260520081026539282.webp",
    # 교환/반품 안내
    "https://store.img11.co.kr/76294482/efce4d00-d29e-4b06-8bb5-da701d2d1c56_1770869244145.png": "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16197-20260520081242171493.png",
}

FAQ_URL_FRAGMENT = "21a9c880-854b-4ef4-b79f-779b59fad311"
FAQ_IMG_PATTERN = re.compile(
    r"<img\b[^>]*?" + re.escape(FAQ_URL_FRAGMENT) + r"[^>]*?>",
    re.DOTALL,
)

NEW_PURCHASE_NOTICE_URL = (
    "https://d1a9hcae9rlwaq.cloudfront.net/images/Frame_16196-20260520081026539282.webp"
)
PURCHASE_NOTICE_IMG_TAG = (
    '<img style="display: block" '
    f'src="{NEW_PURCHASE_NOTICE_URL}" '
    'alt="구매전 확인사항" />'
)

NEW_HONEST_URL_FRAGMENT = "Frame_84-20260520080948528407"
HONEST_IMG_PATTERN = re.compile(
    r"<img\b[^>]*?" + re.escape(NEW_HONEST_URL_FRAGMENT) + r"[^>]*?>",
    re.DOTALL,
)


def replace_common_images(html: str) -> tuple[str, dict]:
    """공통 이미지 URL 일괄 교체 + FAQ 제거 + 구매전확인사항 보장."""
    counts = {
        "url_replaced": 0,
        "faq_removed": 0,
        "purchase_notice_inserted": 0,
        "purchase_notice_anchor_missing": 0,
    }

    for old_url, new_url in IMAGE_URL_REPLACEMENTS.items():
        if old_url in html:
            html = html.replace(old_url, new_url)
            counts["url_replaced"] += 1

    html, n_faq = FAQ_IMG_PATTERN.subn("", html)
    counts["faq_removed"] = n_faq

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
