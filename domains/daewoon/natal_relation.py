"""원국 격국과 기존 오행 합계가 같은 그룹을 가리킬 때만 대운과의 관계를 문장에 쓴다.

새 가중치는 두지 않는다. 오행 점수는 analyze_strength가 저장한 elem_power를
기존 상생상극표로 그룹에 옮긴 합계다. 1위는 그 합계가 혼자 가장 클 때만 있다.
"""
from typing import Any, Dict, Optional

from core.constants import FIVE_ELEMENT_RELATIONS, GAN_ELEM
from core.sipsin import sipsin_group
from domains.daewoon.axis import to_past

_PRODUCES = {"비겁": "식상", "식상": "재성", "재성": "관성", "관성": "인성", "인성": "비겁"}
_CONTROLS = {"비겁": "재성", "재성": "인성", "인성": "식상", "식상": "관성", "관성": "비겁"}
_PRESSURE = ("규제", "맞섬")
_SMOOTH = ("순탄", "순하게")

_BODY = {
    "강화": "이 {span}은 사주에 이미 두꺼운 힘과 월령이 같은 쪽을 가리켜, 그 흐름이 이어집니다.",
    "표출": "이 {span}은 사주에 이미 실린 힘이 바깥의 다른 일로 이어져 나갑니다.",
    "보강": "이 {span}은 사주에 이미 있는 흐름을 받쳐 주는 조건이 붙습니다.",
    "규제": "이 {span}은 스스로 밀고 가던 힘 위에 바깥 기준이 올라섭니다.",
    "맞섬": "이 {span}은 사주에 이미 실린 힘이 들어온 기준을 밀어냅니다.",
}
_RIDER = {
    "규제": {
        "favorable": "그 기준이 버겁기만 한 것은 아니고, 맡은 일이 결과로 드러나기 쉬운 시기입니다.",
        "unfavorable": "그 기준은 힘을 보태기보다 부담으로 남기 쉽습니다.",
        "neutral": "그 기준의 무게는 한쪽으로 크게 기울지 않습니다.",
    },
    "맞섬": {
        "favorable": "그 맞섬이 버겁기만 한 것은 아니고, 맡은 일이 결과로 드러나기 쉬운 시기입니다.",
        "unfavorable": "그 맞섬은 힘을 보태기보다 부담으로 남기 쉽습니다.",
        "neutral": "그 맞섬의 세기는 한쪽으로 크게 기울지 않습니다.",
    },
}


def element_group_totals(day_master: str, elem_power: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """저장된 오행 점수를 일간 기준 다섯 그룹 합계로 옮긴다."""
    dm_elem = GAN_ELEM.get(day_master or "", "")
    totals: Dict[str, float] = {}
    for elem, value in (elem_power or {}).items():
        group = FIVE_ELEMENT_RELATIONS.get((dm_elem, elem))
        if not group:
            continue
        totals[group] = totals.get(group, 0.0) + float(value)
    return totals


def unique_group_leader(totals: Dict[str, float]) -> Optional[str]:
    """합계가 혼자 가장 큰 그룹만 1위다. 같으면 1위를 정하지 않는다."""
    if not totals:
        return None
    top = max(totals.values())
    leaders = [name for name, value in totals.items() if value == top]
    if len(leaders) != 1:
        return None
    return leaders[0]


def gyeok_group(saju: Dict[str, Any]) -> Optional[str]:
    raw = ((saju.get("gyeokguk") or {}).get("sipsin") or "")
    group = sipsin_group(raw)
    return group if group != "미정" else None


def agreed_natal_group(saju: Dict[str, Any]) -> Optional[str]:
    """격국 그룹과 오행 합계의 단독 1위가 같을 때만 그 그룹을 돌려준다."""
    strength = saju.get("strength") or {}
    leader = unique_group_leader(
        element_group_totals(saju.get("day_master") or "", strength.get("elem_power") or {})
    )
    frame = gyeok_group(saju)
    if leader and frame and leader == frame:
        return leader
    return None


def relation_between(natal_group: str, daewoon_group: str) -> Optional[str]:
    if not natal_group or not daewoon_group:
        return None
    if natal_group == daewoon_group:
        return "강화"
    if _PRODUCES.get(natal_group) == daewoon_group:
        return "표출"
    if _PRODUCES.get(daewoon_group) == natal_group:
        return "보강"
    if _CONTROLS.get(daewoon_group) == natal_group:
        return "규제"
    if _CONTROLS.get(natal_group) == daewoon_group:
        return "맞섬"
    return None


def decade_relation(saju: Dict[str, Any], daewoon_group: str) -> Optional[str]:
    natal = agreed_natal_group(saju)
    if not natal:
        return None
    return relation_between(natal, daewoon_group)


def relation_sentence(relation: str, span: str, polarity: str, past: bool = False) -> str:
    body = _BODY[relation].format(span=span)
    if relation in _PRESSURE:
        rider = _RIDER[relation].get(polarity) or _RIDER[relation]["neutral"]
        body = f"{body} {rider}"
    if past:
        body = to_past(body if body.endswith(".") else body + ".")
    return body


def without_smooth_clauses(text: str) -> str:
    """규제·맞섬 문장 옆에 순탄·순하게 절이 붙지 않게 그 절만 뺀다."""
    if not text or not any(mark in text for mark in _SMOOTH):
        return text
    kept = []
    for piece in text.split(". "):
        chunk = piece.strip()
        if not chunk or any(mark in chunk for mark in _SMOOTH):
            continue
        if not chunk.endswith("."):
            chunk += "."
        kept.append(chunk)
    return " ".join(kept).strip()


def scrub_smooth(value: Any) -> Any:
    if isinstance(value, str):
        if any(mark in value for mark in _SMOOTH) and ". " not in value and not value.endswith("."):
            return ""
        return without_smooth_clauses(value)
    if isinstance(value, list):
        scrubbed = []
        for item in value:
            if isinstance(item, str) and any(mark in item for mark in _SMOOTH):
                continue
            scrubbed.append(scrub_smooth(item))
        return scrubbed
    if isinstance(value, dict):
        return {key: scrub_smooth(item) for key, item in value.items()}
    return value
