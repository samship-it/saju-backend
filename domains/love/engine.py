"""내 사주가 끌어당기는 인연 — 순수 룰 조립.

입력은 calculate_saju 결과(또는 같은 키를 가진 명식)뿐이다.
네트워크·DB·LLM 호출이 없다. 같은 명식은 항상 같은 문장이다.
"""
from typing import Any, Dict, Optional, Tuple

from core.constants import FIVE_ELEMENT_RELATIONS, GAN_ELEM, SAMHAP, YUKHAP
from core.sipsin import calculate_sipsin, sipsin_group
from domains.love.fragments import (
    CHIP, DATE_TIP, ELEMENTS, FACT, FACT_AND, FACT_SUBJECT, FALLBACK, NEED,
    PALACE, PERSON, PERSONALITY, SPOUSE_OPEN, SPOUSE_QUIET,
)

# 오미합은 상수표에 토가 빠져 있다. 전통 합화는 토.
_YUKHAP_ELEM = {
    "자축합토": "토",
    "인해합목": "목",
    "묘술합화": "화",
    "진유합금": "금",
    "사신합수": "수",
    "오미합": "토",
}


def yukhap_of(branch: str) -> Tuple[Optional[str], Optional[str]]:
    """일지와 육합인 지지, 그리고 그 합이 만드는 오행."""
    for pair, name in YUKHAP.items():
        if branch in pair:
            other = next(b for b in pair if b != branch)
            return other, _YUKHAP_ELEM.get(name)
    return None, None


def samhap_of(branch: str) -> Optional[str]:
    """일지가 속한 삼합의 오행. 없으면 None."""
    for group, elem in SAMHAP.items():
        if branch in group:
            return elem
    return None


def _power(elem_power: Dict[str, Any]) -> Dict[str, float]:
    out = {}
    for elem in ELEMENTS:
        try:
            out[elem] = float(elem_power.get(elem, 0) or 0)
        except (TypeError, ValueError):
            out[elem] = 0.0
    return out


def _first_known(values, allowed) -> Optional[str]:
    for value in values or []:
        if value in allowed:
            return value
    return None


def build_ideal_partner(saju: Dict[str, Any]) -> Tuple[dict, bool]:
    """진단 4필드. 매칭에 필요한 명식이 없으면 고정 폴백과 is_fallback=True."""
    if not isinstance(saju, dict):
        return _copy_fallback(), True

    day_master = saju.get("day_master") or ""
    day_branch = saju.get("day_branch") or ""
    strength = saju.get("strength") if isinstance(saju.get("strength"), dict) else {}
    elem_power = _power(strength.get("elem_power") or {})
    dm_elem = GAN_ELEM.get(day_master) or strength.get("day_master_elem") or ""

    if not day_master or not day_branch or dm_elem not in ELEMENTS or not strength.get("elem_power"):
        return _copy_fallback(), True

    yongsin = _first_known(strength.get("yongsin"), ELEMENTS)
    heesin = _first_known(strength.get("heesin"), ELEMENTS)
    zeros = [elem for elem in ELEMENTS if elem_power[elem] <= 0]
    complement = yongsin or (zeros[0] if zeros else min(ELEMENTS, key=lambda e: (elem_power[e], ELEMENTS.index(e))))
    if heesin == complement:
        heesin = None

    group = FIVE_ELEMENT_RELATIONS.get((dm_elem, complement), "인성")
    if group not in PERSONALITY:
        group = "인성"
    palace_star = (saju.get("sipsin") or {}).get("day_ji")
    if not palace_star:
        palace_star = calculate_sipsin(day_master, day_branch, is_gan=False)
    palace_group = sipsin_group(palace_star)
    if palace_group not in PALACE:
        palace_group = "인성"

    spouse = saju.get("spouse_star") if isinstance(saju.get("spouse_star"), dict) else {}
    spouse_present = bool(spouse.get("present"))
    _, hap_elem = yukhap_of(day_branch)
    if hap_elem not in DATE_TIP:
        hap_elem = "토"
    trio = samhap_of(day_branch)

    personality_type, personality_text = PERSONALITY[group]
    data = {
        "user_diagnosis": _diagnosis(elem_power),
        "complement_element": _complement(complement, heesin, personality_type),
        "partner_personality": {"type": personality_type, "text": personality_text},
        "partner_synergy_tip": _synergy(spouse_present, hap_elem, palace_group, trio),
    }
    return data, False


