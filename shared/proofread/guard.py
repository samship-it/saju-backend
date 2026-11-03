"""LLM 수정이 점수, 간지, 명리 용어, 문장 길이를 바꾸면 거절한다."""
import re

_DIGITS = re.compile(r"\d+")
_HANJA = re.compile(r"[甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]")
_TERMS = (
    "십신", "오행", "천간", "지지", "일간", "일지", "원국", "용신", "희신", "기신",
    "신강", "신약", "대운", "세운", "일주", "도화", "육합", "삼합",
    "식신", "상관", "정재", "편재", "정관", "편관", "정인", "편인", "비견", "겁재",
)

APPLY_TYPES = frozenset({"spelling", "spacing", "particle", "punctuation", "typo"})
MIN_CONFIDENCE = 0.85


def same_facts(before: str, after: str) -> bool:
    if _DIGITS.findall(before) != _DIGITS.findall(after):
        return False
    if _HANJA.findall(before) != _HANJA.findall(after):
        return False
    for term in _TERMS:
        if before.count(term) != after.count(term):
            return False
    if not after.strip():
        return False
    if len(after) > int(len(before) * 1.25) + 12:
        return False
    if len(after) + 12 < int(len(before) * 0.75):
        return False
    return True


def accept_edit(text: str, edit: dict) -> bool:
    if not isinstance(edit, dict):
        return False
    try:
        confidence = float(edit.get("confidence", 0))
    except (TypeError, ValueError):
        return False
    if confidence < MIN_CONFIDENCE:
        return False
    if str(edit.get("error_type") or "") not in APPLY_TYPES:
        return False
    src = str(edit.get("original") or "")
    dst = str(edit.get("suggestion") or "")
    if not src or src == dst or text.count(src) != 1:
        return False
    if not same_facts(src, dst):
        return False
    return same_facts(text, text.replace(src, dst, 1))


def apply_edits(text: str, edits) -> str:
    out = text
    for edit in edits or []:
        if not accept_edit(out, edit):
            continue
        out = out.replace(str(edit["original"]), str(edit["suggestion"]), 1)
    return out
