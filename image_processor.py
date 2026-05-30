"""이미지 처리 - WebP 변환 및 썸네일 생성

참고: https://github.com/judy1467/seobo-gallery-manager (main.py 기반)
- EXIF 방향 자동 보정
- 원본 이미지 1200px 최대 너비로 리사이즈
- 400px 너비 썸네일 생성
"""

import os
from PIL import Image, ImageOps
from typing import Optional, Tuple


def convert_to_webp(
    source_path: str,
    output_dir: str,
    base_name: str,
    max_width: int = 1200,
    thumb_width: int = 400,
    full_quality: int = 85,
    thumb_quality: int = 80,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    원본 이미지를 WebP로 변환 (1200px 최대 너비 리사이즈 + 400px 썸네일).

    Args:
        source_path: 원본 이미지 파일 경로
        output_dir: 변환된 파일을 저장할 디렉토리
        base_name: 파일명 (확장자 제외)
        max_width: 원본 이미지 최대 너비 px (기본 1200)
        thumb_width: 썸네일 너비 px (기본 400)
        full_quality: 원본 WebP 품질 (기본 85)
        thumb_quality: 썸네일 WebP 품질 (기본 80)

    Returns:
        (full_image_path, thumb_image_path, error_message)
        성공 시 error는 빈 문자열, 실패 시 경로들은 None
    """
    try:
        img = Image.open(source_path)

        # EXIF 방향 정보 반영
        img = ImageOps.exif_transpose(img)

        # RGBA/P → RGB 변환 (WebP 호환, 흰 배경)
        if img.mode in ("RGBA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 1. Full-size WebP (1200px 최대 너비 리사이즈)
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(img.height * ratio)
            img_resized = img.resize((max_width, new_height), Image.LANCZOS)
        else:
            img_resized = img

        full_path = os.path.join(output_dir, f"{base_name}.webp")
        img_resized.save(full_path, "WEBP", quality=full_quality)

        # 2. Thumbnail WebP (400px 너비, 비율 유지)
        ratio = thumb_width / float(img.width)
        thumb_height = int(img.height * ratio)
        thumb = img.resize((thumb_width, thumb_height), Image.LANCZOS)

        thumb_dir = os.path.join(output_dir, "thumbs")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"{base_name}_thumb.webp")
        thumb.save(thumb_path, "WEBP", quality=thumb_quality)

        return full_path, thumb_path, ""

    except Exception as e:
        return None, None, f"이미지 변환 실패: {str(e)}"


def get_supported_formats() -> list:
    """지원하는 이미지 포맷 목록"""
    return [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"]


def is_supported_image(file_path: str) -> bool:
    """지원하는 이미지 포맷인지 확인"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in get_supported_formats()
