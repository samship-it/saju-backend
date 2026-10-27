"""Swap a repeated stock phrase in a stored yearly one-line.

The stored sentence stays. Only a shared heat phrase such as "뜨거운 열정"
is rewritten so each category does not open on the same words. No new event
is added, and the rest of the sentence is left as stored.
"""
import re
from functools import lru_cache
from typing import Dict, Tuple

from domains.yearly import content_db as _db

_PLAIN = (
    "overall", "health", "career_change", "business",
    "wealth", "love", "travel", "hobby",
)
_STAGES = ("s10", "s20", "s30_plus")
_KEEP = ("overall", "health", "study", "career_change", "business", "wealth", "love", "travel", "hobby")
# Longest first, so a short stem is not replaced inside a longer phrase.
_PHRASES = ("뜨거운 열정", "강한 열정", "뜨거운 열망", "열정", "열망")
_FAMILY = ("열정", "열망", "폭발", "불꽃")
_ALT = {
    "overall": "강한 기운",
    "health": "활력이 넘치는 기운",
    "study": "긍정적인 흐름",
    "career_change": "추진력이 살아나는 흐름",
    "business": "일을 밀어붙이는 기운",
    "wealth": "힘이 실리는 흐름",
    "love": "마음이 살아나는 흐름",
    "travel": "움직이는 기운",
    "hobby": "하고 싶은 기운",
}


def _hits(line: str) -> bool:
    return any(word in (line or "") for word in _FAMILY)


def _swap(line: str, phrase: str, alt: str) -> str:
    if phrase == "열정":
        return re.sub(r"열정(?!적)", alt, line)
    if phrase == "열망":
        return line.replace("열망", alt)
    return line.replace(phrase, alt)


def rewrite_repeated_phrase(category: str, line: str, group: Dict[str, str]) -> str:
    """Return the stored line, with the shared heat phrase changed for this category."""
    text = line or ""
    holders = [name for name, sample in group.items() if sample and _hits(sample)]
    if category not in holders or len(holders) < 3:
        return text
    keeper = next(name for name in _KEEP if name in holders)
    if category == keeper:
        return text
    alt = _ALT.get(category)
    if not alt:
        return text
    rewritten = text
    for phrase in _PHRASES:
        if phrase in rewritten:
            rewritten = _swap(rewritten, phrase, alt)
    if rewritten != text:
        rewritten = rewritten.replace("폭발적인 ", "").replace("불꽃같은 ", "")
        rewritten = re.sub(r"[ \t]{2,}", " ", rewritten).strip()
    return rewritten


@lru_cache(maxsize=512)
def _bundle(ilju: str, seun: str) -> Tuple[Tuple[str, str], ...]:
    rows = []
    for category in _PLAIN:
        entry = _db.lookup(category, ilju, seun, required=("one_line",))
        rows.append((category, str((entry or {}).get("one_line") or "")))
    for stage in _STAGES:
        entry = _db.lookup(
            "study", ilju, seun, required=("one_line",), key=f"{ilju}_{seun}_{stage}",
        )
        rows.append((f"study:{stage}", str((entry or {}).get("one_line") or "")))
    return tuple(rows)


def vary_repeated_phrase(
    category: str,
    ilju: str,
    seun: str,
    one_line: str,
    study_stage: str = "",
) -> str:
    """Serve the stored one-line, varying it only when the heat phrase is shared."""
    if not ilju or not seun or not (one_line or "").strip():
        return one_line or ""
    stored = {key: line for key, line in _bundle(ilju, seun)}
    stage = study_stage if study_stage in _STAGES else "s30_plus"
    group = {name: stored.get(name, "") for name in _PLAIN}
    group["study"] = stored.get(f"study:{stage}", "")
    key = "study" if category == "study" else category
    return rewrite_repeated_phrase(key, one_line, group)
