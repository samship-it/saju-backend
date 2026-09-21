"""domains/daewoon/pipeline.py — 7단계 대운 해석 파이프라인 검증.

1.원국분석 2.대운분석 3.영역매핑 4.영향도(0~5) 5.고영역구체 6.저영역간소화 7.자연어합성.
연령대(20세 미만/이상)에 따른 영역별 가중치 필터링과 anti-prediction 원칙(특정 사건 단정
금지)이 핵심 회귀 대상이다.
"""
from core.saju_base import calculate_saju
from core.daewoon import daewoon_step_facts
from domains.daewoon.pipeline import (
    ADULT_FOCUS_DOMAINS,
    CHILD_AGE_THRESHOLD,
    CHILD_FOCUS_DOMAINS,
    DOMAIN_DEFINITIONS,
    DOMAIN_ORDER,
    KEY_AREA_MIN_SCORE,
    analyze_daewoon_stage,
    analyze_natal_stage,
    build_domain_pipeline,
    build_domain_sentence,
    score_domains,
)
from domains.daewoon.service import CHILD_AGE_THRESHOLD as SERVICE_CHILD_AGE_THRESHOLD

# Anti-prediction 원칙 — 특정 사건을 단정하는 표현 금지(content.py FORBIDDEN_ADULT_WORDS와
# 같은 설계: 표를 잘못 고쳐도 즉시 예외/테스트 실패로 걸러지게 한다).
_FORBIDDEN_PREDICTION_PHRASES = ["할 것이다", "할 것입니다", "반드시", "확실히"]


def _sample_saju():
    return calculate_saju(1983, 5, 14, 14, 0, gender="female", is_lunar=False)


def _sample_fact(saju):
    dw = saju["daewoon"]
    facts = daewoon_step_facts(saju["day_master"], saju["day_branch"], saju["month_ganji"], dw["direction"] == "순행", count=8)
    return facts[1]  # 정관(己未) 대운(18~27세) — 앞선 폴라리티 작업에서 이미 검증된 단계


# ============================================================================
# 9개 영역 정의 완결성
# ============================================================================
def test_domain_definitions_has_exactly_nine_domains_matching_user_spec():
    expected_labels = {
        "자아/성장", "학업/전문성", "직업/사회", "재물", "가족/부모",
        "형제자매", "친구/인간관계", "애정/연애", "결혼/배우자",
    }
    assert len(DOMAIN_DEFINITIONS) == 9
    assert {d["label"] for d in DOMAIN_DEFINITIONS.values()} == expected_labels
    assert list(DOMAIN_ORDER) == list(DOMAIN_DEFINITIONS.keys())


def test_child_age_threshold_matches_service_module():
    # pipeline.py는 독립 상수를 쓰지만 service.py의 CHILD_AGE_THRESHOLD(20)와 값이
    # 어긋나면 안 된다 — 어긋나면 이 테스트가 즉시 잡아준다.
    assert CHILD_AGE_THRESHOLD == SERVICE_CHILD_AGE_THRESHOLD == 20


def test_focus_domain_sets_match_user_spec_and_are_disjoint():
    assert CHILD_FOCUS_DOMAINS == {"자아_성장", "학업_전문성", "가족_부모", "친구_인간관계"}
    assert ADULT_FOCUS_DOMAINS == {"직업_사회", "재물", "애정_연애", "결혼_배우자"}
    assert CHILD_FOCUS_DOMAINS.isdisjoint(ADULT_FOCUS_DOMAINS)
    assert (CHILD_FOCUS_DOMAINS | ADULT_FOCUS_DOMAINS) <= set(DOMAIN_ORDER)


# ============================================================================
# 1단계: 원국 분석
# ============================================================================
def test_analyze_natal_stage_extracts_day_master_elements_strength_and_sipsin():
    saju = _sample_saju()
    natal = analyze_natal_stage(saju)
    assert natal["day_master"] == saju["day_master"]
    assert natal["day_master_elem"] == saju["day_master_elem"]
    assert natal["strength_verdict"] == saju["strength"]["verdict"]
    assert natal["five_elements"] == saju["five_elements"]
    assert set(natal["natal_sipsin"].keys()) >= {"year", "month", "day"}
    for pos, pair in natal["natal_sipsin"].items():
        assert set(pair.keys()) == {"gan", "ji"}
        assert pair["gan"]


