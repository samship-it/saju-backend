"""10년 대운(domains/daewoon) — 평생운세와 별개의 독립 모듈 검증.

십신 10종(비견/겁재/식신/상관/정재/편재/정관/편관/정인/편인) 정/편 분기가 핵심
회귀 대상이다 — 과거에는 5분류(sipsin_group)만 써서 정인/편인처럼 같은 그룹 안의
두 십신이 완전히 동일한 문구를 냈다. 이 파일의 다수 테스트는 "10종 모두 서로
다른 결과"를 직접 검증한다.
"""
import json

from domains.daewoon.content import (
    ALLOWANCE_ECONOMY,
    ALLOWANCE_NUANCE,
    CAREER_ADULT,
    CAREER_YOUTH,
    DECADE_TASKS,
    FAMILY_ENV_NUANCE,
    FAMILY_ENVIRONMENT,
    FAMILY_FLOW,
    FAMILY_NUANCE,
    FORBIDDEN_ADULT_WORDS,
    FRIENDSHIP,
    FRIENDSHIP_NUANCE,
    GROUPS,
    KEYWORDS,
    POLARITY_STATES,
    RELATIONSHIP_FLOW,
    RELATIONSHIP_NUANCE,
    RELATIONSHIP_STATUS_GUIDE,
    SIPSIN_10,
    SIPSIN_CHANGE_AREA,
    SIPSIN_HANJA,
    SIPSIN_KEYWORDS,
    SIPSIN_YINYANG_PAIR,
    STUDY_GROWTH,
    TRANSITION_BACK_CAREER,
    TRANSITION_FRONT_STUDY,
    WEALTH_FLOW,
    WEALTH_NUANCE,
    _has_batchim,
    _josa,
    _resolve_field,
    _with_polarity_note,
    build_career_or_study,
    build_child_domains,
    build_decade_theme,
    build_family,
    build_relationship,
    build_transition_back_domains,
    build_transition_front_domains,
    build_wealth_flow,
    resolve_decade_polarity,
)
from domains.daewoon.landscape import SAJU_RELATION_TEMPLATE, build_decade_landscape
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
    # GROUPS(5분류)는 lifelong 모듈과의 호환을 위해 유지 — daewoon 자체 콘텐츠는
    # 이제 SIPSIN_10(10종)을 기준으로 매칭한다.
    assert set(GROUPS) == set(DOMINANT_GROUPS)


def test_sipsin_10_has_exactly_ten_distinct_entries_with_five_pairs():
    assert len(SIPSIN_10) == 10
    assert len(set(SIPSIN_10)) == 10
    pairs = [
        ("비견", "겁재"), ("식신", "상관"), ("정재", "편재"), ("정관", "편관"), ("정인", "편인"),
    ]
    for a, b in pairs:
        assert a in SIPSIN_10 and b in SIPSIN_10


# ------------------------------------------------------------------ content.py 표 완결성(10종)
def test_keyword_and_decade_task_tables_cover_all_ten_sipsin():
    assert set(KEYWORDS.keys()) == set(SIPSIN_10)
    assert set(DECADE_TASKS.keys()) == set(SIPSIN_10)
    for s in SIPSIN_10:
        assert len(KEYWORDS[s]) == 3
        assert len(DECADE_TASKS[s]) == 3


def test_career_adult_and_youth_tables_cover_all_ten_sipsin_with_distinct_shape():
    assert set(CAREER_ADULT.keys()) == set(SIPSIN_10)
    assert set(CAREER_YOUTH.keys()) == set(SIPSIN_10)
    for s in SIPSIN_10:
        assert set(CAREER_ADULT[s].keys()) == {"core_change", "how_it_shows", "cautions"}
        assert set(CAREER_YOUTH[s].keys()) == {"growth_flow", "study_style", "cautions"}


