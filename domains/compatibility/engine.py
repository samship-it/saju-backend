"""두 사람 원국의 관계 연산 → 세부 궁합 점수(전체/애정/소통/갈등/경제) + 종합 점수.

문장은 만들지 않는다. 점수와 관계 요소만 산출한다.

합·충·형·해·파·삼합은 글자 쌍 1건이다. 같은 글자가 여러 기둥에 있어도 한 번만 센다.
일간끼리·일지끼리의 합충만 무거운 점수를 쓰고, 그 외 기둥은 가벼운 점수를 쓴다.
오행 보완·배우자성·도화·일간 상생은 점수에 넣지 않는다.
"""
from typing import Dict, Any, List, Set
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


def _unique_relations(xs: List[str], ys: List[str], table) -> int:
    """기둥을 모두 짝지어 같은 글자 쌍이 여러 번 나와도 관계 표의 쌍은 1건이다.

    합·충 표는 지지/천간 글자의 관계이지, 기둥 칸 수만큼 거듭되는 관계가 아니다.
    """
    found = set()
    for x, y in product(xs, ys):
        key = frozenset((x, y))
        if len(key) == 2 and key in table:
            found.add(key)
    return len(found)


def _cross_samhap(jis_a: List[str], jis_b: List[str]) -> int:
    """삼합은 왕지를 포함한 반합이 두 사람에게 나뉘어 있을 때 국마다 1건이다.

    SAMHAP 튜플은 (생지, 왕지, 고지)다. 생지와 고지만 있는 겹침은 반합이 아니므로
    전체 점수에 넣지 않는다. 한 국 안의 반합이 두 개여도 그 국은 1건이다.
    """
    set_a, set_b = set(jis_a), set(jis_b)
    n = 0
    for group in SAMHAP:
        wang = group[1]
        for side in (group[0], group[2]):
            if (wang in set_a and side in set_b) or (wang in set_b and side in set_a):
                n += 1
                break
    return n


def _absence_complement(fa: Dict[str, int], fb: Dict[str, int]) -> int:
    """없는 오행(개수 0)을 상대가 2개 이상 가진 경우만 보완 1건으로 센다.

    가장 적은 오행을 항상 부족으로 넣으면, 다섯 오행이 모두 있어도 보완이 생긴다.
    """
    if not fa or not fb:
        return 0

    def absent(f: Dict[str, int]) -> Set[str]:
        return {e for e, c in f.items() if c == 0}

    def strong(f: Dict[str, int]) -> Set[str]:
        return {e for e, c in f.items() if c >= 2}

    return len(absent(fa) & strong(fb)) + len(absent(fb) & strong(fa))


# 기본 62. 사건이 없으면 모든 축이 62다.
# 일지·일간끼리만 무겁고, 다른 기둥의 같은 관계는 가볍다. 형·해·파는 자리를 나누지 않는다.
_SCORE_BASE = 62
_SCORE_WEIGHT = {
    "일지충": -8,
    "일간충": -6,
    "지지충": -4,
    "천간충": -3,
    "형": -3,
    "해": -1,
    "파": -1,
    "일지육합": 8,
    "일간합": 6,
    "지지육합": 4,
    "천간합": 3,
    "삼합": 3,
}
# 성향은 표 전체. 애정은 일간·일지와 지지 합충·삼합.
# 소통은 천간 합충과 형·해. 갈등은 삼합을 뺀 합충형해파(높은 점수 = 부딪힘이 적음).
# 경제는 지지 합충과 해·파·삼합. 삼합은 갈등을 지우는 합이 아니라 방향이 같다는 신호다.
_AXIS_KEYS = {
    "overall": tuple(_SCORE_WEIGHT),
    "love": ("일지충", "일지육합", "일간충", "일간합", "지지충", "지지육합", "삼합"),
    "communication": ("일간충", "일간합", "천간충", "천간합", "해", "형"),
    "conflict": (
        "일지충", "일간충", "지지충", "천간충", "형", "해", "파",
        "일지육합", "일간합", "지지육합", "천간합",
    ),
    "economy": ("일지충", "일지육합", "지지충", "지지육합", "파", "해", "삼합"),
}


