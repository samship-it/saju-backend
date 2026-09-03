"""분야별 파생 데이터 & '작용 강도 지표' 산출.

여기서는 사람이 읽을 문장을 만들지 않는다. Gemini 프롬프트에 넘길 구조화 데이터만 만든다.
점수(0~100)는 Python이 정하지 않고 AI가 이 강도 지표를 근거로 산출한다.
"""
from typing import Dict, Any, List, Optional
from collections import Counter

from core.constants import JIJANGGAN, GAN_ELEM
from core.sipsin import calculate_sipsin, sipsin_group

_GROUPS = ["비겁", "식상", "재성", "관성", "인성"]


def _weighted_group_counts(day_master: str, pillars: Dict[str, str]) -> Dict[str, float]:
    """천간(1.0) + 지장간(가중) 기준 십신 그룹 세력."""
    power = {g: 0.0 for g in _GROUPS}
    for gz in pillars.values():
        if not gz or len(gz) < 2:
            continue
        gan, ji = gz[0], gz[1]
        if gan in GAN_ELEM:
            power[sipsin_group(calculate_sipsin(day_master, gan, is_gan=True))] += 1.0
        for hidden, w in JIJANGGAN.get(ji, []):
            g = sipsin_group(calculate_sipsin(day_master, hidden, is_gan=True))
            if g in power:
                power[g] += w
    return {k: round(v, 2) for k, v in power.items()}


def _strength_label(value: float, scale: float) -> str:
    r = value / scale if scale else 0
    if r >= 0.9:
        return "매우 강함"
    if r >= 0.6:
        return "강함"
    if r >= 0.35:
        return "보통"
    if r >= 0.15:
        return "약함"
    return "매우 약함"


def analyze_domain_derived(
    saju: Dict[str, Any],
    overlay_sipsin: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """saju: calculate_saju 산출물 (day_master, sipsin, birth_ganji, strength 등).

    overlay_sipsin: 일운/세운 간지의 일간 대비 십신 목록 (당일/당해 작용).
    """
    day_master = saju.get("day_master", "己")
    pillars = saju.get("birth_ganji", {}) or {}
    pillars = {k: v for k, v in pillars.items() if v and v != "미정"}

    group_power = _weighted_group_counts(day_master, pillars)
    scale = max(group_power.values()) or 1.0

    # 표면 십신(간지 글자) 단순 카운트 — 레거시 호환
    sipsin_values = list((saju.get("sipsin") or {}).values())
    surface = Counter(sipsin_group(s) for s in sipsin_values if s and s != "미정")

    strength = saju.get("strength", {}) or {}
    dm_verdict = strength.get("verdict", "중화")

    # 당일/당해 작용 오버레이
    overlay_groups = Counter(sipsin_group(s) for s in (overlay_sipsin or []) if s and s != "미정")

    def dyn(group: str) -> float:
        return group_power.get(group, 0.0) + 1.2 * overlay_groups.get(group, 0)

    # 분야별 작용 요소 묶음
    domains = {
        "overall": ["비겁", "식상", "재성", "관성", "인성"],
        "money": ["재성", "식상", "비겁"],
        "love": ["관성", "재성", "인성"],
        "work_study": ["관성", "인성", "식상"],
        "business": ["식상", "재성", "비겁", "관성"],
        "career_change": ["관성", "인성", "식상"],
        "study": ["인성", "관성", "식상"],
        "health": ["인성", "비겁", "식상"],
        "travel": ["식상", "관성"],
        "hobby": ["식상", "인성", "재성"],
    }

    domain_strength: Dict[str, Any] = {}
    for name, groups in domains.items():
        factors = {}
        agg = 0.0
        for g in groups:
            v = dyn(g)
            agg += v
            factors[g] = {"power": round(v, 2), "label": _strength_label(v, scale * 1.5)}
        domain_strength[name] = {
            "factors": factors,
            "aggregate": round(agg, 2),
            "aggregate_label": _strength_label(agg / max(len(groups), 1), scale * 1.2),
            "day_master_strength": dm_verdict,
        }

    # active_elements: 원국 세력 + 오버레이 종합 상위 3
    combined = Counter()
    for g, v in group_power.items():
        combined[g] += v
    for g, c in overlay_groups.items():
        combined[g] += 1.5 * c
    active = [g for g, _ in combined.most_common(3)]

    # score_components (점수가 필요한 도메인)
    score_components = {
        "overall": {
            "day_master_strength": dm_verdict,
            "group_power": group_power,
            "today_overlay": dict(overlay_groups),
            "branch_relations": (saju.get("branch_relations") or {}).get("counts", {}),
        },
        "money": {
            "재성": group_power.get("재성"),
            "식상생재": bool(group_power.get("식상", 0) > 0 and group_power.get("재성", 0) > 0),
            "비겁": group_power.get("비겁"),
            "일간강약": dm_verdict,
            "당일작용": {g: overlay_groups.get(g, 0) for g in ("재성", "식상", "비겁")},
        },
        "love": {
            "배우자성": (saju.get("spouse_star") or {}).get("spouse_star_group"),
            "배우자성_존재": (saju.get("spouse_star") or {}).get("present"),
            "일지십신": (saju.get("sipsin") or {}).get("day_ji"),
            "관성": group_power.get("관성"),
            "재성": group_power.get("재성"),
            "도화": (saju.get("sinsal") or {}).get("has_dohwa"),
            "당일작용": {g: overlay_groups.get(g, 0) for g in ("관성", "재성", "인성")},
        },
        "work_study": {
            "관성": group_power.get("관성"),
            "인성": group_power.get("인성"),
            "식상": group_power.get("식상"),
            "일간강약": dm_verdict,
            "당일작용": {g: overlay_groups.get(g, 0) for g in ("관성", "인성", "식상")},
        },
    }

    return {
        "group_power": group_power,
        "surface_counts": dict(surface),
        "domain_strength": domain_strength,
        "active_elements": active,
        "score_components": score_components,
        "patterns": {
            "식상생재": bool(group_power.get("식상", 0) > 0 and group_power.get("재성", 0) > 0),
            "관인상생": bool(group_power.get("관성", 0) > 0 and group_power.get("인성", 0) > 0),
            "재자약살": bool(dm_verdict == "신약" and group_power.get("재성", 0) > group_power.get("비겁", 0)),
        },
    }