def test_wealth_relationship_family_base_tables_still_five_way_with_ten_way_nuance():
    # 이 3개 도메인은 5분류 기본 문단 + 10종 뉘앙스 한 문장으로 차별화한다(전면
    # 재작성 대신 오버레이 방식 — build_wealth_flow 등 참고).
    assert set(WEALTH_FLOW.keys()) == set(GROUPS)
    assert set(RELATIONSHIP_FLOW.keys()) == set(GROUPS)
    assert set(FAMILY_FLOW.keys()) == set(GROUPS)
    assert set(WEALTH_NUANCE.keys()) == set(SIPSIN_10)
    assert set(RELATIONSHIP_NUANCE.keys()) == set(SIPSIN_10)
    assert set(FAMILY_NUANCE.keys()) == set(SIPSIN_10)
    assert set(RELATIONSHIP_STATUS_GUIDE.keys()) == {"single", "dating", "married"}


# ------------------------------------------------------------------ content.py 빌더(10종)
def test_build_career_or_study_switches_shape_by_age_bracket():
    adult = build_career_or_study("정재", is_adult=True)
    youth = build_career_or_study("정재", is_adult=False)
    assert set(adult.keys()) == {"core_change", "how_it_shows", "cautions"}
    assert set(youth.keys()) == {"growth_flow", "study_style", "cautions"}
    assert adult != youth


def test_build_career_or_study_distinguishes_jeong_and_pyeon_pairs():
    # 사용자가 명시한 회귀 버그: 같은 그룹의 정/편이 동일한 결과를 내면 안 된다.
    for jeong, pyeon in [
        ("정재", "편재"), ("정관", "편관"), ("정인", "편인"),
    ]:
        assert build_career_or_study(jeong, is_adult=True) != build_career_or_study(pyeon, is_adult=True)
        assert build_career_or_study(jeong, is_adult=False) != build_career_or_study(pyeon, is_adult=False)
    # 비겁/식상은 정/편 이름 자체가 다른 규칙(비견/겁재, 식신/상관)이지만 같은 축이다.
    assert build_career_or_study("비견", is_adult=True) != build_career_or_study("겁재", is_adult=True)
    assert build_career_or_study("식신", is_adult=True) != build_career_or_study("상관", is_adult=True)


def test_build_relationship_includes_guide_only_when_current_decade():
    not_current = build_relationship("식신", "single", is_current=False)
    assert not_current["guide_by_status"] is None
    assert not_current["flow"]

    current_known = build_relationship("식신", "single", is_current=True)
    assert current_known["guide_by_status"] == {"single": RELATIONSHIP_STATUS_GUIDE["single"]}

    current_unknown = build_relationship("식신", None, is_current=True)
    assert current_unknown["guide_by_status"] == RELATIONSHIP_STATUS_GUIDE


def test_build_wealth_flow_and_family_return_full_shape():
    w = build_wealth_flow("편관")
    assert set(w.keys()) == {"earning_style", "cash_flow", "management_caution"}
    f = build_family("편인")
    assert set(f.keys()) == {"change_flow", "warning"}


def test_build_wealth_relationship_family_distinguish_jeong_and_pyeon_pairs_via_nuance():
    for jeong, pyeon in [("정재", "편재"), ("정관", "편관"), ("정인", "편인")]:
        assert build_wealth_flow(jeong) != build_wealth_flow(pyeon)
        assert build_relationship(jeong, None, False) != build_relationship(pyeon, None, False)
        assert build_family(jeong) != build_family(pyeon)


# ------------------------------------------------------------------ 20세 미만 4대 영역(10종)
def test_child_domain_tables_cover_all_ten_sipsin_or_five_groups_as_designed():
    # study_growth는 10종 전면 재작성, 나머지 3영역은 5분류 기본표 + 10종 뉘앙스.
    assert set(STUDY_GROWTH.keys()) == set(SIPSIN_10)
    assert set(ALLOWANCE_ECONOMY.keys()) == set(GROUPS)
    assert set(FRIENDSHIP.keys()) == set(GROUPS)
    assert set(FAMILY_ENVIRONMENT.keys()) == set(GROUPS)
    assert set(ALLOWANCE_NUANCE.keys()) == set(SIPSIN_10)
    assert set(FRIENDSHIP_NUANCE.keys()) == set(SIPSIN_10)
    assert set(FAMILY_ENV_NUANCE.keys()) == set(SIPSIN_10)
    for s in SIPSIN_10:
        assert set(STUDY_GROWTH[s].keys()) == {"school_life", "exam_luck", "aptitude_path"}


