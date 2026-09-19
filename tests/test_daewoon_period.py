"""10년 대운(domains/daewoon) — 평생운세와 별개의 독립 모듈 검증."""
from domains.daewoon.content import (
    ALLOWANCE_ECONOMY,
    CAREER_ADULT,
    CAREER_YOUTH,
    DECADE_TASKS,
    FAMILY_ENVIRONMENT,
    FAMILY_FLOW,
    FORBIDDEN_ADULT_WORDS,
    FRIENDSHIP,
    GROUPS,
    KEYWORDS,
    RELATIONSHIP_FLOW,
    RELATIONSHIP_STATUS_GUIDE,
    STUDY_GROWTH,
    TRANSITION_BACK_CAREER,
    TRANSITION_FRONT_STUDY,
    WEALTH_FLOW,
    build_career_or_study,
    build_child_domains,
    build_family,
    build_relationship,
    build_transition_back_domains,
    build_transition_front_domains,
    build_wealth_flow,
)
from domains.daewoon.landscape import build_decade_landscape
from domains.daewoon.service import (
    ADULT_AGE_THRESHOLD,
    CHILD_AGE_THRESHOLD,
    TRANSITION_SPLIT_AGE,
    TRANSITION_START_MAX,
    TRANSITION_START_MIN,
    _ganji_label,
    analyze_daewoon_period,
)
from domains.lifelong.service import DOMINANT_GROUPS


def test_groups_match_lifelong_dominant_groups():
    assert set(GROUPS) == set(DOMINANT_GROUPS)


# ------------------------------------------------------------------ content.py 표 완결성
def test_keyword_and_decade_task_tables_cover_all_groups():
    assert set(KEYWORDS.keys()) == set(GROUPS)
    assert set(DECADE_TASKS.keys()) == set(GROUPS)
    for g in GROUPS:
        assert len(KEYWORDS[g]) == 3
        assert len(DECADE_TASKS[g]) == 3


def test_career_adult_and_youth_tables_cover_all_groups_with_distinct_shape():
    assert set(CAREER_ADULT.keys()) == set(GROUPS)
    assert set(CAREER_YOUTH.keys()) == set(GROUPS)
    for g in GROUPS:
        assert set(CAREER_ADULT[g].keys()) == {"core_change", "how_it_shows", "cautions"}
        assert set(CAREER_YOUTH[g].keys()) == {"growth_flow", "study_style", "cautions"}


def test_wealth_and_family_tables_cover_all_groups():
    assert set(WEALTH_FLOW.keys()) == set(GROUPS)
    assert set(FAMILY_FLOW.keys()) == set(GROUPS)
    for g in GROUPS:
        assert set(WEALTH_FLOW[g].keys()) == {"earning_style", "cash_flow", "management_caution"}
        assert set(FAMILY_FLOW[g].keys()) == {"change_flow", "warning"}


def test_relationship_flow_covers_all_groups_and_status_guide_has_three():
    assert set(RELATIONSHIP_FLOW.keys()) == set(GROUPS)
    assert set(RELATIONSHIP_STATUS_GUIDE.keys()) == {"single", "dating", "married"}


# ------------------------------------------------------------------ content.py 빌더
def test_build_career_or_study_switches_shape_by_age_bracket():
    adult = build_career_or_study("재성", is_adult=True)
    youth = build_career_or_study("재성", is_adult=False)
    assert set(adult.keys()) == {"core_change", "how_it_shows", "cautions"}
    assert set(youth.keys()) == {"growth_flow", "study_style", "cautions"}
    assert adult != youth


def test_build_relationship_includes_guide_only_when_current_decade():
    not_current = build_relationship("식상", "single", is_current=False)
    assert not_current["guide_by_status"] is None
    assert not_current["flow"]

    current_known = build_relationship("식상", "single", is_current=True)
    assert current_known["guide_by_status"] == {"single": RELATIONSHIP_STATUS_GUIDE["single"]}

    current_unknown = build_relationship("식상", None, is_current=True)
    assert current_unknown["guide_by_status"] == RELATIONSHIP_STATUS_GUIDE


def test_build_wealth_flow_and_family_return_full_shape():
    w = build_wealth_flow("관성")
    assert set(w.keys()) == {"earning_style", "cash_flow", "management_caution"}
    f = build_family("인성")
    assert set(f.keys()) == {"change_flow", "warning"}


