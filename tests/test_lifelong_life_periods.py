"""평생운세 섹션8~10 '생애주기별 분석'(domains/lifelong/life_periods.py) 검증."""
from domains.lifelong.life_periods import (
    GROUPS,
    _group_at_age,
    _step_covering_age,
    build_early_life,
    build_late_life,
    build_middle_life,
)
from domains.lifelong.service import analyze_lifelong_fortune

_JARGON = ("재성", "관성", "식상", "비겁", "인성", "용신", "희신", "기신", "십신", "일간", "격국")


def _assert_no_jargon(text: str):
    for term in _JARGON:
        assert term not in text, f"사주 용어 노출: {term!r} in {text!r}"


def _facts(sequence):
    return [{"step": i + 1, "sipsin_group": g} for i, g in enumerate(sequence)]


# ------------------------------------------------------------------ 나이 -> 대운 단계 매핑
def test_step_covering_age_finds_exact_containing_step():
    facts = _facts(["비겁"] * 8)
    # daewoon_num=5 -> 1단계 [5,14], 2단계 [15,24], ... 4단계 [35,44]
    assert _step_covering_age(facts, daewoon_num=5, target_age=40) == 4


def test_step_covering_age_falls_back_to_nearest_when_out_of_range():
    facts = _facts(["비겁"] * 8)
    # daewoon_num=5 -> 8단계 끝은 [75,84]. age=90 은 범위 밖 -> 가장 가까운(8단계) 폴백.
    assert _step_covering_age(facts, daewoon_num=5, target_age=90) == 8


def test_group_at_age_reads_the_matching_step_group():
    facts = _facts(["비겁", "식상", "재성", "관성", "인성", "재성", "관성", "인성"])
    assert _group_at_age(facts, daewoon_num=5, target_age=40) == "관성"  # 4단계 [35,44]


# ------------------------------------------------------------------ 8. 초년의 모습
def test_build_early_life_uses_gyeokguk_sipsin_group():
    saju = {"gyeokguk": {"sipsin": "편재"}}  # 편재 -> 재성
    out = build_early_life(saju)
    from domains.lifelong.life_periods import _GROWTH_ENV
    assert out["growth_env"] == _GROWTH_ENV["재성"]


def test_build_early_life_falls_back_to_bigeop_when_gyeokguk_missing():
    out = build_early_life({})
    from domains.lifelong.life_periods import _GROWTH_ENV
    assert out["growth_env"] == _GROWTH_ENV["비겁"]


def test_build_early_life_has_all_five_fields():
    out = build_early_life({"gyeokguk": {"sipsin": "정관"}})
    assert set(out.keys()) == {"growth_env", "inner_child", "academics_friends", "keywords", "summary_one_line"}
    assert isinstance(out["keywords"], list) and len(out["keywords"]) == 2
    for v in out.values():
        if isinstance(v, str):
            assert v
            _assert_no_jargon(v)


def test_early_life_tables_cover_all_five_groups():
    from domains.lifelong.life_periods import (
        _ACADEMICS_FRIENDS, _EARLY_KEYWORDS, _EARLY_SUMMARY, _GROWTH_ENV, _INNER_CHILD,
    )
    for table in (_GROWTH_ENV, _INNER_CHILD, _ACADEMICS_FRIENDS, _EARLY_KEYWORDS, _EARLY_SUMMARY):
        assert set(table.keys()) == set(GROUPS)


# ------------------------------------------------------------------ 9. 중년의 모습
def test_build_middle_life_turning_points_mentions_all_three_decades():
    facts = _facts(["비겁", "식상", "재성", "관성", "인성", "재성", "관성", "인성"])
    out = build_middle_life({}, facts, daewoon_num=5)
    assert "30대" in out["turning_points"]
    assert "40대" in out["turning_points"]
    assert "50대" in out["turning_points"]


def test_build_middle_life_has_all_five_fields():
    facts = _facts(["비겁", "식상", "재성", "관성", "인성", "재성", "관성", "인성"])
    out = build_middle_life({}, facts, daewoon_num=5)
    assert set(out.keys()) == {
        "social_position", "wealth_lifestyle", "family_relationships", "turning_points", "summary_one_line",
    }
    for v in out.values():
        assert v
        _assert_no_jargon(v)


