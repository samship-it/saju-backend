"""두 사람 원국의 관계 연산 → 세부 궁합 점수(전체/애정/소통/갈등/경제) + 종합 점수.

문장은 만들지 않는다. 점수와 관계 요소만 산출한다.
"""
from typing import Dict, Any, List
from itertools import product

from core.constants import (
    GAN_ELEM, SHENG, KE,
    YUKHAP, CHUNG, PA, HAE, SANGHYEONG, SAMHAP,
)

_CHEONGAN_HAP = {
    frozenset(("甲", "己")), frozenset(("乙", "庚")), frozenset(("丙", "辛")),
    frozenset(("丁", "壬")), frozenset(("戊", "癸")),
}
_CHEONGAN_CHUNG = {
    frozenset(("甲", "庚")), frozenset(("乙", "辛")), frozenset(("丙", "壬")), frozenset(("丁", "癸")),
}


def _pillars(saju: Dict[str, Any]) -> Dict[str, str]:
    bg = saju.get("birth_ganji", {}) or {}
    return {k: v for k, v in bg.items() if v and v != "미정"}


def _clamp(v: float) -> int:
    return max(0, min(100, int(round(v))))


def calculate_compatibility_interactions(saju_a: Dict[str, Any], saju_b: Dict[str, Any]) -> Dict[str, Any]:
    pa = _pillars(saju_a)
    pb = _pillars(saju_b)
    gans_a = [gz[0] for gz in pa.values()]
    gans_b = [gz[0] for gz in pb.values()]
    jis_a = [gz[1] for gz in pa.values()]
    jis_b = [gz[1] for gz in pb.values()]

    dm_a, dm_b = saju_a.get("day_master", ""), saju_b.get("day_master", "")
    dji_a = saju_a.get("day_branch", "")
    dji_b = saju_b.get("day_branch", "")

    # 천간 합/충
    gan_hap = gan_chung = 0
    for x, y in product(gans_a, gans_b):
        key = frozenset((x, y))
        if key in _CHEONGAN_HAP:
            gan_hap += 1
        if key in _CHEONGAN_CHUNG:
            gan_chung += 1

    # 지지 관계 (교차)
    ji_yukhap = ji_chung = ji_hyeong = ji_pa = ji_hae = ji_samhap = 0
    for x, y in product(jis_a, jis_b):
        key = frozenset((x, y))
        if key in YUKHAP:
            ji_yukhap += 1
        if key in CHUNG:
            ji_chung += 1
        if key in SANGHYEONG:
            ji_hyeong += 1
        if key in PA:
            ji_pa += 1
        if key in HAE:
            ji_hae += 1
    for group in SAMHAP:
        a_hit = [g for g in group if g in jis_a]
        b_hit = [g for g in group if g in jis_b]
        if a_hit and b_hit and (set(a_hit) | set(b_hit)) != set(a_hit):
            ji_samhap += 1

    # 일간 관계
    dm_hap = frozenset((dm_a, dm_b)) in _CHEONGAN_HAP
    dm_chung = frozenset((dm_a, dm_b)) in _CHEONGAN_CHUNG
    ea, eb = GAN_ELEM.get(dm_a, ""), GAN_ELEM.get(dm_b, "")
    if ea and eb:
        if ea == eb:
            dm_relation = "비화(같은 기운)"
        elif SHENG.get(ea) == eb or SHENG.get(eb) == ea:
            dm_relation = "상생"
        elif KE.get(ea) == eb or KE.get(eb) == ea:
            dm_relation = "상극"
        else:
            dm_relation = "중립"
    else:
        dm_relation = "중립"

    # 일지(배우자궁) 관계
    dji_key = frozenset((dji_a, dji_b))
    if dji_a and dji_a == dji_b:
        day_ji_relation = "동일"
    elif dji_key in YUKHAP:
        day_ji_relation = "육합"
    elif any(dji_a in g and dji_b in g for g in SAMHAP):
        day_ji_relation = "삼합"
    elif dji_key in CHUNG:
        day_ji_relation = "충"
    elif dji_key in SANGHYEONG:
        day_ji_relation = "형"
    elif dji_key in HAE:
        day_ji_relation = "해"
    elif dji_key in PA:
        day_ji_relation = "파"
    else:
        day_ji_relation = "무관"

    # 오행 상호 보완 (상대의 강한 오행이 나의 약한 오행을 채우는가)
    fa = saju_a.get("five_elements", {}) or {}
    fb = saju_b.get("five_elements", {}) or {}
    def _lack(f):
        return [e for e, c in f.items() if c == 0] + [min(f, key=f.get)] if f else []
    a_lack = set(_lack(fa))
    b_lack = set(_lack(fb))
    a_strong = {e for e, c in fa.items() if c >= 2}
    b_strong = {e for e, c in fb.items() if c >= 2}
    complement = len(a_lack & b_strong) + len(b_lack & a_strong)

    # 배우자성 존재: 상대 일간이 나의 배우자성 그룹?
    ss_a = saju_a.get("spouse_star", {}).get("spouse_star_group")
    ss_b = saju_b.get("spouse_star", {}).get("spouse_star_group")
    from core.sipsin import calculate_sipsin, sipsin_group
    b_is_spouse_for_a = sipsin_group(calculate_sipsin(dm_a, dm_b, is_gan=True)) == ss_a
    a_is_spouse_for_b = sipsin_group(calculate_sipsin(dm_b, dm_a, is_gan=True)) == ss_b

    dohwa = saju_a.get("sinsal", {}).get("has_dohwa") or saju_b.get("sinsal", {}).get("has_dohwa")

    # ---- 세부 점수 ----
    harmony = gan_hap + ji_yukhap + ji_samhap + complement
    discord = gan_chung + ji_chung + ji_hyeong + ji_pa + ji_hae

    overall = 62 + 8 * harmony - 7 * discord + (8 if dm_relation in ("상생", "비화(같은 기운)") else 0) \
        + (6 if dm_hap else 0) - (8 if dm_chung else 0)

    love = 60 + (14 if day_ji_relation in ("육합", "삼합") else 0) \
        - (16 if day_ji_relation in ("충", "형") else 0) \
        + (10 if (b_is_spouse_for_a or a_is_spouse_for_b) else 0) \
        + (5 if dohwa else 0) + 4 * ji_yukhap - 4 * ji_chung

    communication = 60 + (12 if dm_relation == "상생" else 0) + (6 if dm_relation == "비화(같은 기운)" else 0) \
        - (10 if dm_relation == "상극" else 0) + 5 * gan_hap + 4 * ji_yukhap - 5 * gan_chung - 3 * ji_hae

    conflict = 78 - 12 * (gan_chung + ji_chung) - 10 * ji_hyeong - 5 * (ji_pa + ji_hae) \
        + 4 * (gan_hap + ji_yukhap)

    economy = 60 + 6 * complement + 4 * ji_yukhap - 6 * ji_chung \
        - (6 if dm_relation == "상극" else 0) + (5 if harmony >= 2 else 0)

    sub = {
        "overall": _clamp(overall),
        "love": _clamp(love),
        "communication": _clamp(communication),
        "conflict": _clamp(conflict),
        "economy": _clamp(economy),
    }
    total = _clamp(
        sub["overall"] * 0.30 + sub["love"] * 0.25 + sub["communication"] * 0.20
        + sub["conflict"] * 0.15 + sub["economy"] * 0.10
    )

    positives: List[str] = []
    negatives: List[str] = []
    if dm_hap:
        positives.append("일간 천간합(깊은 끌림)")
    if dm_relation in ("상생", "비화(같은 기운)"):
        positives.append(f"일간 {dm_relation}")
    if day_ji_relation in ("육합", "삼합"):
        positives.append(f"일지(배우자궁) {day_ji_relation}")
    if complement:
        positives.append("오행 상호 보완")
    if gan_hap or ji_yukhap:
        positives.append(f"천간합 {gan_hap} / 지지 육합 {ji_yukhap}")
    if dm_chung:
        negatives.append("일간 천간충")
    if day_ji_relation in ("충", "형"):
        negatives.append(f"일지(배우자궁) {day_ji_relation}")
    if ji_chung:
        negatives.append(f"지지 충 {ji_chung}")
    if ji_hyeong:
        negatives.append(f"지지 형 {ji_hyeong}")

    return {
        "day_master_a": dm_a,
        "day_master_b": dm_b,
        "day_master_relation": dm_relation,
        "day_master_hap": dm_hap,
        "day_master_chung": dm_chung,
        "day_ji_relation": day_ji_relation,
        "counts": {
            "천간합": gan_hap, "천간충": gan_chung,
            "지지육합": ji_yukhap, "지지충": ji_chung, "지지형": ji_hyeong,
            "지지파": ji_pa, "지지해": ji_hae, "지지삼합": ji_samhap,
        },
        "오행보완": complement,
        "배우자성_교차": {"b_is_spouse_for_a": b_is_spouse_for_a, "a_is_spouse_for_b": a_is_spouse_for_b},
        "도화": bool(dohwa),
        "sub_scores": sub,
        "total_score": total,
        "positive_factors": positives,
        "negative_factors": negatives,
    }
