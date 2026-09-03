"""'타로카드 설명.docx' 를 카드별 구조화 데이터로 파싱.

각 카드마다 4종:
  upright / reversed        : 기본 타로 (오늘의 타로)
  finance_upright / finance_reversed : 재테크 타로 (오늘의 재테크 타로)

각 항목: {summary?, description, advice_detail, advice}
  - description : '카드의 설명' 본문
  - advice_detail : '조언' 본문 전체
  - advice : 제일 끝 한 문장 (기획 문서 규칙: "제일 끝에 한문장이 조언임")
  - summary : 재테크 헤더의 콜론 뒤 요약 (기본 타로는 없음 → None)
"""
import os
import re
import logging
from functools import lru_cache
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

DOCX_PATH = os.path.join(os.path.dirname(__file__), "타로카드 설명.docx")

_HEADER_RE = re.compile(r"^\s*(\d{1,2})\.\s*([^(]+?)\s*\(([^)]+)\)\s*(.*)$")
_SENT_SPLIT = re.compile(r"(?<=[다요])[.!?]\s+")


def _read_paragraphs(path: str) -> List[str]:
    import zipfile
    from xml.etree import ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml").decode("utf-8"))
    out = []
    for p in root.iter(ns + "p"):
        text = "".join(t.text for t in p.iter(ns + "t") if t.text).strip()
        if text:
            out.append(text)
    return out


def _last_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    parts = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    return parts[-1] if parts else text


def _parse_block(headers_trailer: str, body_paras: List[str]) -> Dict[str, Any]:
    """body_paras: 헤더 다음 ~ 다음 헤더 전까지. '카드의 설명' 헤딩은 제거된 상태."""
    desc_parts: List[str] = []
    advice_parts: List[str] = []
    in_advice = False
    for para in body_paras:
        if not in_advice:
            if para == "조언":
                in_advice = True
                continue
            if para.rstrip().endswith("조언"):
                stripped = para.rstrip()[:-2].rstrip()
                if stripped:
                    desc_parts.append(stripped)
                in_advice = True
                continue
            desc_parts.append(para)
        else:
            advice_parts.append(para)

    description = " ".join(desc_parts).strip()
    advice_detail = " ".join(advice_parts).strip()
    advice = _last_sentence(advice_detail) if advice_detail else ""

    summary = None
    trailer = headers_trailer.strip()
    m = re.search(r":\s*(.+)$", trailer)
    if m:
        summary = m.group(1).strip()

    return {
        "summary": summary,
        "description": description,
        "advice_detail": advice_detail,
        "advice": advice,
    }


@lru_cache(maxsize=1)
def load_card_content() -> Dict[int, Dict[str, Any]]:
    """{card_id: {upright, reversed, finance_upright, finance_reversed}}."""
    if not os.path.exists(DOCX_PATH):
        logger.warning(f"타로 설명 docx 없음: {DOCX_PATH}")
        return {}

    try:
        paras = _read_paragraphs(DOCX_PATH)
    except Exception as e:
        logger.error(f"타로 docx 파싱 실패: {e}")
        return {}

    # 카드 헤더 위치 수집
    marks = []  # (para_idx, card_id, trailer, is_reversed, is_finance)
    for i, p in enumerate(paras):
        m = _HEADER_RE.match(p)
        if not m:
            continue
        cid = int(m.group(1))
        if cid > 21:
            continue
        trailer = (m.group(4) or "")
        paren = m.group(3) or ""
        is_reversed = ("역방향" in trailer) or ("역방향" in paren) or ("- 역방향" in p)
        marks.append((i, cid, trailer, is_reversed))

    # 재테크 섹션 시작 인덱스
    finance_start = None
    for i, p in enumerate(paras):
        if p.startswith("재테크 타로"):
            finance_start = i
            break

    result: Dict[int, Dict[str, Any]] = {}
    for k, (idx, cid, trailer, is_reversed) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(paras)
        body = [b for b in paras[idx + 1:end] if b != "카드의 설명"]
        parsed = _parse_block(trailer, body)

        is_finance = finance_start is not None and idx >= finance_start
        if is_finance:
            key = "finance_reversed" if is_reversed else "finance_upright"
        else:
            key = "reversed" if is_reversed else "upright"

        result.setdefault(cid, {})[key] = parsed

    return result


def get_card_reading(card_id: int, reversed_: bool, finance: bool) -> Dict[str, Any]:
    data = load_card_content().get(card_id, {})
    if finance:
        key = "finance_reversed" if reversed_ else "finance_upright"
    else:
        key = "reversed" if reversed_ else "upright"
    return data.get(key) or {"summary": None, "description": "", "advice_detail": "", "advice": ""}
