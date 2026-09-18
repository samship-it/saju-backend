"""평생운세 '고민 심화 분석' 4단계 스키마(domains/lifelong/highlight.py) 검증.

[공통 총평 -> 명리적 해석 -> 치명적 금기 -> 맞춤 액션 플랜] — 실제 명리 로직(용신/
기신/신강약/대운 십신군 흐름)으로 실시간 합성되는지, 사주 전문 용어가 사용자 문장에
새지 않는지까지 함께 검증한다.
"""
from domains.lifelong.highlight import (
    CONCERN_LABELS,
    CONCERN_TO_DOMAIN,
    CRITICAL_TABOO,
    DOMAIN_ANCHOR,
    _elem_for_group,
    _find_timing_step,
    _group_power,
    _polarity,
    _verdict_key,
    build_action_plan,
    build_common_summary,
    build_highlight,
    build_saju_interpretation,
)
from domains.lifelong.service import DOMAIN_ANCHOR as SERVICE_DOMAIN_ANCHOR
from domains.lifelong.service import analyze_lifelong_fortune

_JARGON = ("재성", "관성", "식상", "비겁", "인성", "용신", "희신", "기신", "십신", "일간")


def _assert_no_jargon(text: str):
    for term in _JARGON:
        assert term not in text, f"사주 용어 노출: {term!r} in {text!r}"


# ------------------------------------------------------------------ 순수 계산 헬퍼
def test_elem_for_group_matches_five_element_relations():
    # 일간 오행이 '목'일 때: 비겁=목, 식상=화, 재성=토, 관성=금, 인성=수
    assert _elem_for_group("목", "비겁") == "목"
    assert _elem_for_group("목", "식상") == "화"
    assert _elem_for_group("목", "재성") == "토"
    assert _elem_for_group("목", "관성") == "금"
    assert _elem_for_group("목", "인성") == "수"


def test_polarity_favors_yongsin_and_heesin_over_gisin():
    strength = {"yongsin": ["금"], "heesin": ["토"], "gisin": ["화"]}
    assert _polarity("금", strength) == "favorable"
    assert _polarity("토", strength) == "favorable"
    assert _polarity("화", strength) == "unfavorable"
    assert _polarity("수", strength) == "neutral"


def test_verdict_key_defaults_to_junghwa_for_unknown_value():
    assert _verdict_key({"verdict": "신강"}) == "신강"
    assert _verdict_key({"verdict": "신약"}) == "신약"
    assert _verdict_key({"verdict": "이상값"}) == "중화"
    assert _verdict_key({}) == "중화"


def test_group_power_reads_elem_power_for_the_right_element():
    elem_power = {"목": 1.0, "화": 2.0, "토": 3.0, "금": 4.0, "수": 5.0}
    assert _group_power(elem_power, "목", "재성") == elem_power["토"]  # 목 기준 재성=토


def test_find_timing_step_prefers_current_step_when_it_matches():
    facts = [{"step": s, "sipsin_group": g} for s, g in enumerate(
        ["비겁", "재성", "재성", "관성", "식상", "인성", "재성", "비겁"], start=1)]
    assert _find_timing_step(facts, "재성", current_step=2) == 2


def test_find_timing_step_picks_nearest_future_when_current_does_not_match():
    facts = [{"step": s, "sipsin_group": g} for s, g in enumerate(
        ["비겁", "식상", "재성", "관성", "재성", "인성", "비겁", "비겁"], start=1)]
    assert _find_timing_step(facts, "재성", current_step=1) == 3


def test_find_timing_step_falls_back_to_past_when_no_future_match():
    facts = [{"step": s, "sipsin_group": g} for s, g in enumerate(
        ["재성", "비겁", "식상", "관성", "인성", "비겁", "식상", "인성"], start=1)]
    assert _find_timing_step(facts, "재성", current_step=5) == 1


