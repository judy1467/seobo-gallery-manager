"""이미지 처리 - WebP 변환 및 썸네일 생성"""

import os
import tempfile
from PIL import Image
from typing import Optional, Tuple


def convert_to_webp(
    source_path: str,
    output_dir: str,
    base_name: str,
    thumb_height: int = 160,
    full_quality: int = 85,
    thumb_quality: int = 70,
) -> Tuple[Optional[str], Optional[str], str]:
    """
    원본 이미지를 WebP로 변환.
    
    Returns:
        (full_image_path, thumb_image_path, error_message)
        성공 시 error는 빈 문자열, 실패 시 경로들은 None
    """
    try:
        img = Image.open(source_path)
        
        # EXIF 방향 정보 반영
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # RGBA → RGB 변환 (WebP 호환)
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode == "P":
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 1. Full-size WebP
        full_path = os.path.join(output_dir, f"{base_name}.webp")
        img.save(full_path, "WEBP", quality=full_quality)

        # 2. Thumbnail WebP
        width, height = img.size
        ratio = thumb_height / height
        thumb_width = int(width * ratio)
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