def test_build_child_domains_returns_all_four_areas_for_every_sipsin():
    for s in SIPSIN_10:
        child = build_child_domains(s)
        assert set(child.keys()) == {
            "study_growth", "allowance_economy", "friendship", "family_environment",
        }


def test_build_child_domains_distinguishes_jeong_and_pyeon_pairs():
    for jeong, pyeon in [("정재", "편재"), ("정관", "편관"), ("정인", "편인")]:
        assert build_child_domains(jeong) != build_child_domains(pyeon)


def test_child_domain_tables_never_contain_forbidden_adult_words():
    assert FORBIDDEN_ADULT_WORDS
    for s in SIPSIN_10:
        rendered = str(build_child_domains(s))
        for word in FORBIDDEN_ADULT_WORDS:
            assert word not in rendered


# ------------------------------------------------------------------ 과도기 대운 콘텐츠(10종)
def test_transition_content_tables_cover_all_ten_sipsin_with_expected_shape():
    assert set(TRANSITION_FRONT_STUDY.keys()) == set(SIPSIN_10)
    assert set(TRANSITION_BACK_CAREER.keys()) == set(SIPSIN_10)
    for s in SIPSIN_10:
        assert set(TRANSITION_FRONT_STUDY[s].keys()) == {"school_life", "exam_luck", "aptitude_path"}
        assert set(TRANSITION_BACK_CAREER[s].keys()) == {"core_change", "how_it_shows", "cautions"}


def test_transition_front_study_never_contains_forbidden_adult_words():
    for fields in TRANSITION_FRONT_STUDY.values():
        for text in fields.values():
            for word in FORBIDDEN_ADULT_WORDS:
                assert word not in text


def test_build_transition_front_domains_keeps_child_shape_with_overridden_study():
    for s in SIPSIN_10:
        domains = build_transition_front_domains(s)
        assert set(domains.keys()) == {
            "study_growth", "allowance_economy", "friendship", "family_environment",
        }
        assert domains["study_growth"] == dict(TRANSITION_FRONT_STUDY[s])


def test_build_transition_back_domains_keeps_adult_shape_with_overridden_career():
    for s in SIPSIN_10:
        domains = build_transition_back_domains(s, None, False)
        assert set(domains.keys()) == {"career_or_study", "wealth_flow", "relationship", "family"}
        assert domains["career_or_study"] == dict(TRANSITION_BACK_CAREER[s])


def test_transition_front_and_back_distinguish_jeong_and_pyeon_pairs():
    for jeong, pyeon in [("정재", "편재"), ("정관", "편관"), ("정인", "편인")]:
        assert build_transition_front_domains(jeong) != build_transition_front_domains(pyeon)
        assert build_transition_back_domains(jeong, None, False) != build_transition_back_domains(pyeon, None, False)


# ------------------------------------------------------------------ landscape(10종)
def test_build_decade_landscape_reused_from_lifelong_tables():
    from domains.lifelong.landscape import ENV_IMAGE, SUBJECT_IMAGE

    out = build_decade_landscape("수", "戊辰", "정재")
    assert out["scene"] == f"{ENV_IMAGE['토']} 아래 {SUBJECT_IMAGE['수']}"


def test_saju_relation_template_covers_all_ten_sipsin():
    assert set(SAJU_RELATION_TEMPLATE.keys()) == set(SIPSIN_10)


def test_build_decade_landscape_saju_relation_names_the_exact_sipsin():
    out = build_decade_landscape("수", "戊辰", "정재")
    assert "정재운" in out["saju_relation"]
    assert "토" in out["saju_relation"]
    assert "수" in out["saju_relation"]