def test_child_domain_tables_cover_all_groups_with_expected_shape():
    for table in (STUDY_GROWTH, ALLOWANCE_ECONOMY, FRIENDSHIP, FAMILY_ENVIRONMENT):
        assert set(table.keys()) == set(GROUPS)
    for g in GROUPS:
        assert set(STUDY_GROWTH[g].keys()) == {"school_life", "exam_luck", "aptitude_path"}
        assert set(ALLOWANCE_ECONOMY[g].keys()) == {"allowance_flow", "money_mindset", "spending_habit"}
        assert set(FRIENDSHIP[g].keys()) == {"peer_relationship", "bond_with_others", "group_adaptation"}
        assert set(FAMILY_ENVIRONMENT[g].keys()) == {
            "parent_relationship", "home_support", "home_atmosphere",
        }


def test_build_child_domains_returns_all_four_areas_for_every_group():
    for g in GROUPS:
        child = build_child_domains(g)
        assert set(child.keys()) == {
            "study_growth", "allowance_economy", "friendship", "family_environment",
        }


def test_child_domain_tables_never_contain_forbidden_adult_words():
    assert FORBIDDEN_ADULT_WORDS  # 표가 비어있으면 이 검증 자체가 무의미해짐을 방지
    for table in (STUDY_GROWTH, ALLOWANCE_ECONOMY, FRIENDSHIP, FAMILY_ENVIRONMENT):
        for fields in table.values():
            for text in fields.values():
                for word in FORBIDDEN_ADULT_WORDS:
                    assert word not in text


def test_transition_content_tables_cover_all_groups_with_expected_shape():
    assert set(TRANSITION_FRONT_STUDY.keys()) == set(GROUPS)
    assert set(TRANSITION_BACK_CAREER.keys()) == set(GROUPS)
    for g in GROUPS:
        assert set(TRANSITION_FRONT_STUDY[g].keys()) == {"school_life", "exam_luck", "aptitude_path"}
        assert set(TRANSITION_BACK_CAREER[g].keys()) == {"core_change", "how_it_shows", "cautions"}


def test_transition_front_study_never_contains_forbidden_adult_words():
    for fields in TRANSITION_FRONT_STUDY.values():
        for text in fields.values():
            for word in FORBIDDEN_ADULT_WORDS:
                assert word not in text


def test_build_transition_front_domains_keeps_child_shape_with_overridden_study():
    for g in GROUPS:
        domains = build_transition_front_domains(g)
        assert set(domains.keys()) == {
            "study_growth", "allowance_economy", "friendship", "family_environment",
        }
        assert domains["study_growth"] == {
            field: text for field, text in TRANSITION_FRONT_STUDY.get(g, TRANSITION_FRONT_STUDY["비겁"]).items()
        }


def test_build_transition_back_domains_keeps_adult_shape_with_overridden_career():
    for g in GROUPS:
        domains = build_transition_back_domains(g, None, False)
        assert set(domains.keys()) == {"career_or_study", "wealth_flow", "relationship", "family"}
        assert domains["career_or_study"] == dict(
            TRANSITION_BACK_CAREER.get(g, TRANSITION_BACK_CAREER["비겁"])
        )


def test_domain_content_reaches_five_sentences_per_domain_for_every_group():
    for g in GROUPS:
        career_adult = build_career_or_study(g, is_adult=True)
        assert sum(v.count(".") for v in career_adult.values()) >= 5

        career_youth = build_career_or_study(g, is_adult=False)
        assert sum(v.count(".") for v in career_youth.values()) >= 5

        wealth = build_wealth_flow(g)
        assert sum(v.count(".") for v in wealth.values()) >= 5

        assert RELATIONSHIP_FLOW[g].count(".") >= 5

        family = build_family(g)
        assert sum(v.count(".") for v in family.values()) >= 5


# ------------------------------------------------------------------ landscape
def test_build_decade_landscape_reused_from_lifelong_tables():
    from domains.lifelong.landscape import ENV_IMAGE, SUBJECT_IMAGE

    out = build_decade_landscape("수", "戊辰", "재성")
    assert out["scene"] == f"{ENV_IMAGE['토']} 아래 {SUBJECT_IMAGE['수']}"


def test_build_decade_landscape_saju_relation_names_the_group_and_elements():
    out = build_decade_landscape("수", "戊辰", "재성")
    assert "재성운" in out["saju_relation"]
    assert "토" in out["saju_relation"]
    assert "수" in out["saju_relation"]


def test_build_decade_landscape_saju_relation_none_without_group():
    out = build_decade_landscape("수", "戊辰")
    assert out["saju_relation"] is None


# ------------------------------------------------------------------ 간지 라벨
def test_ganji_label_formats_hangul_and_hanja():
    assert _ganji_label("戊辰") == "무진(戊辰)"


def test_ganji_label_handles_empty_input():
    assert _ganji_label("") == ""


