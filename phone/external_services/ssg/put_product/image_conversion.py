"""SSG 대표이미지용 JPG 변환.

SSG 상품등록 API는 대표이미지(dataFileNm) URL 검증 시 webp를 거부한다.
webp 원본을 JPG로 변환해 S3(ssg_item_images/)에 올리고 CloudFront URL을 반환한다.
같은 원본은 결정적 경로를 사용해 재변환 없이 재사용한다.
"""

import io
import os
import re

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

CONVERTED_DIR = "ssg_item_images"
JPEG_QUALITY = 90
# SSG 대표이미지 규격: 1200x1200 권장, 최소 720x720
SSG_IMAGE_SIZE = 1200
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _converted_path(original_name: str) -> str:
    base = os.path.splitext(os.path.basename(original_name))[0]
    return f"{CONVERTED_DIR}/{base}.jpg"


def _already_uploaded(url: str) -> bool:
    # S3 HeadObject 권한이 없어 default_storage.exists() 대신
    # 공개 CloudFront URL로 존재 여부를 확인한다.
    try:
        return requests.head(url, timeout=10).status_code == 200
    except requests.RequestException:
        return False


def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    # 투명 배경은 흰색으로 합성 (JPG는 알파 미지원)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        return background
    return img.convert("RGB")


def prepare_square_jpg(content: bytes, size: int = SSG_IMAGE_SIZE) -> bytes:
    """이미지를 SSG 규격의 정사각 JPG로 정규화한다.

    비율을 유지한 채 size 안에 맞추고 남는 영역은 흰색 패딩.
    원본이 작으면 업스케일(LANCZOS)한다.
    """
    img = _flatten_to_rgb(Image.open(io.BytesIO(content)))

    scale = size / max(img.size)
    resized = img.resize(
        (max(1, round(img.size[0] * scale)), max(1, round(img.size[1] * scale))),
        Image.LANCZOS,
    )

    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    canvas.paste(
        resized,
        ((size - resized.size[0]) // 2, (size - resized.size[1]) // 2),
    )

    buffer = io.BytesIO()
    canvas.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _safe_basename(filename: str) -> str:
    """URL·파일시스템 안전한 basename. 공백/특수문자는 언더스코어로 치환.

    SSG 대표이미지 URL 검증이 까다로워(webp 거부 등) 공백 인코딩(%20)을
    피하고, 한글·기호 없는 ASCII 파일명만 남긴다.
    """
    base = os.path.splitext(os.path.basename(filename))[0]
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_")
    return safe or "image"


def upload_ssg_image(content: bytes, filename: str) -> str:
    """정규화된 JPG를 S3(ssg_item_images/)에 올리고 CDN URL을 반환한다."""
    saved_path = default_storage.save(
        f"{CONVERTED_DIR}/{_safe_basename(filename)}.jpg", ContentFile(content)
    )
    return default_storage.url(saved_path)


def ensure_jpg_url(image_field) -> str:
    """ImageField가 webp면 JPG로 변환해 업로드하고 URL 반환, 아니면 원본 URL."""
    name = image_field.name or ""
    if not name.lower().endswith(".webp"):
        return image_field.url

    target_path = _converted_path(name)
    target_url = default_storage.url(target_path)
    if not _already_uploaded(target_url):
        # S3 GetObject 권한이 없어 원본도 공개 CloudFront URL로 받는다.
        response = requests.get(image_field.url, timeout=30)
        response.raise_for_status()

        img = Image.open(io.BytesIO(response.content))
        # 투명 배경은 흰색으로 합성 (JPG는 알파 미지원)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        saved_path = default_storage.save(target_path, ContentFile(buffer.getvalue()))
        return default_storage.url(saved_path)

    return target_url