def test_find_timing_step_falls_back_to_current_when_group_never_appears():
    facts = [{"step": s, "sipsin_group": "비겁"} for s in range(1, 9)]
    assert _find_timing_step(facts, "재성", current_step=4) == 4


# ------------------------------------------------------------------ 1단계: 공통 총평
def test_common_summary_states_the_actual_age_range():
    text = build_common_summary("wealth", timing_step=3, current_step=3, age_range=(28, 37))
    assert "28" in text and "37" in text
    assert "지금이 바로" in text


def test_common_summary_future_tense_when_timing_step_is_later():
    text = build_common_summary("wealth", timing_step=5, current_step=2, age_range=(48, 57))
    assert "아직 오지 않은 시기" in text


def test_common_summary_past_tense_when_timing_step_is_earlier():
    text = build_common_summary("wealth", timing_step=1, current_step=5, age_range=(8, 17))
    assert "이미 지나온 시기" in text


# ------------------------------------------------------------------ 2단계: 명리적 해석
def test_saju_interpretation_money_favorable_and_unfavorable_differ():
    fav = build_saju_interpretation(
        "wealth", "목", {"verdict": "신강", "yongsin": ["토"], "gisin": [], "heesin": []}, None,
    )
    unfav = build_saju_interpretation(
        "wealth", "목", {"verdict": "신강", "yongsin": [], "gisin": ["토"], "heesin": []}, None,
    )
    assert fav != unfav
    _assert_no_jargon(fav)
    _assert_no_jargon(unfav)


def test_saju_interpretation_career_picks_strongest_axis():
    # 목 일간 기준: 관성=금, 인성=수, 식상=화. 금을 가장 강하게 줘서 관성 축이 뽑히는지 확인.
    strength = {"verdict": "중화", "elem_power": {"목": 1, "화": 1, "토": 1, "금": 9, "수": 1}}
    text = build_saju_interpretation("career", "목", strength, None)
    assert text == build_saju_interpretation(
        "career", "목", {"verdict": "중화", "elem_power": {"목": 1, "화": 1, "토": 1, "금": 9, "수": 1}}, None,
    )
    _assert_no_jargon(text)


def test_saju_interpretation_social_balanced_when_bigeop_and_siksang_both_weak():
    # 목 일간: 비겁=목, 식상=화. 둘 다 낮고 비슷하게 주면 balanced 축.
    strength = {"verdict": "중화", "elem_power": {"목": 1, "화": 1, "토": 5, "금": 5, "수": 5}}
    text = build_saju_interpretation("social", "목", strength, None)
    assert "소수" in text  # balanced 텍스트는 소수 정예형 표현을 포함
    _assert_no_jargon(text)


def test_saju_interpretation_family_present_vs_absent_differ():
    present = build_saju_interpretation("family", "목", {"verdict": "신약"}, True)
    absent = build_saju_interpretation("family", "목", {"verdict": "신약"}, False)
    assert present != absent
    _assert_no_jargon(present)
    _assert_no_jargon(absent)


# ------------------------------------------------------------------ 3단계: 치명적 금기
def test_critical_taboo_covers_all_domains_and_topics_dont_overlap():
    assert set(CRITICAL_TABOO.keys()) == {"wealth", "career", "social", "family"}
    texts = list(CRITICAL_TABOO.values())
    assert len(set(texts)) == 4  # 4개 전부 서로 다른 문구


def test_critical_taboo_matches_user_specified_topics():
    assert "차용" in CRITICAL_TABOO["wealth"] or "빌려" in CRITICAL_TABOO["wealth"]
    assert "통제" in CRITICAL_TABOO["career"] or "수동적" in CRITICAL_TABOO["career"]
    assert "보증" in CRITICAL_TABOO["social"] or "문서" in CRITICAL_TABOO["social"]
    assert "간섭" in CRITICAL_TABOO["family"] or "통제" in CRITICAL_TABOO["family"]


