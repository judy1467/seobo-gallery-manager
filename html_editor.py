"""Gallery data JS 편집기 - product-gallery-data.js / process-gallery-data.js 수정"""

import re
from typing import List, Optional, Tuple

# 공정 폴더명 → 한글 caption 매핑
PROCESS_CAPTIONS = {
    "barrel": "바렐",
    "cut": "절단",
    "dry": "건조",
    "inspect": "검사",
    "package": "포장",
    "wash": "세척",
    "sustube": "제품",
}


# ======== product-gallery-data.js (제품 사진) ========

def generate_new_entry(caption: str, date: str, image_numbers: List[int]) -> str:
    """
    새 제품 항목의 JS 코드를 생성한다. (product-gallery-data.js 용)

    Example output:
      {
        caption: "25G-RW(0.5x0.26)x22.4mm",
        date: "2026-05-28",
        images: [
          { thumb: "images/sustube/thumbs/sustube122_thumb.webp", full: "images/sustube/sustube122.webp" },
          { thumb: "images/sustube/thumbs/sustube123_thumb.webp", full: "images/sustube/sustube123.webp" },
        ]
      }
    """
    images_js = ",\n".join(
        f'        {{ thumb: "images/sustube/thumbs/sustube{num}_thumb.webp", full: "images/sustube/sustube{num}.webp" }}'
        for num in image_numbers
    )

    if date:
        return f"""    {{
      caption: "{caption}",
      date: "{date}",
      images: [
{images_js}
      ]
    }}"""
    else:
        return f"""    {{
      caption: "{caption}",
      images: [
{images_js}
      ]
    }}"""


def add_product_to_js(js_content: str, caption: str, date: str, image_numbers: List[int]) -> Tuple[Optional[str], str]:
    """
    product-gallery-data.js 콘텐츠에 새 제품 항목을 **맨 위**에 추가한다.

    Args:
        js_content: product-gallery-data.js 내용
        caption: 제품 규격
        date: 등록일 (yyyy-MM-dd)
        image_numbers: 이미지 번호 목록

    Returns:
        (수정된 JS 콘텐츠, 에러 메시지)
    """
    new_entry = generate_new_entry(caption, date, image_numbers)

    # productGroups 배열 시작 '[' 찾기
    match = re.search(r"const\s+productGroups\s*=\s*\[", js_content)
    if not match:
        return None, "productGroups 배열의 시작을 찾을 수 없습니다."

    insert_pos = match.end()

    # '[' 뒤에 오는 내용 (공백/줄바꿈 제외)
    rest = js_content[insert_pos:].lstrip()

    if rest.startswith("]"):
        # 빈 배열: 그냥 새 항목 추가
        modified = js_content[:insert_pos] + "\n" + new_entry + "\n" + js_content[insert_pos:]
    else:
        # 기존 항목이 있으면 새 항목 + 쉼표를 맨 앞에 삽입
        modified = js_content[:insert_pos] + "\n" + new_entry + ",\n" + js_content[insert_pos:]

    return modified, ""


# ======== process-gallery-data.js (공정 사진) ========

def generate_process_image_js(folder_name: str, image_numbers: List[int]) -> str:
    """공정 사진 이미지 배열 JS 코드 생성"""
    lines = []
    for i, num in enumerate(image_numbers):
        comma = "," if i < len(image_numbers) - 1 else ""
        lines.append(
            f'      {{ thumb: "images/{folder_name}/thumbs/{folder_name}{num}_thumb.webp",'
            f' full: "images/{folder_name}/{folder_name}{num}.webp" }}{comma}'
        )
    return "\n".join(lines)


def add_process_to_js(js_content: str, folder_name: str, image_numbers: List[int]) -> Tuple[Optional[str], str]:
    """
    process-gallery-data.js 콘텐츠에 공정 사진을 추가한다.

    같은 caption(예: "절단")의 images 배열에 새 이미지를 추가한다.
    만약 해당 caption이 없으면 새 섹션을 생성한다.

    Args:
        js_content: process-gallery-data.js 내용
        folder_name: 공정 폴더명 (barrel, cut, dry, inspect, package, wash)
        image_numbers: 추가할 이미지 번호 목록

    Returns:
        (수정된 JS 콘텐츠, 에러 메시지)
    """
    caption = PROCESS_CAPTIONS.get(folder_name, folder_name)
    new_images_js = generate_process_image_js(folder_name, image_numbers)

    # 1) 해당 caption의 images 배열 닫는 부분 찾기
    # "caption: "<caption>" 섹션 찾기
    pattern = re.compile(
        r'(\{\s*caption:\s*"' + re.escape(caption) + r'"[^}]*?images:\s*\[)([^\]]*?)(\]\s*[,\s])',
        re.DOTALL,
    )
    match = pattern.search(js_content)

    if match:
        # 기존 섹션의 images 배열에 새 항목 추가
        before_images = match.group(1)  # { caption: "...", ... images: [
        existing_images = match.group(2).strip()
        after_bracket = match.group(3)  # ]  ,  또는 ]\n

        if existing_images:
            # 기존 이미지가 있으면 끝에 쉼표 + 새 이미지
            new_section = before_images + existing_images + ",\n" + new_images_js + after_bracket
        else:
            # 빈 images 배열
            new_section = before_images + "\n" + new_images_js + after_bracket

        modified = js_content[: match.start()] + new_section + js_content[match.end():]
        return modified, ""
    else:
        # 2) 해당 caption이 없으면 새 섹션 추가 (processImages 배열 끝에)
        new_section = (
            f"  {{\n"
            f'    caption: "{caption}",\n'
            f"    images: [\n"
            f"{new_images_js}\n"
            f"    ]\n"
            f"  }}"
        )

        # processImages 배열의 끝(]); 앞에 삽입
        end_match = re.search(r"\];\s*$", js_content)
        if not end_match:
            return None, "processImages 배열의 끝을 찾을 수 없습니다."

        # 배열 끝 '];' 앞에 쉼표 + 새 항목 추가
        pre_end = js_content[: end_match.start()].rstrip()
        if pre_end.endswith("]") or pre_end.endswith("["):
            # 배열이 비어있거나 마지막 항목이 없음
            modified = js_content[: end_match.start()] + new_section + "\n" + js_content[end_match.start():]
        else:
            # 마지막 항목 뒤에 쉼표 추가
            modified = js_content[: end_match.start()] + ",\n" + new_section + "\n" + js_content[end_match.start():]

        return modified, ""
