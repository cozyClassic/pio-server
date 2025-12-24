"""
Next.js ISR On-demand Revalidation 유틸리티

사용법:
    from phone.revalidate import revalidate_cache, RevalidateTag

    # 특정 태그 revalidate
    revalidate_cache(RevalidateTag.PRODUCTS)

    # 여러 태그 revalidate
    revalidate_cache([RevalidateTag.PRODUCTS, RevalidateTag.BANNERS])

    # 모든 캐시 revalidate
    revalidate_cache(RevalidateTag.ALL)
"""

import logging
import os
from enum import Enum
from typing import Union, List
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class RevalidateTag(str, Enum):
    """사용 가능한 캐시 태그"""

    PRODUCTS = "products"
    PRODUCT_DETAIL = "product-detail"
    BANNERS = "banners"
    REVIEWS = "reviews"
    FAQS = "faqs"
    PARTNER_CARDS = "partner-cards"
    ALL = "all"


def revalidate_cache(
    tags: Union[RevalidateTag, List[RevalidateTag], str, List[str]],
    async_call: bool = True,
) -> bool:
    """
    Next.js ISR 캐시를 revalidate합니다.

    Args:
        tags: revalidate할 태그 (단일 또는 리스트)
        async_call: True면 비동기로 실행 (응답 대기 안함)

    Returns:
        성공 여부 (async_call=True면 항상 True)
    """
    frontend_url = getattr(
        settings,
        "FRONTEND_URL",
        os.environ.get("FRONTEND_URL", "https://www.phoneinone.com"),
    )
    revalidate_token = getattr(
        settings, "REVALIDATE_SECRET_TOKEN", os.environ.get("REVALIDATE_SECRET_TOKEN")
    )

    if not revalidate_token:
        logger.warning(
            "REVALIDATE_SECRET_TOKEN이 설정되지 않았습니다. Revalidation을 건너뜁니다."
        )
        return False

    # 태그 정규화
    if isinstance(tags, (RevalidateTag, str)):
        tag_list = [str(tags.value if isinstance(tags, RevalidateTag) else tags)]
    else:
        tag_list = [str(t.value if isinstance(t, RevalidateTag) else t) for t in tags]

    url = f"{frontend_url}/api/revalidate"
    headers = {
        "Authorization": f"Bearer {revalidate_token}",
        "Content-Type": "application/json",
    }
    payload = {"tag": tag_list if len(tag_list) > 1 else tag_list[0]}

    try:
        timeout = 1 if async_call else 10
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)

        if response.status_code == 200:
            logger.info(f"캐시 revalidation 성공: {tag_list}")
            return True
        else:
            logger.error(
                f"캐시 revalidation 실패: {response.status_code} - {response.text}"
            )
            return False

    except requests.exceptions.Timeout:
        if async_call:
            logger.info(f"캐시 revalidation 요청 전송됨 (비동기): {tag_list}")
            return True
        logger.error(f"캐시 revalidation 타임아웃: {tag_list}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"캐시 revalidation 오류: {e}")
        return False


def revalidate_products():
    """제품 관련 캐시 revalidate"""
    return revalidate_cache([RevalidateTag.PRODUCTS, RevalidateTag.PRODUCT_DETAIL])


def revalidate_banners():
    """배너 캐시 revalidate"""
    return revalidate_cache(RevalidateTag.BANNERS)


def revalidate_reviews():
    """리뷰 캐시 revalidate"""
    return revalidate_cache(RevalidateTag.REVIEWS)


def revalidate_faqs():
    """FAQ 캐시 revalidate"""
    return revalidate_cache(RevalidateTag.FAQS)


def revalidate_all():
    """모든 캐시 revalidate"""
    return revalidate_cache(RevalidateTag.ALL)
