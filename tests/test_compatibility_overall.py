"""상단 전체 점수의 집계 규칙을 고정한다.

애정·소통·갈등·경제의 기둥 조합 횟수 공식은 바꾸지 않는다.
같은 글자 쌍이 여러 기둥에 있어도 전체 점수는 1건이다. 기둥 위치는 나누지 않는다.
"""
import random
from itertools import product

import pytest

from core.constants import CHUNG, HAE, PA, SANGHYEONG, YUKHAP
from core.saju_base import calculate_saju
from domains.compatibility.engine import (
    _CHEONGAN_CHUNG,
    _CHEONGAN_HAP,
    _pillars,
    calculate_compatibility_interactions,
)


def _chart(pillars, day_master, day_branch, elements=None):
    keys = ("year", "month", "day", "time")
    return {
        "birth_ganji": {keys[i]: gz for i, gz in enumerate(pillars)},
        "day_master": day_master,
        "day_branch": day_branch,
        "five_elements": elements or {},
        "spouse_star": {},
        "sinsal": {},
    }


def _legacy_raw(result):
    """개선 전 전체 점수. 기둥 조합 횟수와 최소 오행을 포함한 보완을 그대로 쓴다."""
    counts = result["counts"]
    harmony = counts["천간합"] + counts["지지육합"] + counts["지지삼합"] + result["오행보완"]
    discord = (
        counts["천간충"] + counts["지지충"] + counts["지지형"] + counts["지지파"] + counts["지지해"]
    )
    relation = result["day_master_relation"]
    bonus = (8 if relation in ("상생", "비화(같은 기운)") else 0)
    bonus += 6 if result["day_master_hap"] else 0
    bonus -= 8 if result["day_master_chung"] else 0
    return 62 + 8 * harmony - 7 * discord + bonus


def test_repeated_branch_pair_adds_once():
    left = _chart(["戊午", "戊午", "戊午", "戊午"], "戊", "午")
    right = _chart(["甲未", "甲未", "甲未", "甲未"], "甲", "未")
    result = calculate_compatibility_interactions(left, right)

    assert result["counts"]["지지육합"] == 16
    assert result["overall_basis"]["지지육합"] == 1
    assert result["sub_scores"]["overall"] == 70
    assert _legacy_raw(result) == 190
    # 애정은 여전히 조합 횟수(16 × 4)를 쓰므로 상한에 닿는다.
    assert result["sub_scores"]["love"] == 100


def test_yukhap_and_pa_both_count_once():
    left = _chart(["戊巳"], "戊", "巳")
    right = _chart(["甲申"], "甲", "申")
    result = calculate_compatibility_interactions(left, right)
    basis = result["overall_basis"]

    assert basis["지지육합"] == 1
    assert basis["지지파"] == 1
    assert result["sub_scores"]["overall"] == 63


def test_samhap_without_wangji_is_not_an_event():
    left = _chart(["甲巳"], "甲", "巳")
    right = _chart(["戊丑"], "戊", "丑")
    result = calculate_compatibility_interactions(left, right)

    assert result["counts"]["지지삼합"] == 1
    assert result["overall_basis"]["지지삼합"] == 0
    assert result["sub_scores"]["overall"] == 62
    assert _legacy_raw(result) == 70


def test_rarest_present_element_is_not_complement():
    elements_a = {"목": 1, "화": 2, "토": 2, "금": 2, "수": 2}
    elements_b = {"목": 2, "화": 1, "토": 2, "금": 2, "수": 2}
    left = _chart(["甲子"], "甲", "子", elements_a)
    right = _chart(["戊寅"], "戊", "寅", elements_b)
    result = calculate_compatibility_interactions(left, right)

    assert result["오행보완"] == 2
    assert result["overall_basis"]["오행보완"] == 0
    assert result["sub_scores"]["overall"] == 62
    assert result["sub_scores"]["economy"] == 71


