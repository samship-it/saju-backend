"""규칙으로 확실한 맞춤법만 고친다. 외부 맞춤법 API 는 쓰지 않는다.

명리 용어가 잘못 붙은 표현은 찾아서 기록만 한다. 직업이나 해석을 만들어 넣지 않는다.
"""
import re
from typing import Dict, List, Tuple

# 긴 표현을 먼저 바꾼다.
_TYPOS: Tuple[Tuple[str, str], ...] = (
    ("않을때", "않을 때"),
    ("어떨때", "어떨 때"),
    ("어떻해", "어떻게"),
    ("맞춤뻡", "맞춤법"),
    ("될때", "될 때"),
    ("볼때", "볼 때"),
    ("할때", "할 때"),
    ("됬", "됐"),
)

# 고치면 해석이 바뀌므로 탐지만 한다.
_SAJU_MASHUPS = (
    "식살한",
    "식상한 영업",
    "식신한 ",
)

_ISSUE = Dict[str, str]


def correct(text: str) -> Tuple[str, List[_ISSUE]]:
    if not text:
        return text, []
    issues: List[_ISSUE] = []
    for bad in _SAJU_MASHUPS:
        if bad in text:
            issues.append({
                "type": "saju_mashup",
                "original": bad,
                "applied": "false",
            })
    out = text
    for bad, good in _TYPOS:
        if bad not in out:
            continue
        out = out.replace(bad, good)
        issues.append({"type": "spelling", "original": bad, "applied": "true"})
    spaced = re.sub(r"[ \t]{2,}", " ", out)
    if spaced != out:
        issues.append({"type": "spacing", "original": "  ", "applied": "true"})
        out = spaced
    return out, issues
