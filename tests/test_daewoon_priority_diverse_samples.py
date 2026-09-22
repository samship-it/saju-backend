"""domains/daewoon/pipeline.py — priority tier 불변조건(Rule1~7)을 다양한 원국
25개(합성 생년월일, 실존 인물 아님) × 8개 대운 전부(=200개 대운 표본, domain 결과
1,800건)에서 검증한다(STEP5-B, 2026-09-21).

목적: STEP5-A(단일 원국, 1983-05-14 14:00 여성)에서 관찰된 현상이 그 원국에만
국한된 우연인지, domain/priority 구조 자체의 일반적 특성인지 구분하는 것.
이 파일은 activation 공식·domain 정의·priority 정책 어느 것도 바꾸지 않는다 — 순수
검증 전용(STEP5-B "테스트/분석용 코드만 추가" 지시에 따름).

표본은 성별(12남/13녀)·일간(10종 중 10종 전부 포함)·신강신약(3분류 전부 포함)이
고르게 섞이도록 무작위 생성 후 다양성을 확인해 고정했다(재현성을 위해 하드코딩).
"""
from itertools import combinations

import pytest

from core.saju_base import calculate_saju
from core.daewoon import daewoon_step_facts
from domains.daewoon.pipeline import build_domain_pipeline, DOMAIN_ORDER, DOMAIN_DEFINITIONS

PEOPLE = [
    (1990, 2, 1, 23, "male"), (1967, 4, 8, 4, "female"), (1997, 2, 22, 23, "male"),
    (2007, 9, 3, 18, "female"), (1977, 1, 1, 2, "male"), (1963, 4, 17, 19, "female"),
    (1951, 9, 7, 22, "male"), (1991, 12, 18, 13, "female"), (1964, 8, 19, 8, "male"),
    (2001, 1, 25, 5, "female"), (1994, 7, 11, 8, "male"), (1959, 4, 25, 10, "female"),
    (1956, 2, 13, 3, "male"), (1972, 6, 20, 8, "female"), (2001, 1, 24, 14, "male"),
    (1984, 2, 13, 2, "female"), (1985, 5, 27, 20, "male"), (1989, 6, 19, 6, "female"),
    (1995, 2, 2, 21, "male"), (1964, 5, 3, 7, "female"), (2005, 2, 13, 8, "male"),
    (1979, 11, 27, 11, "female"), (1960, 6, 12, 6, "male"), (1992, 5, 23, 21, "female"),
    (1965, 2, 18, 13, "female"),  # 癸 일간 보충(나머지 24개가 9종만 커버해서 추가)
]


def _all_decade_results():
    """25개 원국 x 8개 대운 전부(debug=True로 9개 domain 전부) 결과를 한 번만 계산해
    모듈 스코프로 캐싱 — 매 테스트마다 재계산하지 않는다."""
    results = []
    for gender_idx, (y, m, d, h, gender) in enumerate(PEOPLE):
        saju = calculate_saju(y, m, d, h, 0, gender=gender, is_lunar=False)
        dw = saju["daewoon"]
        facts = daewoon_step_facts(
            saju["day_master"], saju["day_branch"], saju["month_ganji"], dw["direction"] == "순행", count=8
        )
        for f in facts:
            age = dw["daewoon_num"] + (f["step"] - 1) * 10 + 5
            result = build_domain_pipeline(saju, f, age=age, gender=gender, debug=True)
            results.append((gender_idx, gender, saju["day_master"], saju["strength"]["verdict"], f, age, result))
    return results


_CACHE = _all_decade_results()


def test_sample_diversity_covers_all_ten_day_masters_and_both_genders():
    day_masters = {r[2] for r in _CACHE}
    genders = {r[1] for r in _CACHE}
    verdicts = {r[3] for r in _CACHE}
    assert len(day_masters) == 10, f"일간 10종 전부 커버해야 함, 실제: {day_masters}"
    assert genders == {"male", "female"}
    assert verdicts == {"신강", "신약", "중화"}


def test_rule1_activation_below_three_never_has_priority_tier():
    violations = []
    for *_ , result in _CACHE:
        for d in result["debug_all_domains"]:
            if d["activation"] < 3 and "priority_tier" in d:
                violations.append(d)
    assert not violations, f"{len(violations)}건 위반"


def test_rule2_top_activation_band_is_always_all_primary():
    violations = []
    for *_ , result in _CACHE:
        ge3 = [d for d in result["debug_all_domains"] if d["eligible"] and d["activation"] >= 3]
        if not ge3:
            continue
        top = max(d["activation"] for d in ge3)
        for d in ge3:
            if d["activation"] == top and d["priority_tier"] != "primary":
                violations.append(d)
    assert not violations, f"{len(violations)}건 위반"


def test_rule3_second_band_is_always_all_secondary():
    violations = []
    for *_ , result in _CACHE:
        ge3 = [d for d in result["debug_all_domains"] if d["eligible"] and d["activation"] >= 3]
        bands = sorted({d["activation"] for d in ge3}, reverse=True)
        if len(bands) < 2:
            continue
        second = bands[1]
        for d in ge3:
            if d["activation"] == second and d["priority_tier"] != "secondary":
                violations.append(d)
    assert not violations, f"{len(violations)}건 위반"


