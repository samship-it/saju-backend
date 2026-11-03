"""대운 문단 37,800칸. 요청에 없는 사주도 이 칸 중 하나로 떨어진다.

일간 오행 5 × 강약 7 × 성향 6 × 간지 60 × 나이 3 = 37,800.
용신 목록과 대운 관계는 이 키에서 다시 계산되므로 키에 넣지 않는다.
"""
from typing import Dict, Iterator, List, Optional, Tuple

from core.constants import FIVE_ELEMENT_RELATIONS, GAN, GAN_ELEM, JI, JI_ELEM, SHENG
from domains.daewoon.natal_relation import relation_between

ELEMENTS = ("목", "화", "토", "금", "수")
GROUPS = ("비겁", "식상", "재성", "관성", "인성")
STRENGTHS = ("신강", "신약", "중화-목", "중화-화", "중화-토", "중화-금", "중화-수")
TENDENCIES = ("none",) + GROUPS
AGE_BANDS = ("school", "span", "adult")
GANJI: Tuple[str, ...] = tuple(GAN[i % 10] + JI[i % 12] for i in range(60))

_THEME = {
    "비겁": "스스로 버티고 곁과 몫을 나누는 힘",
    "식상": "만들고 드러내는 일",
    "재성": "결과와 살림",
    "관성": "기준, 역할, 책임",
    "인성": "배움과 돌봄",
}
_SEASON = {
    "寅": "봄", "卯": "봄", "巳": "여름", "午": "여름",
    "申": "가을", "酉": "가을", "亥": "겨울", "子": "겨울",
    "辰": "환절", "未": "환절", "戌": "환절", "丑": "환절",
}


def age_band(start_age: int) -> str:
    """10년 구간의 시작 나이. 끝 나이는 시작+9다."""
    if start_age <= 9:
        return "school"
    if start_age <= 18:
        return "span"
    return "adult"


def strength_state(verdict: str, elem_power: Optional[Dict[str, float]]) -> str:
    if verdict == "신강":
        return "신강"
    if verdict == "신약":
        return "신약"
    order = list(ELEMENTS)
    power = elem_power or {}
    weakest = min(order, key=lambda name: float(power.get(name, 0.0)))
    return f"중화-{weakest}"


def prose_key(dm_elem: str, strength: str, tendency: str, ganji: str, band: str) -> str:
    return "|".join((dm_elem, strength, tendency or "none", ganji, band))


def iter_keys() -> Iterator[str]:
    for dm in ELEMENTS:
        for strength in STRENGTHS:
            for tendency in TENDENCIES:
                for ganji in GANJI:
                    for band in AGE_BANDS:
                        yield prose_key(dm, strength, tendency, ganji, band)


def parse_key(key: str) -> Tuple[str, str, str, str, str]:
    dm, strength, tendency, ganji, band = key.split("|")
    return dm, strength, tendency, ganji, band


def _elem_for_group(dm_elem: str, group: str) -> str:
    for elem in ELEMENTS:
        if FIVE_ELEMENT_RELATIONS[(dm_elem, elem)] == group:
            return elem
    return ""


def _roles(dm_elem: str, strength: str) -> Tuple[List[str], List[str], List[str]]:
    """analyze_strength와 같은 순서로 용신·기신·희신을 고른다. 점수는 다시 더하지 않는다."""
    if strength == "신강":
        yong_groups, gi_groups = ["관성", "식상", "재성"], ["인성", "비겁"]
    elif strength == "신약":
        yong_groups, gi_groups = ["인성", "비겁"], ["재성", "관성", "식상"]
    else:
        weakest = strength.split("-", 1)[1]
        yong_groups, gi_groups = [FIVE_ELEMENT_RELATIONS[(dm_elem, weakest)]], []
    yong = [_elem_for_group(dm_elem, group) for group in yong_groups if _elem_for_group(dm_elem, group)][:2]
    gi = [_elem_for_group(dm_elem, group) for group in gi_groups if _elem_for_group(dm_elem, group)][:2]
    hee: List[str] = []
    for elem in yong:
        for source, target in SHENG.items():
            if target == elem and source not in hee and source not in gi and source not in yong:
                hee.append(source)
    return yong, gi, hee[:2]


def polarity_for(dm_elem: str, strength: str, stem_elem: str) -> str:
    yong, gi, hee = _roles(dm_elem, strength)
    if stem_elem in gi:
        return "unfavorable"
    if stem_elem in yong or stem_elem in hee:
        return "favorable"
    return "neutral"


def next_ganji(ganji: str) -> str:
    return GANJI[(GANJI.index(ganji) + 1) % 60]


def is_pair_front(dm_elem: str, ganji: str) -> bool:
    nxt = next_ganji(ganji)
    return FIVE_ELEMENT_RELATIONS[(dm_elem, GAN_ELEM[ganji[0]])] == FIVE_ELEMENT_RELATIONS[(dm_elem, GAN_ELEM[nxt[0]])]


def prompt_facts(key: str) -> Dict[str, object]:
    dm, strength, tendency, ganji, band = parse_key(key)
    stem, branch = ganji[0], ganji[1]
    stem_elem = GAN_ELEM[stem]
    group = FIVE_ELEMENT_RELATIONS[(dm, stem_elem)]
    nxt = next_ganji(ganji)
    paired = is_pair_front(dm, ganji)
    relation = None if tendency == "none" else relation_between(tendency, group)
    return {
        "key": key,
        "day_master_element": dm,
        "strength": strength,
        "tendency": tendency,
        "ganji": ganji,
        "group_theme": _THEME[group],
        "season": _SEASON[branch],
        "branch_element": JI_ELEM[branch],
        "polarity": polarity_for(dm, strength, stem_elem),
        "relation": relation,
        "age_band": band,
        "paired": paired,
        "next_ganji": nxt if paired else "",
        "next_season": _SEASON[nxt[1]] if paired else "",
        "next_theme": _THEME[FIVE_ELEMENT_RELATIONS[(dm, GAN_ELEM[nxt[0]])]] if paired else "",
    }
