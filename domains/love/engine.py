"""내 사주가 끌어당기는 인연 — 순수 룰 조립.

입력은 calculate_saju 결과(또는 같은 키를 가진 명식)뿐이다.
네트워크·DB·LLM 호출이 없다. 같은 명식은 항상 같은 문장이다.
"""
from typing import Any, Dict, Optional, Tuple

from core.constants import FIVE_ELEMENT_RELATIONS, GAN_ELEM, SAMHAP, YUKHAP
from core.sipsin import calculate_sipsin, sipsin_group
from domains.love.fragments import (
    CHIP, DATE_TIP, ELEMENTS, FALLBACK, NEED, PALACE, PERSON, PERSONALITY,
    SPOUSE_OPEN, SPOUSE_QUIET,
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
    gap = complement if complement in zeros else (zeros[0] if zeros else None)
    if heesin == complement:
        heesin = None

    strongest = max(ELEMENTS, key=lambda e: (elem_power[e], -ELEMENTS.index(e)))
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
        "user_diagnosis": _diagnosis(strongest, gap, complement, elem_power[strongest]),
        "complement_element": _complement(complement, heesin),
        "partner_personality": {"type": personality_type, "text": personality_text},
        "partner_synergy_tip": _synergy(spouse_present, hap_elem, palace_group, trio),
    }
    return data, False


def _diagnosis(strongest: str, gap: Optional[str], complement: str, strong_power: float) -> str:
    if strong_power <= 0:
        return f"다섯 기운이 모두 얇게 깔린 사주예요. 곁에서 더해 주면 좋은 건 {NEED[complement]}입니다."
    if gap and gap == complement and strongest != gap:
        return (
            f"{NEED[strongest]}은 두드러지고, {NEED[gap]}은 비어 있는 사주예요. "
            "그 빈자리를 채워 주는 사람이 가장 잘 맞습니다."
        )
    if gap and gap != complement:
        return (
            f"{NEED[strongest]}은 두드러지고, {NEED[gap]}은 비어 있는 사주예요. "
            f"곁에서 더해 주면 좋은 건 {NEED[complement]}입니다."
        )
    if strongest == complement:
        return f"{NEED[strongest]}이 이미 두드러진 사주예요. 같은 결을 가진 사람이 곁에 있으면 그 힘이 더 또렷해집니다."
    return f"{NEED[strongest]}이 두드러진 사주예요. 그중 더 채워 주면 좋은 건 {NEED[complement]}입니다."


def _complement(element: str, support: Optional[str]) -> dict:
    text = f"내게 필요한 핵심은 {CHIP[element]}이에요. {PERSON[element]}이 그 자리를 채워 줍니다."
    if support:
        text += f" 그 힘을 북돋우는 {CHIP[support]}이 함께 있으면 더 편해요."
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