def test_sample_pair_keeps_other_axes_and_drops_repeated_counts():
    left = calculate_saju(1990, 3, 15, 10, 30, gender="male")
    right = calculate_saju(1992, 7, 8, 14, 0, gender="female")
    result = calculate_compatibility_interactions(left, right)
    scores = result["sub_scores"]

    assert result["counts"]["지지육합"] == 3
    assert result["overall_basis"]["지지육합"] == 2
    assert result["counts"]["지지충"] == 2
    assert result["overall_basis"]["지지충"] == 1
    assert result["overall_basis"]["지지파"] == 1
    assert scores["love"] == 53
    assert scores["communication"] == 67
    assert scores["conflict"] == 65
    assert scores["economy"] == 71
    assert scores["overall"] == 96
    assert _legacy_raw(result) == 105


def _occurrence_counts(left, right):
    """개선 전 집계를 엔진 결과와 분리해 다시 센다."""
    pa, pb = _pillars(left), _pillars(right)
    gans_a = [gz[0] for gz in pa.values()]
    gans_b = [gz[0] for gz in pb.values()]
    jis_a = [gz[1] for gz in pa.values()]
    jis_b = [gz[1] for gz in pb.values()]
    counts = {
        "천간합": 0, "천간충": 0, "지지육합": 0, "지지충": 0,
        "지지형": 0, "지지파": 0, "지지해": 0,
    }
    for x, y in product(gans_a, gans_b):
        key = frozenset((x, y))
        if key in _CHEONGAN_HAP:
            counts["천간합"] += 1
        if key in _CHEONGAN_CHUNG:
            counts["천간충"] += 1
    for x, y in product(jis_a, jis_b):
        key = frozenset((x, y))
        if key in YUKHAP:
            counts["지지육합"] += 1
        if key in CHUNG:
            counts["지지충"] += 1
        if key in SANGHYEONG:
            counts["지지형"] += 1
        if key in PA:
            counts["지지파"] += 1
        if key in HAE:
            counts["지지해"] += 1
    return counts


def test_same_letter_pair_on_different_pillars_is_one_event():
    # 午가 월주와 일주에 있어도 午未는 한 관계다. 기둥 위치는 점수에 나누지 않는다.
    left = _chart(["甲子", "乙午", "丙午"], "丙", "午")
    right = _chart(["丁未", "戊申", "己酉"], "己", "酉")
    result = calculate_compatibility_interactions(left, right)

    assert result["counts"]["지지육합"] == 2
    assert result["overall_basis"]["지지육합"] == 1
    assert _occurrence_counts(left, right)["지지육합"] == 2


def test_different_letter_pairs_stay_separate():
    left = _chart(["甲午", "乙巳"], "乙", "巳")
    right = _chart(["丙未", "丁申"], "丁", "申")
    result = calculate_compatibility_interactions(left, right)

    assert result["counts"]["지지육합"] == 2
    assert result["overall_basis"]["지지육합"] == 2
    assert result["overall_basis"]["지지파"] == 1


@pytest.mark.parametrize(
    ("pillars_a", "pillars_b", "key"),
    [
        (["甲子", "乙子"], ["戊午"], "지지충"),
        (["甲子", "乙子"], ["戊卯"], "지지형"),
        (["甲子"], ["戊未", "己未"], "지지해"),
        (["甲子"], ["戊酉", "己酉"], "지지파"),
        (["甲子", "甲丑"], ["己寅"], "천간합"),
        (["甲子", "甲丑"], ["庚寅"], "천간충"),
    ],
)
def test_each_relation_table_collapses_repeated_pairs(pillars_a, pillars_b, key):
    left = _chart(pillars_a, pillars_a[-1][0], pillars_a[-1][1])
    right = _chart(pillars_b, pillars_b[-1][0], pillars_b[-1][1])
    result = calculate_compatibility_interactions(left, right)

    assert result["counts"][key] == 2
    assert result["overall_basis"][key] == 1
    assert _occurrence_counts(left, right)[key] == result["counts"][key]