def _join_facts(elems) -> str:
    """목(木)과 불(火)처럼 잇는다. 조사는 앞 글자 읽기 기준."""
    if len(elems) == 1:
        return FACT[elems[0]]
    if len(elems) == 2:
        return f"{FACT[elems[0]]}{FACT_AND[elems[0]]} {FACT[elems[1]]}"
    head = ", ".join(FACT[elem] for elem in elems[:-1])
    return f"{head}{FACT_AND[elems[-2]]} {FACT[elems[-1]]}"


def _by_power(elems, elem_power: Dict[str, float], reverse: bool):
    return sorted(elems, key=lambda elem: (elem_power[elem], -ELEMENTS.index(elem)), reverse=reverse)


def _diagnosis(elem_power: Dict[str, float]) -> str:
    """원국에서 강한 기운과 비거나 얇은 기운을 이름으로 짚고, 그 과다·부족을 풀어 쓴다."""
    peak = max(elem_power.values())
    if peak <= 0:
        named = _join_facts(list(ELEMENTS))
        return (
            f"{named} 기운이 모두 얇게 깔린 사주예요. "
            "어느 기운도 두드러지지 않고, 자리마다 비어 있는 쪽에 가깝습니다."
        )

    excess = _by_power(
        [elem for elem in ELEMENTS if elem_power[elem] >= peak * 0.8 and elem_power[elem] > 0],
        elem_power,
        reverse=True,
    )
    absent = _by_power([elem for elem in ELEMENTS if elem_power[elem] <= 0], elem_power, reverse=False)
    floor = min(elem_power.values())
    thin = _by_power(
        [elem for elem in ELEMENTS if elem not in excess and abs(elem_power[elem] - floor) <= 1e-9],
        elem_power,
        reverse=False,
    )
    excess_s = _join_facts(excess)

    if absent:
        lack_s = _join_facts(absent)
        return (
            f"{excess_s} 기운이 강하고 {lack_s} 기운이 결핍된 사주예요. "
            f"{NEED[excess[0]]}은 넘치고, {NEED[absent[0]]}은 비어 있습니다."
        )
    if thin and floor < peak * 0.5:
        lack_s = _join_facts(thin)
        return (
            f"{excess_s} 기운이 강하고 {lack_s} 기운이 부족한 사주예요. "
            f"{NEED[excess[0]]}은 넘치고, {NEED[thin[0]]}은 얇습니다."
        )
    return (
        f"{excess_s} 기운이 고르게 놓인 사주예요. "
        "어느 한쪽이 특별히 넘치거나 비어 있지는 않습니다."
    )


def _complement(element: str, support: Optional[str], personality_type: str) -> dict:
    """앞 진단에 이어, 상대에게 필요한 오행과 성향을 이름으로 추천한다."""
    wanted = [element] if not support else [element, support]
    developed = _join_facts(wanted) + FACT_SUBJECT[wanted[-1]]
    text = (
        f"그래서 {developed} 발달한 상대가 잘 맞아요. "
        f"{PERSON[element]}이라, {personality_type}으로 나를 보완합니다."
    )
    if support:
        text += f" {FACT[support]} 기운이 함께 있으면 그 보완이 더 편해집니다."
    return {
        "element": element,
        "label": CHIP[element],
        "support_element": support,
        "support_label": CHIP[support] if support else None,
        "text": text,
    }


def _synergy(spouse_present: bool, hap_elem: str, palace_group: str, trio: Optional[str]) -> str:
    parts = [
        SPOUSE_OPEN if spouse_present else SPOUSE_QUIET,
        DATE_TIP[hap_elem],
        PALACE[palace_group],
    ]
    if trio in CHIP and trio != hap_elem:
        parts.append(f"오래 같이 있을수록 {CHIP[trio]}이 관계를 받쳐 줘요.")
    return " ".join(parts)


def _copy_fallback() -> dict:
    src = FALLBACK
    return {
        "user_diagnosis": src["user_diagnosis"],
        "complement_element": dict(src["complement_element"]),
        "partner_personality": dict(src["partner_personality"]),
        "partner_synergy_tip": src["partner_synergy_tip"],
    }