# ============================================================================
# 2단계: 대운 분석
# ============================================================================
def test_analyze_daewoon_stage_computes_sipsin_elements_relations_and_polarity():
    saju = _sample_saju()
    fact = _sample_fact(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    assert daewoon["ganji"] == fact["ganji"]
    assert daewoon["gan_sipsin"] == fact["sipsin"]
    assert daewoon["ji_sipsin"] == fact["sipsin_ji"]
    assert daewoon["gan_elem"] and daewoon["ji_elem"]
    assert set(daewoon["relations"].keys()) >= {"year", "month", "day"}
    assert daewoon["polarity"] in {"favorable", "neutral", "unfavorable"}
    assert daewoon["balance_shift"] in {"widens", "narrows", "neutral"}


def test_analyze_daewoon_stage_relations_match_branch_relation_directly():
    from core.daewoon import branch_relation

    saju = _sample_saju()
    fact = _sample_fact(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    ji = fact["ganji"][1]
    assert daewoon["relations"]["year"] == branch_relation(saju["year_ganji"][1], ji)
    assert daewoon["relations"]["month"] == branch_relation(saju["month_ganji"][1], ji)
    assert daewoon["relations"]["day"] == branch_relation(saju["day_ganji"][1], ji)


# ============================================================================
# 3·4단계: 영역별 영향 분석 + 영향도(0~5)
# ============================================================================
def test_score_domains_returns_nine_scores_within_bounds():
    saju = _sample_saju()
    fact = _sample_fact(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    scored = score_domains(daewoon, age=30, gender="female")
    assert len(scored) == 9
    assert {s["domain"] for s in scored} == set(DOMAIN_ORDER)
    for s in scored:
        assert 0 <= s["score"] <= 5


def test_score_domains_age_weighting_boosts_child_focus_domains_under_twenty():
    # 합성 daewoon_stage로 relation을 전부 "무관"으로 고정해 age 가중치 효과만 순수하게 본다.
    daewoon_stage = {
        "gan_sipsin": "정인", "ji_sipsin": "편인",
        "gan_group": "인성", "ji_group": "인성",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    child = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=10, gender="male")}
    adult = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=30, gender="male")}
    # 학업/전문성(인성 그룹, CHILD_FOCUS)은 20세 미만일 때 정확히 1점 더 높아야 한다.
    assert child["학업_전문성"] == adult["학업_전문성"] + 1
    # 인성 그룹과 무관한 저영역(친구/인간관계, 비겁+식상)은 나이와 무관하게 그대로다
    # (CHILD_FOCUS이긴 하지만 base=0이라 relation_bonus도 0 → 나이 가중치만 붙는다).
    assert child["친구_인간관계"] == 1  # CHILD_FOCUS 가중치 +1만 반영, base/relation은 0


def test_score_domains_age_weighting_boosts_adult_focus_domains_from_twenty():
    daewoon_stage = {
        "gan_sipsin": "편재", "ji_sipsin": "정재",
        "gan_group": "재성", "ji_group": "재성",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    child = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=10, gender="male")}
    adult = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=30, gender="male")}
    assert adult["재물"] == child["재물"] + 1


def test_score_domains_gender_changes_spouse_group_for_love_and_marriage_domains():
    # 관성 대운: 여성은 관성=배우자성이라 애정/결혼 domain base가 붙지만, 남성은 재성이
    # 배우자성이라 관성 대운에서는 붙지 않는다(spouse_star()와 동일 규칙).
    daewoon_stage = {
        "gan_sipsin": "정관", "ji_sipsin": "편관",
        "gan_group": "관성", "ji_group": "관성",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    female = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=30, gender="female")}
    male = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=30, gender="male")}
    assert female["결혼_배우자"] > male["결혼_배우자"]


def test_score_domains_relation_only_bonus_never_reaches_key_area_alone():
    # base=0(이 영역 지배 십신이 이번 대운에 전혀 없음)이면 관계가 아무리 강해도(육합/충)
    # relation_bonus가 최대 1로 깎이고, 나이 가중이 붙어도 최대 2 — 절대 KEY_AREA_MIN_SCORE(3)
    # 에 못 미쳐야 한다(무관한 영역까지 "핵심 변화 영역"으로 부풀려지지 않도록 하는 안전장치).
    daewoon_stage = {
        "gan_sipsin": "식신", "ji_sipsin": "상관",
        "gan_group": "식상", "ji_group": "식상",
        "relations": {"year": "충(충돌·이동)", "month": "육합(협력·인연)", "day": "무관", "hour": "무관"},
    }
    for age in (10, 30):
        scored = {s["domain"]: s["score"] for s in score_domains(daewoon_stage, age=age, gender="male")}
        # 학업/전문성(인성)은 식상 대운과 무관(base=0)이므로 month=육합이어도 낮게 유지.
        assert scored["학업_전문성"] < KEY_AREA_MIN_SCORE


# ============================================================================
# 5·6단계: 고/저영역 문장
# ============================================================================
def test_build_domain_sentence_low_score_uses_exact_user_specified_template():
    entry = {"label": "학업/전문성", "score": 2, "driving_sipsin": "정인"}
    sentence = build_domain_sentence(entry, polarity="neutral")
    assert sentence == "학업/전문성은(는) 이 대운에서 상대적으로 핵심적인 변화 영역은 아니며, 기존 흐름이 유지됩니다."


def test_build_domain_sentence_high_score_includes_change_area_and_tone():
    entry = {"label": "재물", "score": 5, "driving_sipsin": "편재"}
    favorable = build_domain_sentence(entry, polarity="favorable")
    unfavorable = build_domain_sentence(entry, polarity="unfavorable")
    assert "재물" in favorable and "**" in favorable  # 화두는 마크다운 볼드로 감싸진다
    assert favorable != unfavorable
    # anti-prediction 원칙 — 완곡한 가능성 표현("가능성"/"수 있습니다")만 쓴다.
    assert "가능성" in favorable
    assert "수 있습니다" in unfavorable


