"""성격 원문에 이미 있는 특성만 고른다.

평생 사주와 성격운세가 문장을 나눌 때, 원국 해석에 없는 성향을 새로 만들지 않기 위한 표지다.
표지가 없다고 그 문장을 지우지는 않는다. 해당 관점의 덧붙임만 생략한다.
"""
import re

# 검출 순서를 고정해 같은 원문은 항상 같은 문단 순서가 되게 한다.
ORDER = ("vision", "autonomy", "lead", "drive", "finish", "scatter", "blunt", "heat")

_NEEDLES = {
    "vision": ("큰 그림", "넓은 시야", "스케일"),
    "autonomy": ("자유분방", "구속", "간섭", "규율", "자율", "내 뜻대로", "규제"),
    "lead": ("카리스마", "리더", "끌어모", "주도", "우두머리"),
    "drive": ("추진", "과감", "결단"),
    "finish": ("마무리", "끈기", "참을성"),
    "scatter": ("벌여", "여러 일", "많은 일", "분산"),
    "blunt": ("직설", "배려하지", "상처"),
    "heat": ("식어", "충동", "냄비"),
}


def matched(text: str):
    """원문에 표지가 있는 특성 이름. 없는 특성은 넣지 않는다."""
    body = text or ""
    return [name for name in ORDER if any(needle in body for needle in _NEEDLES[name])]


def shares(left: str, right: str, size: int = 18) -> bool:
    """공백을 뺀 뒤 같은 긴 조각이 있으면 문장이 겹친 것으로 본다."""
    return bool(_windows(left, size) & _windows(right, size))


def _windows(text: str, size: int):
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < size:
        return set()
    return {compact[i:i + size] for i in range(0, len(compact) - size + 1)}