def test_middle_life_tables_cover_all_five_groups():
    from domains.lifelong.life_periods import (
        _FAMILY_RELATIONSHIPS_MID, _MIDDLE_SUMMARY, _PHASE1_FORMATION, _PHASE2_EXPANSION,
        _PHASE3_HARVEST, _SOCIAL_POSITION, _WEALTH_LIFESTYLE,
    )
    for table in (
        _SOCIAL_POSITION, _WEALTH_LIFESTYLE, _FAMILY_RELATIONSHIPS_MID,
        _PHASE1_FORMATION, _PHASE2_EXPANSION, _PHASE3_HARVEST, _MIDDLE_SUMMARY,
    ):
        assert set(table.keys()) == set(GROUPS)


# ------------------------------------------------------------------ 10. 말년의 모습
def test_build_late_life_uses_hour_gan_when_birth_time_known():
    saju = {"day_master": "壬", "birth_time_known": True, "time_ganji": "丁未"}
    facts = _facts(["비겁"] * 8)
    out = build_late_life(saju, facts, daewoon_num=5)
    from domains.lifelong.life_periods import _DAILY_LIFESTYLE
    from core.sipsin import calculate_sipsin, sipsin_group
    expected_group = sipsin_group(calculate_sipsin("壬", "丁", is_gan=True))
    assert out["daily_lifestyle"] == _DAILY_LIFESTYLE[expected_group]


def test_build_late_life_falls_back_to_day_branch_when_birth_time_unknown():
    saju = {"day_master": "壬", "day_branch": "寅", "birth_time_known": False, "time_ganji": ""}
    facts = _facts(["비겁"] * 8)
    out = build_late_life(saju, facts, daewoon_num=5)
    from domains.lifelong.life_periods import _DAILY_LIFESTYLE
    from core.sipsin import calculate_sipsin, sipsin_group
    expected_group = sipsin_group(calculate_sipsin("壬", "寅", is_gan=False))
    assert out["daily_lifestyle"] == _DAILY_LIFESTYLE[expected_group]


def test_build_late_life_decade_transition_mentions_70s_and_80s():
    saju = {"day_master": "壬", "birth_time_known": True, "time_ganji": "丁未"}
    facts = _facts(["비겁", "식상", "재성", "관성", "인성", "재성", "관성", "인성"])
    out = build_late_life(saju, facts, daewoon_num=5)
    assert "70대" in out["decade_transition"]
    assert "80대" in out["decade_transition"]


def test_build_late_life_has_all_six_fields():
    saju = {"day_master": "壬", "birth_time_known": True, "time_ganji": "丁未"}
    facts = _facts(["비겁"] * 8)
    out = build_late_life(saju, facts, daewoon_num=5)
    assert set(out.keys()) == {
        "daily_lifestyle", "financial_status", "family_bonds", "mental_social_role",
        "decade_transition", "summary_one_line",
    }
    for v in out.values():
        assert v
        _assert_no_jargon(v)


def test_late_life_tables_cover_all_five_groups():
    from domains.lifelong.life_periods import (
        _DAILY_LIFESTYLE, _FAMILY_BONDS_LATE, _FINANCIAL_STATUS, _LATE_SUMMARY,
        _MENTAL_SOCIAL_ROLE, _PHASE_70S, _PHASE_80S,
    )
    for table in (
        _DAILY_LIFESTYLE, _FINANCIAL_STATUS, _FAMILY_BONDS_LATE, _MENTAL_SOCIAL_ROLE,
        _LATE_SUMMARY, _PHASE_70S, _PHASE_80S,
    ):
        assert set(table.keys()) == set(GROUPS)


# ------------------------------------------------------------------ 통합(analyze_lifelong_fortune)
def test_analyze_lifelong_fortune_includes_early_middle_late_life_sections():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False)
    d = data["data"]
    assert set(d["early_life"].keys()) == {
        "growth_env", "inner_child", "academics_friends", "keywords", "summary_one_line",
    }
    assert set(d["middle_life"].keys()) == {
        "social_position", "wealth_lifestyle", "family_relationships", "turning_points", "summary_one_line",
    }
    assert set(d["late_life"].keys()) == {
        "daily_lifestyle", "financial_status", "family_bonds", "mental_social_role",
        "decade_transition", "summary_one_line",
    }


def test_analyze_lifelong_fortune_life_period_sections_come_before_life_stages_in_key_order():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False)
    keys = list(data["data"].keys())
    assert keys.index("early_life") < keys.index("life_stages")
    assert keys.index("middle_life") < keys.index("life_stages")
    assert keys.index("late_life") < keys.index("life_stages")


def test_analyze_lifelong_fortune_handles_birth_time_unknown_for_late_life():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, None, 0, "female", False)
    late = data["data"]["late_life"]
    assert late["daily_lifestyle"]
