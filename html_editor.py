"""Gallery.html 편집기 - productGroups 배열 및 공정 사진 HTML 파싱/수정"""

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

def generate_new_entry(caption: str, date: str, image_numbers: List[int]) -> str:
    """
    새 제품 항목의 JS 코드를 생성한다.
    
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
        f'          {{ thumb: "images/sustube/thumbs/sustube{num}_thumb.webp", full: "images/sustube/sustube{num}.webp" }}'
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


def add_product_to_html(html: str, caption: str, date: str, image_numbers: List[int]) -> Tuple[Optional[str], str]:
    """
    gallery.html HTML에 새 제품 항목을 **맨 위**에 추가한다.
    
    Returns:
        (수정된 HTML, 에러 메시지)
        성공 시 에러는 빈 문자열
    """
    new_entry = generate_new_entry(caption, date, image_numbers)

    # productGroups 배열의 시작 '[' 찾기
    match = re.search(r"const\s+productGroups\s*=\s*\[", html)
    if not match:
        return None, "productGroups 배열의 시작을 찾을 수 없습니다."

    # '[' 뒤에 삽입
    insert_pos = match.end()

    # '[' 뒤에 오는 내용 (공백/줄바꿈 제외)
    rest = html[insert_pos:].lstrip()
    
    if rest.startswith("]"):
        # 빈 배열: 그냥 새 항목 추가
        modified = html[:insert_pos] + "\n" + new_entry + "\n" + html[insert_pos:]
    else:
        # 기존 항목이 있으면 새 항목 + 쉼표를 맨 앞에 삽입
        modified = html[:insert_pos] + "\n" + new_entry + ",\n" + html[insert_pos:]

    return modified, ""


def generate_process_html(folder_name: str, image_numbers: List[int]) -> str:
    """공정 사진용 gallery-item HTML 블록 생성"""
    caption = PROCESS_CAPTIONS.get(folder_name, folder_name)
    items = []
    for num in image_numbers:
        items.append(f"""          <div class="gallery-item" tabindex="0">
            <div class="image-grid single">
              <img src="images/{folder_name}/thumbs/{folder_name}{num}_thumb.webp" data-full="images/{folder_name}/{folder_name}{num}.webp" alt="{caption} 공정" loading="lazy">
            </div>
            <div class="gallery-caption">{caption}</div>
          </div>""")
    return "\n".join(items)


def add_process_to_html(html: str, folder_name: str, image_numbers: List[int]) -> Tuple[Optional[str], str]:
    """
    gallery.html의 #process div > .gallery 맨 위에 새 공정 사진을 추가.
    
    Returns:
        (수정된 HTML, 에러 메시지)
    """
    new_html_block = generate_process_html(folder_name, image_numbers)

    # #process div 안쪽의 <div class="gallery"> 찾기
    match = re.search(
        r'(<div\s+id="process"[^>]*>\s*<div\s+class="gallery">)\s*',
        html,
    )
    if not match:
        return None, "#process div > .gallery를 찾을 수 없습니다."

    insert_pos = match.end()
    modified = html[:insert_pos] + "\n" + new_html_block + "\n" + html[insert_pos:]
    return modified, ""
