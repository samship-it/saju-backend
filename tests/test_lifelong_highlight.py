"""평생운세 '고민 집중 분석' 하이라이트(selected_concern 답변 전용) 검증."""
from domains.lifelong.service import (
    CONCERN_LABELS,
    CONCERN_SYNTHESIS_FIELDS,
    CONCERN_TO_DOMAIN,
    _build_highlight,
    analyze_lifelong_fortune,
)

_LIFE_DOMAINS = {
    "wealth": {"style": "S", "management_tip": "MT", "money_timing": "MTG", "wealth_method": "WM"},
    "career": {"best_fit_work": "BFW", "success_environment": "SE", "career_direction": "CD", "career_strength": "CS"},
    "family": {"relation_characteristics": "RC", "harmony_key": "HK", "spouse_outlook": "SO", "spouse_star_present": True},
    "social": {"connection_style": "CoS", "network_strategy": "NS", "lucky_person_type": "LPT", "recommended_activity": "RA"},
}


def test_build_highlight_returns_none_without_concern():
    assert _build_highlight(None, _LIFE_DOMAINS, "약점텍스트") is None
    assert _build_highlight("", _LIFE_DOMAINS, "약점텍스트") is None


def test_build_highlight_returns_none_for_unknown_concern():
    assert _build_highlight("not-a-concern", _LIFE_DOMAINS, "약점텍스트") is None


def test_build_highlight_money_and_wealth_alias_to_same_domain():
    h_money = _build_highlight("money", _LIFE_DOMAINS, "약점텍스트")
    h_wealth = _build_highlight("wealth", _LIFE_DOMAINS, "약점텍스트")
    assert h_money["overview"] == h_wealth["overview"] == "S MTG"
    assert h_money["action_plan"] == h_wealth["action_plan"] == "MT WM"
    assert h_money["title"] == f"선택하신 [{CONCERN_LABELS['wealth']}] 영역 집중 분석"


def test_build_highlight_must_avoid_reuses_weaknesses_verbatim():
    h = _build_highlight("career", _LIFE_DOMAINS, "이 사람의 약점입니다.")
    assert h["must_avoid"] == "이 사람의 약점입니다."


def test_build_highlight_career_synthesizes_overview_and_action():
    h = _build_highlight("career", _LIFE_DOMAINS, "w")
    assert h["overview"] == "BFW CD"
    assert h["action_plan"] == "SE CS"
    assert h["selected_concern"] == "career"


def test_build_highlight_social_synthesizes_overview_and_action():
    h = _build_highlight("social", _LIFE_DOMAINS, "w")
    assert h["overview"] == "CoS LPT"
    assert h["action_plan"] == "NS RA"


def test_build_highlight_family_overview_includes_spouse_outlook():
    h = _build_highlight("family", _LIFE_DOMAINS, "w")
    assert h["overview"] == "RC SO"
    assert h["action_plan"] == "HK"


def test_build_highlight_skips_missing_fields_gracefully():
    partial = {"wealth": {"style": "S"}}  # money_timing/management_tip/wealth_method 없음
    h = _build_highlight("money", partial, "w")
    assert h["overview"] == "S"
    assert h["action_plan"] == ""


def test_concern_to_domain_and_synthesis_fields_cover_all_four_domains():
    domains = set(CONCERN_TO_DOMAIN.values())
    assert domains == {"wealth", "career", "social", "family"}
    assert set(CONCERN_SYNTHESIS_FIELDS.keys()) == domains
    assert set(CONCERN_LABELS.keys()) == domains


# ------------------------------------------------------------------ 통합(analyze_lifelong_fortune)
def test_analyze_lifelong_fortune_without_concern_has_no_highlight():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False)
    assert data["data"]["highlight"] is None


def test_analyze_lifelong_fortune_with_concern_returns_full_highlight():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False, selected_concern="career")
    h = data["data"]["highlight"]
    assert h is not None
    assert h["selected_concern"] == "career"
    assert h["overview"] and h["must_avoid"] and h["action_plan"]
    assert h["must_avoid"] == data["data"]["core_nature"]["weaknesses"]


def test_analyze_lifelong_fortune_unknown_concern_has_no_highlight():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False, selected_concern="not-a-concern")
    assert data["data"]["highlight"] is None