def test_build_decade_landscape_saju_relation_distinguishes_jeong_and_pyeon():
    jeong = build_decade_landscape("수", "戊辰", "정인")
    pyeon = build_decade_landscape("수", "戊辰", "편인")
    assert jeong["saju_relation"] != pyeon["saju_relation"]
    assert "정인운" in jeong["saju_relation"]
    assert "편인운" in pyeon["saju_relation"]


def test_build_decade_landscape_saju_relation_none_without_sipsin():
    out = build_decade_landscape("수", "戊辰")
    assert out["saju_relation"] is None


# ------------------------------------------------------------------ 10년의 풍경 하단 2/3단계 — 화두(decade_theme)
def test_sipsin_theme_tables_cover_all_ten_sipsin():
    assert set(SIPSIN_KEYWORDS.keys()) == set(SIPSIN_10)
    assert set(SIPSIN_CHANGE_AREA.keys()) == set(SIPSIN_10)
    assert set(SIPSIN_HANJA.keys()) == set(SIPSIN_10)


def test_sipsin_yinyang_pair_covers_all_ten_and_is_symmetric():
    assert set(SIPSIN_YINYANG_PAIR.keys()) == set(SIPSIN_10)
    for s, pair in SIPSIN_YINYANG_PAIR.items():
        assert SIPSIN_YINYANG_PAIR[pair] == s  # 짝의 짝은 자기 자신(대칭)
        assert pair != s


def test_sipsin_yinyang_pair_matches_the_five_jeong_pyeon_pairs():
    expected = {
        frozenset(["비견", "겁재"]), frozenset(["식신", "상관"]),
        frozenset(["정재", "편재"]), frozenset(["정관", "편관"]),
        frozenset(["정인", "편인"]),
    }
    actual = {frozenset([s, p]) for s, p in SIPSIN_YINYANG_PAIR.items()}
    assert actual == expected


def test_build_decade_theme_returns_pair_sipsin_and_sentence_shape():
    out = build_decade_theme("정인")
    assert set(out.keys()) == {"pair_sipsin", "sentence"}
    assert out["pair_sipsin"] == "편인"
    # 2단계 변화 영역·3단계 짝 십신 모두 **로 감싸져 있다 — 프론트가 이미 saju_relation/
    # summary에 쓰는 components/Markdown.tsx(** → <strong>)로 그대로 렌더링한다.
    assert f"**{SIPSIN_CHANGE_AREA['정인']}**" in out["sentence"]
    assert "**편인운(偏印運)**" in out["sentence"]
    assert out["sentence"].startswith("정인은")
    assert "대운의 직접적인 영향을 크게 받지 않는 영역" in out["sentence"]


def test_build_decade_theme_none_when_sipsin_missing():
    assert build_decade_theme(None) is None
    assert build_decade_theme("") is None
    assert build_decade_theme("존재하지않는십신") is None


def test_build_decade_theme_all_ten_sipsin_produce_distinct_sentences():
    # 정재/편재처럼 같은 5분류 안에서도 정/편이 완전히 다른 문장을 내야 한다(핵심 회귀).
    sentences = {build_decade_theme(s)["sentence"] for s in SIPSIN_10}
    assert len(sentences) == len(SIPSIN_10)


def test_build_decade_theme_references_correct_yinyang_pair_for_every_sipsin():
    for s in SIPSIN_10:
        out = build_decade_theme(s)
        pair = SIPSIN_YINYANG_PAIR[s]
        assert out["pair_sipsin"] == pair
        assert f"**{pair}운({SIPSIN_HANJA[pair]}運)**" in out["sentence"]


# ------------------------------------------------------------------ 한글 조사(은/는, 과/와) 선택 헬퍼
def test_has_batchim_detects_final_consonant():
    assert _has_batchim("정인") is True   # "인" 받침 ㄴ
    assert _has_batchim("정재") is False  # "재" 받침 없음
    assert _has_batchim("") is False
    assert _has_batchim("abc") is False  # 한글 완성형 범위 밖