def test_rule4_lower_bands_are_always_supporting():
    violations = []
    for *_ , result in _CACHE:
        ge3 = [d for d in result["debug_all_domains"] if d["eligible"] and d["activation"] >= 3]
        bands = sorted({d["activation"] for d in ge3}, reverse=True)
        if len(bands) < 3:
            continue
        lower = set(bands[2:])
        for d in ge3:
            if d["activation"] in lower and d["priority_tier"] != "supporting":
                violations.append(d)
    assert not violations, f"{len(violations)}건 위반"


def test_rule5_specificity_never_reverses_activation_band():
    tier_rank = {"primary": 0, "secondary": 1, "supporting": 2}
    violations = []
    for *_ , result in _CACHE:
        ge3 = [d for d in result["debug_all_domains"] if d["eligible"] and d["activation"] >= 3]
        for a, b in combinations(ge3, 2):
            if a["activation"] > b["activation"] and a["specificity"] < b["specificity"]:
                if tier_rank[a["priority_tier"]] > tier_rank[b["priority_tier"]]:
                    violations.append((a["domain"], b["domain"]))
    assert not violations, f"{len(violations)}건 역전 발생"


def test_rule6_identical_activation_confidence_specificity_never_split_across_tiers():
    violations = []
    for *_ , result in _CACHE:
        ge3 = [d for d in result["debug_all_domains"] if d["eligible"] and d["activation"] >= 3]
        for a, b in combinations(ge3, 2):
            key_a = (a["activation"], a["confidence"], a["specificity"])
            key_b = (b["activation"], b["confidence"], b["specificity"])
            if key_a == key_b and a["priority_tier"] != b["priority_tier"]:
                violations.append((a["domain"], b["domain"]))
    assert not violations, f"{len(violations)}건 위반"


def test_rule7_life_stage_eligibility_matches_domain_definitions_stages():
    for *_ , result in _CACHE:
        for d in result["debug_all_domains"]:
            expected = result["life_stage"] in DOMAIN_DEFINITIONS[d["domain"]]["stages"]
            assert d["eligible"] == expected


def test_primary_zero_only_occurs_when_no_domain_reaches_activation_three():
    for *_ , result in _CACHE:
        primaries = [d for d in result["domain_scores"] if d["priority_tier"] == "primary"]
        if not primaries:
            ge3 = [d for d in result["debug_all_domains"] if d["eligible"] and d["activation"] >= 3]
            assert not ge3, "activation>=3인 eligible domain이 있는데 primary가 0개(규칙 위반)"


def test_gender_dynamic_spouse_group_applied_correctly_across_diverse_samples():
    for _, gender, _, _, _, _, result in _CACHE:
        expected_spouse_group = "관성" if gender == "female" else "재성"
        for d in result["debug_all_domains"]:
            if d["domain"] not in ("애정_연애", "결혼_배우자"):
                continue
            if d["activation"] >= 3 and d["driving_group"] is not None:
                assert d["driving_group"] in (expected_spouse_group, "식상"), (
                    f"{gender} {d['domain']} driving_group={d['driving_group']}(기대: {expected_spouse_group} 또는 식상)"
                )


def test_career_social_activation_ge3_rate_is_structurally_universal():
    # 2차 감사(STEP4-A-2)에서 수학적으로 증명된 내용의 다표본 실측 재확인: 직업_사회는
    # eligible한 모든 대운에서 activation>=3(5개 그룹 전체 scope로 base가 항상 3 보장).
    career_rows = [
        d
        for *_, result in _CACHE
        for d in result["debug_all_domains"]
        if d["domain"] == "직업_사회" and d["eligible"]
    ]
    assert career_rows
    ge3 = [d for d in career_rows if d["activation"] >= 3]
    assert len(ge3) == len(career_rows), "직업_사회가 eligible인데 activation<3인 사례 발견(예상과 다름)"


def test_scope_size_correlates_with_average_activation_but_is_not_asserted_as_bug():
    # 관찰용 회귀 테스트 — STEP5-B에서 상관계수 0.937을 실측했다. 이 상관관계 자체를
    # "고쳐야 할 버그"로 판단하지 않는다(사용자 지침) — 단지 이 특성이 유지되는지만
    # 추적한다. 상관계수가 갑자기 크게 달라지면(예: activation 공식이 바뀌면) 이
    # 테스트가 그 변화를 잡아준다.
    import statistics

    per_domain_scope = {k: len(v["groups"]) + (1 if v["dynamic_spouse"] else 0) for k, v in DOMAIN_DEFINITIONS.items()}
    means = {}
    for dom in DOMAIN_ORDER:
        acts = [
            d["activation"]
            for *_, result in _CACHE
            for d in result["debug_all_domains"]
            if d["domain"] == dom and d["eligible"]
        ]
        if acts:
            means[dom] = statistics.mean(acts)
    xs = [per_domain_scope[d] for d in means]
    ys = [means[d] for d in means]
    corr = statistics.correlation(xs, ys)
    assert corr > 0.7, f"scope_size와 activation_mean의 상관관계가 예상보다 약해짐(corr={corr:.3f})"