def _split_day_pair(chars_a: List[str], chars_b: List[str], day_a: str, day_b: str, table) -> tuple:
    """표에 있는 글자 쌍을 일간·일지끼리 1건과 그 외 기둥 1건으로 나눈다.

    두 일간 또는 두 일지가 그 쌍이면 무거운 칸만 쓴다. 다른 기둥에 같은 글자가 더 있어도 다시 세지 않는다.
    """
    found = set()
    for x, y in product(chars_a, chars_b):
        key = frozenset((x, y))
        if len(key) == 2 and key in table:
            found.add(key)
    day_key = None
    if day_a and day_b and day_a != day_b:
        candidate = frozenset((day_a, day_b))
        if candidate in found:
            day_key = candidate
    other = found - ({day_key} if day_key else set())
    return (1 if day_key else 0), len(other)


def _axis_score(events: Dict[str, int], keys) -> int:
    points = sum(events[key] * _SCORE_WEIGHT[key] for key in keys)
    return _clamp(_SCORE_BASE + points)


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

    # 같은 글자 쌍은 기둥이 달라도 1건이다. 삼합은 왕지 반합만, 국마다 1건.
    # 생지·고지만 겹치면 넣지 않는다. 오행 보완은 개수 0을 상대가 2개 이상 채울 때만 센다.
    # 이 보완 건수는 문장용이고 점수에는 넣지 않는다.
    # 육합이면서 파인 쌍(寅亥, 巳申)은 합과 파를 모두 1건씩 반영한다. 어느 쪽도 지우지 않는다.
    u_gan_hap = _unique_relations(gans_a, gans_b, _CHEONGAN_HAP)
    u_gan_chung = _unique_relations(gans_a, gans_b, _CHEONGAN_CHUNG)
    u_yukhap = _unique_relations(jis_a, jis_b, YUKHAP)
    u_chung = _unique_relations(jis_a, jis_b, CHUNG)
    u_hyeong = _unique_relations(jis_a, jis_b, SANGHYEONG)
    u_pa = _unique_relations(jis_a, jis_b, PA)
    u_hae = _unique_relations(jis_a, jis_b, HAE)
    u_samhap = _cross_samhap(jis_a, jis_b)
    u_complement = _absence_complement(fa, fb)

    day_yuk, other_yuk = _split_day_pair(jis_a, jis_b, dji_a, dji_b, YUKHAP)
    day_chung, other_chung = _split_day_pair(jis_a, jis_b, dji_a, dji_b, CHUNG)
    day_hap, other_hap = _split_day_pair(gans_a, gans_b, dm_a, dm_b, _CHEONGAN_HAP)
    day_gchung, other_gchung = _split_day_pair(gans_a, gans_b, dm_a, dm_b, _CHEONGAN_CHUNG)
    events = {
        "일지충": day_chung,
        "일간충": day_gchung,
        "지지충": other_chung,
        "천간충": other_gchung,
        "형": u_hyeong,
        "해": u_hae,
        "파": u_pa,
        "일지육합": day_yuk,
        "일간합": day_hap,
        "지지육합": other_yuk,
        "천간합": other_hap,
        "삼합": u_samhap,
    }
    sub = {name: _axis_score(events, keys) for name, keys in _AXIS_KEYS.items()}
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
        "overall_basis": {
            "천간합": u_gan_hap, "천간충": u_gan_chung,
            "지지육합": u_yukhap, "지지충": u_chung, "지지형": u_hyeong,
            "지지파": u_pa, "지지해": u_hae, "지지삼합": u_samhap,
            "오행보완": u_complement,
        },
        "배우자성_교차": {"b_is_spouse_for_a": b_is_spouse_for_a, "a_is_spouse_for_b": a_is_spouse_for_b},
        "도화": bool(dohwa),
        "score_events": events,
        "sub_scores": sub,
        "total_score": total,
        "positive_factors": positives,
        "negative_factors": negatives,
    }