def test_only_inhae_and_sashin_are_both_hap_and_pa():
    overlap = {tuple(sorted(pair)) for pair in YUKHAP} & {tuple(sorted(pair)) for pair in PA}
    assert overlap == {("亥", "寅"), ("巳", "申")}

    left = _chart(["戊寅"], "戊", "寅")
    right = _chart(["甲亥"], "甲", "亥")
    result = calculate_compatibility_interactions(left, right)
    assert result["overall_basis"]["지지육합"] == 1
    assert result["overall_basis"]["지지파"] == 1
    assert result["sub_scores"]["overall"] == 63


def test_samhap_accepts_cross_banhap_once_per_group():
    both = calculate_compatibility_interactions(
        _chart(["甲巳", "乙酉"], "乙", "酉"),
        _chart(["戊丑", "己酉"], "己", "酉"),
    )
    assert both["overall_basis"]["지지삼합"] == 1

    internal = calculate_compatibility_interactions(
        _chart(["甲巳", "乙酉"], "乙", "酉"),
        _chart(["戊午"], "戊", "午"),
    )
    assert internal["counts"]["지지삼합"] == 0
    assert internal["overall_basis"]["지지삼합"] == 0

    # 한쪽이 반합을 이미 가지고 상대가 왕지만 겹치면, 기존 횟수는 0이고 전체 점수는 1이다.
    repeated_wang = calculate_compatibility_interactions(
        _chart(["甲巳", "乙酉"], "乙", "酉"),
        _chart(["戊酉"], "戊", "酉"),
    )
    assert repeated_wang["counts"]["지지삼합"] == 0
    assert repeated_wang["overall_basis"]["지지삼합"] == 1


def test_absent_element_counts_and_single_copy_does_not():
    filled = calculate_compatibility_interactions(
        _chart(["甲子"], "甲", "子", {"목": 1, "화": 1, "토": 1, "금": 1, "수": 0}),
        _chart(["戊寅"], "戊", "寅", {"목": 1, "화": 1, "토": 1, "금": 1, "수": 2}),
    )
    assert filled["overall_basis"]["오행보완"] == 1

    only_one = calculate_compatibility_interactions(
        _chart(["甲子"], "甲", "子", {"목": 1, "화": 1, "토": 1, "금": 1, "수": 0}),
        _chart(["戊寅"], "戊", "寅", {"목": 1, "화": 1, "토": 1, "금": 1, "수": 1}),
    )
    assert only_one["overall_basis"]["오행보완"] == 0


def test_unknown_birth_time_drops_the_hour_pillar():
    hidden = {
        "day_master": "甲",
        "day_branch": "寅",
        "five_elements": {},
        "spouse_star": {},
        "sinsal": {},
    }
    without_time = calculate_compatibility_interactions(
        {**hidden, "birth_ganji": {"year": "甲寅", "month": "甲寅", "day": "甲寅", "time": "미정"}},
        _chart(["戊未"], "戊", "未"),
    )
    with_time = calculate_compatibility_interactions(
        {**hidden, "birth_ganji": {"year": "甲寅", "month": "甲寅", "day": "甲寅", "time": "甲子"}},
        _chart(["戊未"], "戊", "未"),
    )
    assert without_time["counts"]["지지해"] == 0
    assert without_time["overall_basis"]["지지해"] == 0
    assert with_time["counts"]["지지해"] == 1

    known = calculate_saju(1990, 3, 15, 10, 30, gender="male")
    unknown = calculate_saju(1990, 3, 15, None, gender="male")
    partner = calculate_saju(1992, 7, 8, 14, 0, gender="female")
    assert unknown["birth_ganji"]["time"] == "미정"
    assert unknown["birth_time_known"] is False
    assert "巳" not in (
        unknown["birth_ganji"]["year"][1],
        unknown["birth_ganji"]["month"][1],
        unknown["birth_ganji"]["day"][1],
    )
    assert unknown["five_elements"]["화"] == known["five_elements"]["화"] - 1
    assert unknown["five_elements"]["토"] == known["five_elements"]["토"] - 1

    with_hour = calculate_compatibility_interactions(known, partner)
    without_hour = calculate_compatibility_interactions(unknown, partner)
    assert with_hour["overall_basis"]["지지파"] == 1
    assert without_hour["overall_basis"]["지지파"] == 0
    assert with_hour["overall_basis"]["지지육합"] == without_hour["overall_basis"]["지지육합"] + 1