def test_josa_picks_correct_particle_for_every_sipsin_name():
    # 겁재/정재/편재만 받침 없음(는/와), 나머지 7개는 받침 있음(은/과) — 하드코딩하면
    # 절반은 반드시 틀린다(이전에 SIPSIN_THEME_CORE 어미 문제로 겪은 것과 같은 종류의
    # 버그). build_decade_theme()의 실제 출력 문장으로 직접 검증한다.
    no_batchim = {"겁재", "정재", "편재"}
    for s in SIPSIN_10:
        sentence = build_decade_theme(s)["sentence"]
        if s in no_batchim:
            assert sentence.startswith(f"{s}는 "), sentence
        else:
            assert sentence.startswith(f"{s}은 "), sentence


def test_josa_helper_direct_cases():
    assert _josa("정인", "은", "는") == "은"
    assert _josa("정재", "은", "는") == "는"
    assert _josa("서울", "이", "가") == "이"
    assert _josa("학교", "이", "가") == "가"


# ------------------------------------------------------------------ 십신 10종 전체 무결성(핵심 회귀)
def _distinct_count(results):
    return len({json.dumps(r, sort_keys=True, ensure_ascii=False) for r in results})


def test_no_two_of_the_ten_sipsin_produce_identical_adult_domain_analysis():
    results = []
    for s in SIPSIN_10:
        results.append({
            "career_or_study": build_career_or_study(s, is_adult=True),
            "wealth_flow": build_wealth_flow(s),
            "relationship": build_relationship(s, None, False),
            "family": build_family(s),
        })
    assert _distinct_count(results) == 10


def test_no_two_of_the_ten_sipsin_produce_identical_child_domain_analysis():
    results = [build_child_domains(s) for s in SIPSIN_10]
    assert _distinct_count(results) == 10


def test_no_two_of_the_ten_sipsin_produce_identical_transition_domain_analysis():
    front = [build_transition_front_domains(s) for s in SIPSIN_10]
    back = [build_transition_back_domains(s, None, False) for s in SIPSIN_10]
    assert _distinct_count(front) == 10
    assert _distinct_count(back) == 10


def test_no_two_of_the_ten_sipsin_produce_identical_saju_relation():
    results = [build_decade_landscape("목", "甲子", s)["saju_relation"] for s in SIPSIN_10]
    assert len(set(results)) == 10


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
        "domain_analysis", "decade_theme", "timeline_phases", "decade_tasks", "step",
        "age_range", "target_age", "target", "is_current_decade",
        "strength_verdict", "polarity", "domain_pipeline",
    }
    assert d["strength_verdict"] in {"신강", "신약", "중화"}
    assert d["polarity"] in POLARITY_STATES
    assert len(d["domain_pipeline"]["domain_scores"]) == 9
    assert d["daewoon_header"].endswith("대운")
    assert d["landscape_scene"]
    assert d["saju_relation"]
    assert d["summary"]
    assert len(d["keywords"]) == 3
    assert len(d["decade_tasks"]) == 3
    assert set(d["domain_analysis"].keys()) == {"career_or_study", "wealth_flow", "relationship", "family"}
    assert set(d["decade_theme"].keys()) == {"pair_sipsin", "sentence"}
    # saju_relation(1단계)이 "**{십신}운(...)**에 해당합니다"로, decade_theme(2·3단계)이
    # 각각 겹치지 않는 새 정보(키워드/변화 영역, 음양 쌍 십신)를 담아 중복이 없어야 한다.
    assert d["saju_relation"].count("**") == 2
    assert "에 해당합니다" in d["saju_relation"]
    assert "흐름의 10년입니다" not in d["saju_relation"]


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


