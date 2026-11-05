"""한 편 운세에서 '올해'와 같은 뜻의 반복이 세 번을 넘지 않게 한다.

생성 뒤 후처리와 저장된 본문을 고칠 때만 쓴다.
조회 중 맞춤법만 보는 단계에서는 문장을 지우거나 다시 쓰지 않는다.

다른 명사를 가운데서 빼면 '의견'이 '견'처럼 깨진다.
그래서 올해와 아래 다섯 묶음만 고치고, 빼면 문장이 무너지면 그 문장을 통째로 뺀다.
어색한 동의어는 넣지 않는다.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

MAX_USES = 2

# 같은 뜻으로 반복되면 한 묶음으로 센다.
FAMILIES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("올해", ("올해",)),
    ("변화", ("변화", "변동", "급변", "변동성")),
    ("안정", ("안정", "안정감", "평온")),
    ("마음", ("마음", "진심", "감정")),
    ("수입", ("수입", "소득", "수익")),
    ("기회", ("기회", "가능성", "계기")),
)
_FAMILY_LABELS = frozenset(label for label, _ in FAMILIES)

_PARTICLE = (
    "에서는", "으로는", "에게는", "한테는", "까지는", "부터는", "에서도", "으로도",
    "이라도", "라도", "만큼은", "일수록", "야말로", "랍니다", "입니다", "뿐만",
    "에서", "으로", "까지", "부터", "처럼", "보다", "에게", "한테", "만큼",
    "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "만", "로",
    "예요", "에요",
)
_ATTR = (
    "적으로", "적인", "스럽게", "스러운", "스런", "하고", "하며",
    "적", "감", "성", "형", "원", "한", "된", "히", "해",
)

_TOKEN = re.compile(r"[가-힣]+")
_SENTENCE = re.compile(r"(?<=[\.!?…])\s+")
_MODIFIER_END = re.compile(r"(?:적인|적으로|스럽게|스러운|하고|하며|한|된|히)$")
_END = re.compile(r"(?:요|다|까|죠|니다|세요|예요|에요|입니다|해요)[.!?…]*$")
# 문장 앞에 떨어진 조사만 걷어 낸다. '이 과정에서'의 '이'는 지시사라 그대로 둔다.
_BAD_START = re.compile(r"^(?:으로|에서|에게|한테|[은는을를의와과도에])(?:\s+|$)")
_LEAD = re.compile(r"^(?:그리고|또한|또|그래서|그러나|다만|그런데)\s+")

REPETITION_RULE = """[반복 제한 — 최우선]
- 한 편의 제목, 소제목, 본문을 통틀어 같은 단어는 두 번까지만 씁니다. 주제를 강조하는 단어도 같습니다.
- '올해'는 두 번까지만 씁니다. 소제목마다 '올해'를 붙이지 않습니다. 뜻이 통하면 '연애 전체 흐름', '나의 수입 스타일', '투자·재테크 운'처럼 짧게 씁니다.
- 비슷한 뜻도 한 묶음으로 두 번까지입니다. 변화·변동·급변·변동성 / 안정·안정감·평온 / 마음·진심·감정 / 수입·소득·수익 / 기회·가능성·계기.
- 어색한 동의어로 바꾸지 않습니다. 문장을 다시 짜거나, 같은 말이 또 필요 없이 나오는 문장은 빼세요.
- '이번 년도', '금년'도 쓰지 않습니다."""

_SKIP_KEYS = frozenset({
    "concept_object", "keywords", "content_type", "category", "verdict",
    "day_master", "ganji", "status", "code", "nickname",
})
_FIELD_ORDER = (
    "one_line", "headline", "overall_flow", "first_half", "second_half", "advice",
    "opportunity_month", "caution_month", "cheat_key", "trap_warning",
    "income_style", "spending_pattern", "investment_luck",
    "meeting_style", "relationship_depth", "caution_point",
    "business_traits", "direction", "expansion_timing", "partner_luck",
    "job_change_eval", "opportunity_style", "ideal_environment", "timing_flow",
    "stay_summary", "move_summary",
    "care_points", "recovery_method",
    "travel_style", "travel_luck", "recommended_spots",
    "active_activities", "solo_vs_group", "benefits",
    "study_style", "focus_and_achievement", "recommended_fields",
    "analysis",
)


_YEAR_PREFIX = re.compile(
    r"^올해(?:만큼은|일수록|야말로|랍니다|입니다|뿐만|만큼|예요|에요|의|는|를|가|에|도|와|과|로)?"
)


def _is_tail(rest: str) -> bool:
    s = rest
    changed = True
    while s and changed:
        changed = False
        for tail in _ATTR + _PARTICLE:
            if s.startswith(tail):
                s = s[len(tail):]
                changed = True
                break
    return s == ""


def family_of(token: str) -> Optional[str]:
    prefix = _YEAR_PREFIX.match(token)
    if token.startswith("올해") and prefix and (prefix.end() == len(token) or len(token) - prefix.end() >= 1):
        return "올해"
    for label, stems in FAMILIES:
        for stem in sorted(stems, key=len, reverse=True):
            if token.startswith(stem) and _is_tail(token[len(stem):]):
                return label
    return None


def _split(text: str) -> List[str]:
    parts = [p.strip() for p in _SENTENCE.split(text or "") if p and p.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def _tidy(text: str) -> str:
    s = re.sub(r"[ \t]{2,}", " ", text)
    s = re.sub(r"\s+([,.!?…])", r"\1", s)
    s = _LEAD.sub("", s.strip())
    s = _BAD_START.sub("", s.strip())
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def _readable(text: str) -> bool:
    s = text.strip()
    if len(s) < 8 or _BAD_START.match(s) or not _END.search(s):
        return False
    return True


def _omit_span(sentence: str, start: int, end: int) -> str:
    return _tidy(sentence[:start] + sentence[end:])


def limit_prose(parts: Sequence[str]) -> List[str]:
    """읽히는 순서의 문단에서 올해와 같은 뜻 묶음을 두 번까지 남긴다."""
    counts: Dict[str, int] = {}
    out: List[str] = []
    for part in parts:
        sentences = _split(part)
        kept: List[str] = []
        for index, sentence in enumerate(sentences):
            reduced, blocked = _strip_excess(sentence, counts)
            remaining_after = len(sentences) - index - 1
            if blocked and len(kept) >= 1 and len(kept) + remaining_after >= 3:
                continue
            if not reduced.strip():
                if len(kept) >= 1:
                    continue
                reduced = _tidy(sentence) or sentence.strip()
            for match in _TOKEN.finditer(reduced):
                if _protected(reduced, match.start(), match.end()):
                    continue
                label = family_of(match.group())
                if label:
                    counts[label] = counts.get(label, 0) + 1
            kept.append(reduced)
        if not kept and (part or "").strip():
            kept = [_tidy(part) or part.strip()]
        joiner = "\n\n" if "\n" in (part or "") else " "
        out.append(joiner.join(s for s in kept if s.strip()))
    return out


def _can_omit(sentence: str, label: str, start: int, end: int, token_start: int) -> bool:
    """올해는 빼고, 다른 말은 문장이 남을 때만 뺀다."""
    token = sentence[start:end]
    if label == "올해":
        return True
    head = token.split()[-1]
    prev = sentence[:start].rstrip()
    guarded = prev.endswith(("한", "된", "적", "인", "운")) and not _MODIFIER_END.search(head)
    subject = head.endswith(("이", "은", "는", "의")) and not head.endswith(("을", "를"))
    adverb_object = head.endswith(("을", "를")) and prev.endswith(("게", "히"))
    if not _MODIFIER_END.search(head) and (guarded or not (subject or adverb_object)):
        return False
    if token.endswith(("과", "와", "이나")) and start == token_start:
        return False
    return _readable(_omit_span(sentence, start, end))


def _strip_excess(sentence: str, counts: Dict[str, int]) -> Tuple[str, bool]:
    """초과한 올해·묶음 낱말을 뺀다. 올해는 같은 문장의 다른 반복과 상관없이 뺀다."""
    seen: Dict[str, int] = {}
    marks: List[Tuple[str, int, int]] = []
    for match in _TOKEN.finditer(sentence):
        if _protected(sentence, match.start(), match.end()):
            continue
        label = family_of(match.group())
        if not label:
            continue
        used = counts.get(label, 0) + seen.get(label, 0)
        if used >= MAX_USES:
            end = match.end()
            if label == "올해":
                prefix = _YEAR_PREFIX.match(match.group())
                if prefix and prefix.end() < len(match.group()):
                    end = match.start() + prefix.end()
            marks.append((label, match.start(), end))
        else:
            seen[label] = seen.get(label, 0) + 1
    delete: List[Tuple[int, int]] = []
    blocked = False
    for label, start, end in marks:
        wide_start, wide_end = _extend_pair(sentence, start, end)
        wide_end = _extend_year_modifier(sentence, label, wide_start, wide_end)
        if _can_omit(sentence, label, wide_start, wide_end, start):
            delete.append((wide_start, wide_end))
        else:
            blocked = True
    if not delete:
        return _tidy(sentence), blocked
    delete.sort()
    merged: List[Tuple[int, int]] = []
    for start, end in delete:
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces: List[str] = []
    last = 0
    for start, end in merged:
        pieces.append(sentence[last:start])
        last = end
    pieces.append(sentence[last:])
    return _tidy("".join(pieces)), blocked


def _extend_pair(sentence: str, start: int, end: int) -> Tuple[int, int]:
    """'고정 수입과'처럼 앞 명사와 붙은 반복은 앞 명사까지 함께 뺀다."""
    token = sentence[start:end]
    if token.endswith(("과", "와")):
        prev = re.search(r"[가-힣]+\s*$", sentence[:start])
        if prev:
            return prev.start(), end
    return start, end


def _extend_year_modifier(sentence: str, label: str, start: int, end: int) -> int:
    """'올해를 관통하는'처럼 목적어가 빠진 꾸밈말은 함께 뺀다."""
    if label != "올해" or not sentence[start:end].endswith(("를", "을", "가", "이")):
        return end
    rest = sentence[end:]
    match = re.match(r"\s*[가-힣]{1,8}는(?=\s)", rest)
    return end + match.end() if match else end


def _protected(sentence: str, start: int, end: int) -> bool:
    """상품 이름 '기회의 달'은 반복으로 세지 않는다."""
    token = sentence[start:end]
    if not token.startswith("기회"):
        return False
    return sentence[end:].lstrip().startswith("달")


def _excess_span(sentence: str, counts: Dict[str, int]) -> Optional[Tuple[str, int, int]]:
    seen: Dict[str, int] = {}
    for match in _TOKEN.finditer(sentence):
        if _protected(sentence, match.start(), match.end()):
            continue
        label = family_of(match.group())
        if not label:
            continue
        used = counts.get(label, 0) + seen.get(label, 0)
        if used >= MAX_USES:
            return label, match.start(), match.end()
        seen[label] = seen.get(label, 0) + 1
    return None


def over_limit(parts: Iterable[str], labels: Optional[Iterable[str]] = None) -> Dict[str, int]:
    """세 번 이상 남은 묶음. 수정 뒤 다시 검사할 때 쓴다."""
    wanted = set(labels) if labels is not None else set(_FAMILY_LABELS)
    counts: Dict[str, int] = {}
    for part in parts:
        text = part or ""
        for match in _TOKEN.finditer(text):
            if _protected(text, match.start(), match.end()):
                continue
            label = family_of(match.group())
            if label in wanted:
                counts[label] = counts.get(label, 0) + 1
    return {label: n for label, n in counts.items() if n > MAX_USES}


def limit_entry(entry: dict) -> dict:
    """고객 문장 칸만 고친다. 점수, 키워드, 상징 오브젝트, 판정값은 그대로 둔다."""
    if not isinstance(entry, dict):
        return entry
    slots: List[Tuple[Union[str, Tuple[str, str]], str]] = []
    seen = set()

    def add(slot, text: str) -> None:
        if slot in seen or not isinstance(text, str):
            return
        seen.add(slot)
        slots.append((slot, text))

    for name in _FIELD_ORDER:
        if isinstance(entry.get(name), str):
            add(name, entry[name])
    for name, value in entry.items():
        if name.startswith("_") or name in _SKIP_KEYS:
            continue
        if isinstance(value, str):
            add(name, value)
        elif isinstance(value, dict):
            for sub, sub_value in value.items():
                if sub in _SKIP_KEYS or sub.endswith("_score"):
                    continue
                if isinstance(sub_value, str) and (_END.search(sub_value.strip()) or len(sub_value) >= 40):
                    add((name, sub), sub_value)
    limited = limit_prose([text for _, text in slots])
    for (slot, _), text in zip(slots, limited):
        if isinstance(slot, tuple):
            entry[slot[0]][slot[1]] = text
        else:
            entry[slot] = text
    return entry
