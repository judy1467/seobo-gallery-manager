"""Gallery.html 편집기 - productGroups 배열 파싱 및 수정"""

import re
from typing import List, Dict, Optional, Tuple


def find_product_groups_js(html: str) -> Optional[str]:
    """HTML에서 const productGroups = [...] 배열을 찾아 반환"""
    # "const productGroups = [" 로 시작해서 "];" 로 끝나는 부분
    match = re.search(
        r"const\s+productGroups\s*=\s*\[(.*?)\];",
        html,
        re.DOTALL,
    )
    if match:
        return match.group(0)
    return None


def parse_caption_from_images(html: str) -> Dict[str, int]:
    """HTML 내 sustube 이미지 파일명을 분석해 caption별 이미지 수를 반환"""
    pattern = r'\{[^}]*?caption\s*:\s*"([^"]+)"[^}]*?images\s*:\s*\[([^\]]*?)\][^}]*?\}'
    groups = {}
    for m in re.finditer(pattern, html, re.DOTALL):
        caption = m.group(1)
        images_block = m.group(2)
        img_count = len(re.findall(r'\{[^}]*?\}', images_block))
        groups[caption] = img_count
    return groups


def extract_full_image_paths(html: str, caption: str) -> List[str]:
    """특정 caption에 해당하는 sustube 파일명들을 추출"""
    pattern = rf'caption\s*:\s*"{re.escape(caption)}"[^}}]*?images\s*:\s*\[(.*?)\]'
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        return []
    return re.findall(r'sustube(\d+)', m.group(1))


def find_max_image_number(html: str) -> int:
    """HTML 내 sustube 이미지 중 가장 큰 번호를 반환"""
    numbers = [int(x) for x in re.findall(r'sustube(\d+)', html)]
    return max(numbers) if numbers else 0


def get_all_captions(html: str) -> List[Dict]:
    """현재 등록된 모든 제품 정보를 dict 리스트로 반환"""
    pattern = r'\{\s*caption\s*:\s*"([^"]*)"(?:\s*,\s*date\s*:\s*"([^"]*)")?\s*,\s*images\s*:\s*\[(.*?)\]\s*\}'
    results = []
    for m in re.finditer(pattern, html, re.DOTALL):
        caption = m.group(1)
        date = m.group(2) if m.group(2) else ""
        images_block = m.group(3)
        images = re.findall(r'sustube(\d+)', images_block)
        results.append({
            "caption": caption,
            "date": date,
            "images": images,
            "image_count": len(images),
        })
    return results


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
    gallery.html HTML에 새 제품 항목을 추가한다.
    
    Returns:
        (수정된 HTML, 에러 메시지)
        성공 시 에러는 빈 문자열
    """
    new_entry = generate_new_entry(caption, date, image_numbers)

    # productGroups 배열의 마지막 항목 뒤에 삽입
    # 방법: 마지막 '];' 앞에 새 항목 추가 (단일 이미지 섹션 앞에)
    # 단일 이미지 그룹 마지막 줄 패턴 찾기
    match = re.search(r"^\s*\]\s*;\s*$", html, re.MULTILINE)
    if not match:
        return None, "productGroups 배열의 끝(];)을 찾을 수 없습니다."

    pos = match.start()
    # 마지막 항목 뒤에 쉼표 추가 + 새 항목
    # 배열의 마지막 줄 앞에 삽입
    # '];' 바로 앞에 새 항목 + 쉼표 추가
    prev_line_end = html.rfind("\n", 0, pos)
    before = html[:pos].rstrip()
    after = html[pos:]

    # 마지막 항목에 쉼표가 없으면 추가
    if not before.rstrip().endswith(","):
        modified = before + ",\n" + new_entry + "\n" + after
    else:
        modified = before + "\n" + new_entry + "\n" + after

    return modified, ""