def test_analyze_daewoon_period_consecutive_steps_never_repeat_domain_analysis():
    # "연속된 대운이 들어와도... 매번 완전히 다른 해석" 요구사항 — 실제 한 사람의
    # 8단계 대운 전부(daewoon_num 기준으로 각 단계 한가운데 나이)를 조회해
    # domain_analysis가 서로 겹치지 않는지 확인한다.
    from core.saju_base import calculate_saju

    saju = calculate_saju(1983, 5, 14, 14, 0, gender="female", is_lunar=False)
    daewoon_num = saju["daewoon"]["daewoon_num"]

    results = []
    for step_index in range(8):
        target_age = daewoon_num + step_index * 10 + 5  # 각 단계의 한가운데 나이
        data, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=target_age)
        results.append(data["data"]["domain_analysis"])
    assert _distinct_count(results) == len(results)


# ============================================================================
# 억부 용신/기신 희기(喜忌) 반영(2026-09-21) — 같은 십신이라도 신강/신약 + 용신/기신에
# 따라 실제 체감 톤이 갈려야 한다는 요구사항 검증.
# ============================================================================

def test_resolve_decade_polarity_classifies_gisin_yongsin_heesin_and_hansin():
    strength = {"yongsin": ["금", "수"], "heesin": ["토"], "gisin": ["화", "목"]}
    # 甲=목(기신), 丙=화(기신), 庚=금(용신), 壬=수(용신), 戊=토(희신), 무관계(표에 없는 천간 없음이므로
    # 한신 케이스는 strength 자체가 비어 있을 때로 별도 검증.
    assert resolve_decade_polarity("甲", strength) == "unfavorable"
    assert resolve_decade_polarity("丙", strength) == "unfavorable"
    assert resolve_decade_polarity("庚", strength) == "favorable"
    assert resolve_decade_polarity("壬", strength) == "favorable"
    assert resolve_decade_polarity("戊", strength) == "favorable"  # 희신도 favorable


def test_resolve_decade_polarity_neutral_when_element_in_neither_list():
    # 목/화가 용신·희신·기신 어디에도 없는 "한신" 오행이면 neutral.
    strength = {"yongsin": ["금"], "heesin": [], "gisin": ["수"]}
    assert resolve_decade_polarity("甲", strength) == "neutral"  # 갑=목, 한신


def test_resolve_decade_polarity_defaults_to_neutral_on_missing_input():
    assert resolve_decade_polarity("甲", None) == "neutral"
    assert resolve_decade_polarity("甲", {}) == "neutral"
    assert resolve_decade_polarity("", {"yongsin": ["목"]}) == "neutral"


def test_resolve_field_picks_polarity_variant_and_passes_through_plain_strings():
    field = {"neutral": "N", "favorable": "F", "unfavorable": "U"}
    assert _resolve_field(field, "favorable") == "F"
    assert _resolve_field(field, "unfavorable") == "U"
    assert _resolve_field(field, "neutral") == "N"
    # 아직 3분기 재작성이 안 된 평문 문자열 필드는 그대로 통과.
    assert _resolve_field("그냥 문자열입니다", "favorable") == "그냥 문자열입니다"


def test_with_polarity_note_appends_only_for_favorable_and_unfavorable():
    base = "기본 문장입니다."
    neutral = _with_polarity_note(base, "wealth_flow", "neutral")
    favorable = _with_polarity_note(base, "wealth_flow", "favorable")
    unfavorable = _with_polarity_note(base, "wealth_flow", "unfavorable")
    assert neutral == base  # 한신은 아무것도 덧붙이지 않는다
    assert favorable.startswith(base) and favorable != base
    assert unfavorable.startswith(base) and unfavorable != base
    assert favorable != unfavorable


def test_career_adult_core_change_and_cautions_are_three_way_polarity_dicts():
    for s in SIPSIN_10:
        assert set(CAREER_ADULT[s]["core_change"].keys()) == {"neutral", "favorable", "unfavorable"}
        assert set(CAREER_ADULT[s]["cautions"].keys()) == {"neutral", "favorable", "unfavorable"}
        # how_it_shows는 아직 평문 문자열(희기보다 십신 자체 성격이 좌우하는 필드).
        assert isinstance(CAREER_ADULT[s]["how_it_shows"], str)