# ------------------------------------------------------------------ analyze_daewoon_period()
def test_analyze_daewoon_period_defaults_to_current_age_when_target_age_omitted():
    from domains.lifelong.service import analyze_lifelong_fortune

    lifelong_data, _ = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    expected_step = lifelong_data["data"]["current_step"]

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False)
    assert data["data"]["step"] == expected_step
    assert data["data"]["is_current_decade"] is True


def test_analyze_daewoon_period_honors_explicit_target_age():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=5)
    assert data["data"]["step"] == 1
    assert data["data"]["target_age"] == 5


def test_analyze_daewoon_period_branches_career_or_study_by_target_age():
    # target_age=10은 CHILD_AGE_THRESHOLD(20) 미만이라 domain_analysis 자체가
    # career_or_study 없이 [학업/용돈/교우/부모]로 완전히 바뀐다 — 이 테스트는
    # 성인기 안에서의 career_or_study 문구 분기(ADULT_AGE_THRESHOLD=25)만 보는
    # 것이므로 20~24세 구간(youth 문구)과 25세 이상(adult 문구)을 비교한다.
    # 1990-01-06(male)은 daewoon_num=1이라 어느 단계도 과도기(대운 시작 15~19세)에
    # 걸리지 않는다 — 일반 CHILD_AGE_THRESHOLD/ADULT_AGE_THRESHOLD 게이트만 순수하게 본다.
    youth, _ = analyze_daewoon_period(1990, 1, 6, 10, 0, "male", False, target_age=22)
    adult, _ = analyze_daewoon_period(1990, 1, 6, 10, 0, "male", False, target_age=40)
    assert set(youth["data"]["domain_analysis"]["career_or_study"].keys()) == {
        "growth_flow", "study_style", "cautions",
    }
    assert set(adult["data"]["domain_analysis"]["career_or_study"].keys()) == {
        "core_change", "how_it_shows", "cautions",
    }
    assert ADULT_AGE_THRESHOLD == 25


def test_analyze_daewoon_period_under_20_returns_the_four_child_domains():
    assert CHILD_AGE_THRESHOLD == 20
    for target_age in (0, 5, 10, 15, 19):
        data, _ = analyze_daewoon_period(2015, 3, 10, 9, 0, "male", False, target_age=target_age)
        domains = data["data"]["domain_analysis"]
        assert set(domains.keys()) == {
            "study_growth", "allowance_economy", "friendship", "family_environment",
        }
        assert "career_or_study" not in domains
        assert "wealth_flow" not in domains
        assert "relationship" not in domains
        assert "family" not in domains


def test_analyze_daewoon_period_20_and_above_keeps_the_adult_domains():
    # 과도기 대운(15~19세 시작)과 섞이지 않도록 non-transitional 생일(1990-01-06)을 쓴다.
    for target_age in (20, 21, 24, 25, 40):
        data, _ = analyze_daewoon_period(1990, 1, 6, 10, 0, "male", False, target_age=target_age)
        assert set(data["data"]["domain_analysis"].keys()) == {
            "career_or_study", "wealth_flow", "relationship", "family",
        }


def test_analyze_daewoon_period_under_20_never_outputs_forbidden_adult_words():
    for target_age in (0, 5, 10, 15, 19):
        data, _ = analyze_daewoon_period(2015, 3, 10, 9, 0, "male", False, target_age=target_age)
        rendered = str(data["data"]["domain_analysis"])
        for word in FORBIDDEN_ADULT_WORDS:
            assert word not in rendered


# 1990-01-01(male, 양력)은 daewoon_num=8이라 2단계 대운이 18세에 시작해(18~27세)
# TRANSITION_START_MIN~MAX(15~19) 안에 걸리는 실제 과도기 대운이다 — 별도 가정/모킹 없이
# 실제 계산 결과로 17~27세 구간의 흐름 전환을 검증한다.
_TRANSITION_BIRTH = (1990, 1, 1, 10, 0, "male", False)


def test_transition_decade_start_age_is_within_the_transitional_window():
    data, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=18)
    assert data["data"]["age_range"] == [18, 27]
    assert TRANSITION_START_MIN <= data["data"]["age_range"][0] <= TRANSITION_START_MAX


def test_transition_decade_front_half_uses_the_child_shape_with_transition_study_content():
    # 대운 시작(18세)부터 TRANSITION_SPLIT_AGE(22) 직전까지는 학업/입시 관점(전반부).
    for target_age in range(18, TRANSITION_SPLIT_AGE):
        data, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=target_age)
        domains = data["data"]["domain_analysis"]
        assert set(domains.keys()) == {
            "study_growth", "allowance_economy", "friendship", "family_environment",
        }
        rendered = str(domains)
        for word in FORBIDDEN_ADULT_WORDS:
            assert word not in rendered