def test_build_domain_sentence_never_uses_forbidden_prediction_phrases():
    for score in (0, 1, 2, 3, 4, 5):
        for polarity in ("favorable", "neutral", "unfavorable"):
            entry = {"label": "직업/사회", "score": score, "driving_sipsin": "정관"}
            sentence = build_domain_sentence(entry, polarity=polarity)
            for phrase in _FORBIDDEN_PREDICTION_PHRASES:
                assert phrase not in sentence


# ============================================================================
# 7단계: 자연어 합성 + 전체 파이프라인
# ============================================================================
def test_build_domain_pipeline_returns_all_four_stage_outputs():
    saju = _sample_saju()
    fact = _sample_fact(saju)
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    assert set(result.keys()) == {"natal_summary", "daewoon_summary", "domain_scores", "narrative"}
    assert len(result["domain_scores"]) == 9
    for entry in result["domain_scores"]:
        assert set(entry.keys()) == {"domain", "label", "score", "is_key_area", "sentence"}
        assert entry["is_key_area"] == (entry["score"] >= KEY_AREA_MIN_SCORE)
    assert result["narrative"]


def test_build_domain_pipeline_narrative_mentions_every_key_area_label_and_wraps_up_quiet_ones():
    saju = _sample_saju()
    fact = _sample_fact(saju)
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    key_labels = [d["label"] for d in result["domain_scores"] if d["is_key_area"]]
    quiet_labels = [d["label"] for d in result["domain_scores"] if not d["is_key_area"]]
    for label in key_labels:
        assert label in result["narrative"]
    if quiet_labels:
        assert "상대적으로 유지되는 흐름" in result["narrative"]


def test_build_domain_pipeline_never_contains_forbidden_prediction_phrases():
    saju = _sample_saju()
    for step_index in range(8):
        fact = daewoon_step_facts(
            saju["day_master"], saju["day_branch"], saju["month_ganji"], saju["daewoon"]["direction"] == "순행", count=8
        )[step_index]
        result = build_domain_pipeline(saju, fact, age=25, gender="female")
        for phrase in _FORBIDDEN_PREDICTION_PHRASES:
            assert phrase not in result["narrative"]


def test_build_domain_pipeline_low_area_sentences_never_fabricate_specific_events():
    # 사용자 anti-prediction 요구: 저영역은 반드시 고정 간소화 문구여야 하고, 고영역이라도
    # "~했다/할 것이다"류의 확정 서술이 아니라 "~가능성" 완곡 표현이어야 한다.
    saju = _sample_saju()
    fact = _sample_fact(saju)
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    for entry in result["domain_scores"]:
        if not entry["is_key_area"]:
            assert entry["sentence"].endswith("기존 흐름이 유지됩니다.")
        else:
            # anti-prediction 원칙 — 완곡한 가능성 표현("가능성"/"수 있습니다")만 쓴다.
            assert "가능성" in entry["sentence"] or "수 있습니다" in entry["sentence"]


# ============================================================================
# service.py 통합
# ============================================================================
def test_analyze_daewoon_period_includes_domain_pipeline_field():
    from domains.daewoon.service import analyze_daewoon_period

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    dp = data["data"]["domain_pipeline"]
    assert set(dp.keys()) == {"natal_summary", "daewoon_summary", "domain_scores", "narrative"}
    assert len(dp["domain_scores"]) == 9


def test_analyze_daewoon_period_domain_pipeline_shifts_focus_by_age_bracket():
    # 같은 사람, 같은 daewoon_stage 조건이 아니라 실제로 나이만 다르게 조회했을 때
    # 대운 단계 자체가 달라질 수 있으므로, 이 테스트는 "특정 영역이 반드시 오른다"가 아니라
    # is_key_area 집합이 나이에 따라 달라질 수 있음을(파이프라인이 실제로 age를 쓰고 있음을)
    # 확인하는 용도 — 결정론적 단위 검증은 위 score_domains 테스트들이 이미 커버한다.
    from domains.daewoon.service import analyze_daewoon_period

    child, _ = analyze_daewoon_period(2015, 3, 10, 9, 0, "male", False, target_age=8)
    adult, _ = analyze_daewoon_period(2015, 3, 10, 9, 0, "male", False, target_age=45)
    child_scores = {d["domain"]: d["score"] for d in child["data"]["domain_pipeline"]["domain_scores"]}
    adult_scores = {d["domain"]: d["score"] for d in adult["data"]["domain_pipeline"]["domain_scores"]}
    assert child_scores != adult_scores


def test_analyze_daewoon_period_domain_pipeline_deterministic():
    from domains.daewoon.service import analyze_daewoon_period

    a, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    b, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    assert a["data"]["domain_pipeline"] == b["data"]["domain_pipeline"]