def test_career_youth_growth_flow_and_cautions_are_three_way_polarity_dicts():
    for s in SIPSIN_10:
        assert set(CAREER_YOUTH[s]["growth_flow"].keys()) == {"neutral", "favorable", "unfavorable"}
        assert set(CAREER_YOUTH[s]["cautions"].keys()) == {"neutral", "favorable", "unfavorable"}
        assert isinstance(CAREER_YOUTH[s]["study_style"], str)


def test_study_growth_school_life_and_exam_luck_are_three_way_polarity_dicts():
    for s in SIPSIN_10:
        assert set(STUDY_GROWTH[s]["school_life"].keys()) == {"neutral", "favorable", "unfavorable"}
        assert set(STUDY_GROWTH[s]["exam_luck"].keys()) == {"neutral", "favorable", "unfavorable"}
        assert isinstance(STUDY_GROWTH[s]["aptitude_path"], str)


def test_build_career_or_study_defaults_to_neutral_and_matches_old_behavior():
    # polarity 인자를 생략하면 예전(억부 반영 이전)과 동일한 neutral 문구가 나온다 —
    # 하위 호환성 검증.
    out = build_career_or_study("정관", is_adult=True)
    assert out["core_change"] == CAREER_ADULT["정관"]["core_change"]["neutral"]
    assert out["cautions"] == CAREER_ADULT["정관"]["cautions"]["neutral"]


def test_build_career_or_study_changes_tone_by_polarity_for_every_sipsin():
    for s in SIPSIN_10:
        favorable = build_career_or_study(s, is_adult=True, polarity="favorable")
        unfavorable = build_career_or_study(s, is_adult=True, polarity="unfavorable")
        neutral = build_career_or_study(s, is_adult=True, polarity="neutral")
        assert favorable["core_change"] != unfavorable["core_change"]
        assert favorable["cautions"] != unfavorable["cautions"]
        assert favorable != neutral
        assert unfavorable != neutral
        # how_it_shows(행동 묘사)는 희기와 무관하게 변하지 않는다.
        assert favorable["how_it_shows"] == unfavorable["how_it_shows"] == neutral["how_it_shows"]


def test_build_career_or_study_jeonggwan_favorable_vs_unfavorable_matches_user_example():
    # 사용자 명시 예시: 신강+정관(용신)="조직 안에서 주도적으로 인정받고 성장",
    # 신약+정관(기신)="조직/권위의 압박이 크게 느껴지고 억눌리는 느낌".
    favorable = build_career_or_study("정관", is_adult=True, polarity="favorable")
    unfavorable = build_career_or_study("정관", is_adult=True, polarity="unfavorable")
    assert "주도적으로 인정받고 성장" in favorable["core_change"]
    assert "압박" in unfavorable["core_change"] and "억눌리는" in unfavorable["core_change"]
    # 신약+기신 조합은 "힘들게 느껴질 수 있다"를 명확히 인정하는 톤이어야 한다(무조건
    # 긍정 포장 금지 — 사용자 명시 요구).
    assert "힘들게 느껴질 수 있다" in unfavorable["cautions"]


def test_build_child_domains_school_life_and_exam_luck_change_tone_by_polarity():
    for s in SIPSIN_10:
        favorable = build_child_domains(s, polarity="favorable")["study_growth"]
        unfavorable = build_child_domains(s, polarity="unfavorable")["study_growth"]
        assert favorable["school_life"] != unfavorable["school_life"]
        assert favorable["exam_luck"] != unfavorable["exam_luck"]
        # 구체적 사건·성적 단정 금지 — "반장"·숫자로 된 등수/점수를 직접 언급하지 않는다.
        for text in (favorable["school_life"], favorable["exam_luck"], unfavorable["school_life"], unfavorable["exam_luck"]):
            assert "반장" not in text