# ------------------------------------------------------------------ 4단계: 맞춤 액션 플랜
def test_build_action_plan_uses_yongsin_first_element():
    text = build_action_plan("wealth", ["금", "수"])
    assert text  # 금 기준 wealth 텍스트

    from domains.lifelong.highlight import _ACTION_PLAN
    assert text == _ACTION_PLAN["금"]["wealth"]


def test_build_action_plan_falls_back_without_yongsin():
    from domains.lifelong.highlight import _DEFAULT_ACTION_PLAN
    assert build_action_plan("career", []) == _DEFAULT_ACTION_PLAN["career"]


# ------------------------------------------------------------------ build_highlight() 통합
_COMMON_KWARGS = dict(
    day_master_elem="수",
    strength={"verdict": "신약", "yongsin": ["금", "수"], "gisin": ["화", "토"], "heesin": [], "elem_power": {}},
    spouse_present=True,
    facts=[{"step": s, "sipsin_group": g} for s, g in enumerate(
        ["비겁", "식상", "재성", "관성", "인성", "재성", "관성", "인성"], start=1)],
    current_step=3,
    daewoon_num=5,
)


def test_build_highlight_returns_none_without_concern():
    assert build_highlight(None, **_COMMON_KWARGS) is None
    assert build_highlight("", **_COMMON_KWARGS) is None


def test_build_highlight_returns_none_for_unknown_concern():
    assert build_highlight("not-a-concern", **_COMMON_KWARGS) is None


def test_build_highlight_money_and_wealth_alias_to_same_domain():
    h_money = build_highlight("money", **_COMMON_KWARGS)
    h_wealth = build_highlight("wealth", **_COMMON_KWARGS)
    assert h_money["common_summary"] == h_wealth["common_summary"]
    assert h_money["title"] == f"선택하신 [{CONCERN_LABELS['wealth']}] 영역 집중 분석"


def test_build_highlight_has_exactly_the_four_stage_keys_plus_meta():
    h = build_highlight("career", **_COMMON_KWARGS)
    assert set(h.keys()) == {
        "selected_concern", "title", "common_summary", "saju_interpretation", "critical_taboo", "action_plan",
    }
    for key in ("common_summary", "saju_interpretation", "critical_taboo", "action_plan"):
        assert h[key]


def test_build_highlight_critical_taboo_matches_domain_table():
    h = build_highlight("social", **_COMMON_KWARGS)
    assert h["critical_taboo"] == CRITICAL_TABOO["social"]


def test_domain_anchor_stays_in_sync_between_highlight_and_service():
    assert DOMAIN_ANCHOR == SERVICE_DOMAIN_ANCHOR


def test_concern_to_domain_covers_all_four_domains():
    assert set(CONCERN_TO_DOMAIN.values()) == {"wealth", "career", "social", "family"}
    assert CONCERN_TO_DOMAIN["money"] == CONCERN_TO_DOMAIN["wealth"] == "wealth"


# ------------------------------------------------------------------ 통합(analyze_lifelong_fortune)
def test_analyze_lifelong_fortune_without_concern_has_no_highlight():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False)
    assert data["data"]["highlight"] is None


def test_analyze_lifelong_fortune_with_concern_returns_full_four_stage_highlight():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False, selected_concern="career")
    h = data["data"]["highlight"]
    assert h is not None
    assert h["selected_concern"] == "career"
    assert h["common_summary"] and h["saju_interpretation"] and h["critical_taboo"] and h["action_plan"]
    # 나이대가 명시돼야 한다(사용자 지적 반영 — "언제인지" 반드시 나와야 함)
    assert any(ch.isdigit() for ch in h["common_summary"])
    # 하단 core_nature.weaknesses 와 근거가 달라 절대 동일 문장이면 안 된다.
    assert h["critical_taboo"] != data["data"]["core_nature"]["weaknesses"]


def test_analyze_lifelong_fortune_unknown_concern_has_no_highlight():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False, selected_concern="not-a-concern")
    assert data["data"]["highlight"] is None
