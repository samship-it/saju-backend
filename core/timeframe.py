"""날짜 자동 계산 헬퍼 — 3개월 전략, 결혼운 10년 창.

특정 연도를 하드코딩하지 않는다. 모두 기준일/기준연도에서 파생.
"""
from datetime import date
from typing import List, Dict, Any

from core.constants import GAN, JI, YUKHAP, CHUNG, SAMHAP, DOHWA_BY_GROUP
from core.sipsin import calculate_sipsin, sipsin_group


def next_3_months(base: date) -> List[Dict[str, Any]]:
    """기준일 다음 달부터 3개월. 연도 넘어가는 것 자동."""
    out = []
    y, m = base.year, base.month
    for i in range(1, 4):
        mm = m + i
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        out.append({"year": yy, "month": mm, "label": f"{yy}년 {mm}월"})
    return out


def _year_ganji(year: int) -> str:
    return GAN[(year - 4) % 10] + JI[(year - 4) % 12]


def marriage_10year_window(saju: Dict[str, Any], target_year: int) -> Dict[str, Any]:
    """target_year 부터 10년. 각 연도 결혼 관련 강도 산출 → BEST 1/2/3."""
    dm = saju.get("day_master", "")
    day_branch = saju.get("day_branch", "")
    spouse_group = (saju.get("spouse_star") or {}).get("spouse_star_group")
    yongsin = set((saju.get("strength") or {}).get("yongsin") or [])
    from core.constants import GAN_ELEM, JI_ELEM

    # 도화 지지 (일지 삼합 그룹 기준)
    dohwa_ji = None
    for group, elem in SAMHAP.items():
        if day_branch in group:
            dohwa_ji = DOHWA_BY_GROUP.get(elem)

    rows = []
    for i in range(10):
        yr = target_year + i
        gz = _year_ganji(yr)
        gan, ji = gz[0], gz[1]
        score = 50.0
        reasons = []

        gan_sipsin = sipsin_group(calculate_sipsin(dm, gan, is_gan=True))
        ji_sipsin = sipsin_group(calculate_sipsin(dm, ji, is_gan=False))
        if spouse_group and (gan_sipsin == spouse_group or ji_sipsin == spouse_group):
            score += 16
            reasons.append("배우자성 세운")

        key = frozenset((day_branch, ji))
        if key in YUKHAP:
            score += 14
            reasons.append("일지 육합")
        elif any(day_branch in g and ji in g for g in SAMHAP):
            score += 12
            reasons.append("일지 삼합")
        elif key in CHUNG:
            score -= 14
            reasons.append("일지 충")

        if dohwa_ji and ji == dohwa_ji:
            score += 6
            reasons.append("도화 세운")

        if GAN_ELEM.get(gan) in yongsin or JI_ELEM.get(ji) in yongsin:
            score += 8
            reasons.append("용신 세운")

        rows.append({
            "year": yr,
            "ganji": gz,
            "strength": max(0, min(100, round(score))),
            "reasons": reasons,
        })

    ranked = sorted(rows, key=lambda r: r["strength"], reverse=True)
    best = ranked[:3]
    return {
        "target_year": target_year,
        "window": [target_year, target_year + 9],
        "years": rows,
        "best": [{"rank": n + 1, **b} for n, b in enumerate(best)],
        "best_period_label": _period_label([b["year"] for b in best]),
    }


def _period_label(years: List[int]) -> str:
    if not years:
        return ""
    ys = sorted(years)
    # 연속이면 범위로
    if len(ys) >= 2 and ys[-1] - ys[0] == len(ys) - 1:
        return f"{ys[0]}~{ys[-1]}년"
    return ", ".join(f"{y}년" for y in ys)