def test_secondary_domains_append_polarity_note_only_for_favorable_and_unfavorable():
    neutral = build_wealth_flow("정재", polarity="neutral")
    favorable = build_wealth_flow("정재", polarity="favorable")
    unfavorable = build_wealth_flow("정재", polarity="unfavorable")
    assert favorable["management_caution"].startswith(neutral["management_caution"])
    assert unfavorable["management_caution"].startswith(neutral["management_caution"])
    assert favorable["management_caution"] != neutral["management_caution"]
    assert unfavorable["management_caution"] != neutral["management_caution"]
    assert favorable["management_caution"] != unfavorable["management_caution"]

    fam_neutral = build_family("정인", polarity="neutral")
    fam_favorable = build_family("정인", polarity="favorable")
    assert fam_favorable["warning"] != fam_neutral["warning"]

    rel_neutral = build_relationship("식신", None, False, polarity="neutral")
    rel_unfavorable = build_relationship("식신", None, False, polarity="unfavorable")
    assert rel_unfavorable["flow"] != rel_neutral["flow"]


def test_build_decade_theme_appends_polarity_closing_only_for_favorable_and_unfavorable():
    neutral = build_decade_theme("정관", polarity="neutral")
    favorable = build_decade_theme("정관", polarity="favorable")
    unfavorable = build_decade_theme("정관", polarity="unfavorable")
    assert favorable["sentence"] != neutral["sentence"]
    assert unfavorable["sentence"] != neutral["sentence"]
    assert favorable["sentence"].startswith(neutral["sentence"])
    assert unfavorable["sentence"].startswith(neutral["sentence"])
    # pair_sipsin은 polarity와 무관하게 동일.
    assert favorable["pair_sipsin"] == unfavorable["pair_sipsin"] == neutral["pair_sipsin"] == "편관"


def test_build_decade_theme_default_polarity_is_neutral_backward_compatible():
    # polarity 인자를 생략한 기존 호출은 이전과 완전히 동일한 문장을 낸다.
    assert build_decade_theme("정인") == build_decade_theme("정인", polarity="neutral")


# ----------------------------------------------------------------------------
# 실제 두 사람(신강/신약이 다른, 같은 정관 대운) 비교 — 사용자 요청 검증 시나리오.
# 1996-01-20 06:00 여성(신약, 정관=기신, 35~44세)과 1968-12-28 16:00 남성(신강,
# 정관=용신, 43~52세)은 둘 다 실제 계산 결과로 "정관 대운"에 해당하며 억부가 정반대다
# (둘 다 과도기 대운(15~19세 시작)이 아닌 일반 성인기 구간이라 CAREER_ADULT의 3분기
# 문구가 그대로 적용된다).
# ----------------------------------------------------------------------------

def test_two_real_people_with_opposite_strength_get_opposite_tone_on_the_same_jeonggwan_daewoon():
    weak_gisin, _ = analyze_daewoon_period(1996, 1, 20, 6, 0, "female", False, target_age=38)
    strong_yongsin, _ = analyze_daewoon_period(1968, 12, 28, 16, 0, "male", False, target_age=45)

    # 전제 검증: 실제로 둘 다 정관 대운이고, 신강/신약과 희기가 정반대다.
    assert weak_gisin["data"]["saju_relation"].startswith("이 10년은 **정관운")
    assert strong_yongsin["data"]["saju_relation"].startswith("이 10년은 **정관운")
    assert weak_gisin["data"]["strength_verdict"] == "신약"
    assert strong_yongsin["data"]["strength_verdict"] == "신강"
    assert weak_gisin["data"]["polarity"] == "unfavorable"
    assert strong_yongsin["data"]["polarity"] == "favorable"

    weak_career = weak_gisin["data"]["domain_analysis"]["career_or_study"]
    strong_career = strong_yongsin["data"]["domain_analysis"]["career_or_study"]

    # 십신 이름(정관)은 완전히 같지만 톤은 정반대여야 한다 — 사용자 핵심 요구사항.
    assert weak_career["core_change"] != strong_career["core_change"]
    assert "주도적으로 인정받고 성장" in strong_career["core_change"]
    assert "억눌리는" in weak_career["core_change"]
    assert "힘들게 느껴질 수 있다" in weak_career["cautions"]