def test_transition_decade_back_half_uses_the_adult_shape_with_first_job_content():
    # TRANSITION_SPLIT_AGE(22)부터 대운 끝(27세)까지는 첫 직장/사회초년 관점(후반부) —
    # "직장" 같은 단어는 여기서는 의도적으로 등장해야 한다(전반부와 달리 필터링하지 않음).
    for target_age in range(TRANSITION_SPLIT_AGE, 28):
        data, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=target_age)
        domains = data["data"]["domain_analysis"]
        assert set(domains.keys()) == {"career_or_study", "wealth_flow", "relationship", "family"}
        assert "직장" in domains["career_or_study"]["core_change"] or "직장" in domains["career_or_study"]["how_it_shows"]


def test_transition_decade_flow_changes_at_the_split_age():
    before, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=TRANSITION_SPLIT_AGE - 1)
    after, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=TRANSITION_SPLIT_AGE)
    assert set(before["data"]["domain_analysis"].keys()) != set(after["data"]["domain_analysis"].keys())


def test_non_transition_decades_are_unaffected_by_the_transition_logic():
    # 같은 사람의 다른(과도기가 아닌) 대운 단계는 일반 CHILD_AGE_THRESHOLD/성인 로직 그대로.
    child, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=8)  # 1단계(8~17세)는 과도기 아님
    assert set(child["data"]["domain_analysis"].keys()) == {
        "study_growth", "allowance_economy", "friendship", "family_environment",
    }
    adult, _ = analyze_daewoon_period(*_TRANSITION_BIRTH, target_age=40)  # 4단계(38~47세)도 과도기 아님
    assert set(adult["data"]["domain_analysis"].keys()) == {
        "career_or_study", "wealth_flow", "relationship", "family",
    }


def test_analyze_daewoon_period_relationship_guide_present_only_for_current_decade():
    from domains.lifelong.service import analyze_lifelong_fortune

    lifelong_data, _ = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    current_step = lifelong_data["data"]["current_step"]
    current_age = next(
        s["age_range"][0] for s in lifelong_data["data"]["life_stages"] if s["step"] == current_step
    )
    other_age = current_age + 40 if current_age + 40 <= 90 else max(0, current_age - 40)

    cur, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=current_age, love_status="dating")
    assert cur["data"]["is_current_decade"] is True
    assert cur["data"]["domain_analysis"]["relationship"]["guide_by_status"] is not None

    other, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=other_age, love_status="dating")
    if not other["data"]["is_current_decade"]:
        assert other["data"]["domain_analysis"]["relationship"]["guide_by_status"] is None


def test_analyze_daewoon_period_target_echoed_and_validated():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target="partner")
    assert data["data"]["target"] == "partner"
    data2, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target="not-valid")
    assert data2["data"]["target"] == "me"


def test_analyze_daewoon_period_has_full_schema():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    d = data["data"]
    assert set(d.keys()) == {
        "daewoon_header", "landscape_scene", "saju_relation", "summary", "keywords",
        "domain_analysis", "timeline_phases", "decade_tasks", "step", "age_range",
        "target_age", "target", "is_current_decade",
    }
    assert d["daewoon_header"].endswith("대운")
    assert d["landscape_scene"]
    assert d["saju_relation"]
    assert d["summary"]
    assert len(d["keywords"]) == 3
    assert len(d["decade_tasks"]) == 3
    assert set(d["domain_analysis"].keys()) == {"career_or_study", "wealth_flow", "relationship", "family"}


def test_analyze_daewoon_period_timeline_phases_has_all_eight_steps_with_ten_years_each():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    phases = data["data"]["timeline_phases"]
    assert len(phases) == 8
    assert [p["step"] for p in phases] == list(range(1, 9))
    for p in phases:
        assert len(p["years"]) == 10
        assert p["ganji_label"].endswith(f"({p['ganji']})")
        for y in p["years"]:
            assert isinstance(y["year"], int)
            assert y["ganji"]
    assert sum(1 for p in phases if p["is_selected"]) == 1


def test_analyze_daewoon_period_works_for_ages_across_the_full_lifespan():
    for target_age in (0, 5, 15, 25, 40, 60, 85, 100):
        data, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=target_age)
        assert 1 <= data["data"]["step"] <= 8
        assert data["data"]["summary"]


def test_analyze_daewoon_period_content_type_and_meta():
    data, is_fallback = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False)
    assert data["content_type"] == "daewoon_period"
    assert isinstance(is_fallback, bool)
    assert data["saju_info"]
    assert data["day_master"]


def test_analyze_daewoon_period_deterministic_for_same_birth_and_age():
    a, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    b, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    assert a["data"] == b["data"]