# 시드 7, 400쌍 재실행에서 점수 변화가 가장 큰 10쌍.
_REVIEWED = [
    ((1976, 1, 9, 6, 0, "male"), (1982, 4, 11, 20, 0, "female"), 110, 100, 74),
    ((1985, 9, 2, 4, 0, "female"), (1975, 7, 22, 10, 0, "male"), 82, 82, 56),
    ((1983, 12, 23, 4, 0, "male"), (1978, 11, 18, 14, 0, "female"), 84, 84, 60),
    ((1972, 7, 18, None, 0, "female"), (1995, 6, 25, 14, 0, "male"), 97, 97, 73),
    ((1965, 5, 8, 20, 0, "female"), (1987, 5, 28, 0, 0, "male"), 104, 100, 80),
    ((2000, 12, 9, 0, 0, "male"), (2002, 7, 28, 8, 0, "male"), 1, 1, 58),
    ((1961, 4, 4, 14, 0, "female"), (1976, 7, 27, 14, 0, "male"), 2, 2, 43),
    ((1994, 3, 18, 6, 0, "male"), (1983, 6, 7, 12, 0, "male"), 37, 37, 72),
    ((2004, 2, 5, 10, 0, "female"), (1983, 9, 8, 12, 0, "female"), 43, 43, 74),
    ((1980, 3, 13, 2, 0, "male"), (1983, 10, 2, 6, 0, "male"), 53, 53, 82),
]


def _birth(spec):
    year, month, day, hour, minute, gender = spec
    return calculate_saju(year, month, day, hour, minute, gender=gender)


@pytest.mark.parametrize(("left", "right", "raw", "old", "new"), _REVIEWED)
def test_reviewed_score_changes_stay_fixed(left, right, raw, old, new):
    result = calculate_compatibility_interactions(_birth(left), _birth(right))
    assert _legacy_raw(result) == raw
    assert max(0, min(100, raw)) == old
    assert result["sub_scores"]["overall"] == new
    counted = _occurrence_counts(_birth(left), _birth(right))
    for key, value in counted.items():
        assert result["counts"][key] == value


def _sample_birth(rng):
    year = rng.randint(1960, 2005)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    hour = None if rng.random() < 0.25 else rng.choice(range(0, 24, 2))
    return (year, month, day, hour, 0, rng.choice(("male", "female")))


def test_seed7_four_hundred_pairs_reproduce():
    rng = random.Random(7)
    old_scores = []
    new_scores = []
    for _ in range(400):
        left = calculate_compatibility_interactions(_birth(_sample_birth(rng)), _birth(_sample_birth(rng)))
        raw = _legacy_raw(left)
        old_scores.append(max(0, min(100, raw)))
        new_scores.append(left["sub_scores"]["overall"])

    def summary(values):
        xs = sorted(values)
        k = (len(xs) - 1) * 0.9
        lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
        p90 = xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
        n = len(xs)
        median = xs[n // 2] if n % 2 else round((xs[n // 2 - 1] + xs[n // 2]) / 2, 1)
        return (
            round(sum(xs) / n, 1),
            median,
            round(p90, 1),
            sum(v >= 90 for v in xs),
            sum(v == 100 for v in xs),
        )

    assert summary(old_scores) == (69.2, 72.0, 97.0, 75, 30)
    assert summary(new_scores) == (70.6, 72.0, 90.0, 45, 18)
    assert sum(n < o for o, n in zip(old_scores, new_scores)) == 184
    assert sum(n == o for o, n in zip(old_scores, new_scores)) == 63
    assert sum(n > o for o, n in zip(old_scores, new_scores)) == 153
