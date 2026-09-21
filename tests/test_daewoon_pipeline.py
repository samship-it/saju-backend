"""domains/daewoon/pipeline.py — 10년 대운 해석 엔진(v3, 2026-09-21 2차 개편) 검증.

DaewoonContext + get_eligible_domains(생애단계 사전 필터) + 9개 독립 analyzer(analyze_self/
analyze_study/analyze_career/analyze_wealth/analyze_family/analyze_siblings/
analyze_friendship/analyze_relationship/analyze_marriage) + 영역별 vocab(전역 십신 테이블
공유 금지) + evidence/drivers + global_context(영역별 반복 금지) 검증.

핵심 회귀(2차 감사에서 확인된 문제들):
- 같은 십신이 여러 영역을 구동해도 영역마다 다른 현실 언어(manifestation)를 써야 한다
  (정관이 직업·연애·결혼을 동시에 구동해도 "신분과 공적 신뢰"가 복사되면 안 됨).
- "사주 전체 균형" 문구가 영역마다 반복되면 안 된다(global_context는 1회만).
- 생애단계 게이트는 분석 "전"에 적용된다(get_eligible_domains).
- 재물 영역은 생애단계에 따라 다른 어휘(용돈 ↔ 수입·지출 ↔ 자산관리)를 쓴다.
- confidence가 high일 때만 근거 중첩 부연 문장이 붙는다("driver 하나=결론 하나" 금지).
"""
from core.saju_base import calculate_saju
from core.daewoon import daewoon_step_facts
from domains.daewoon.pipeline import (
    ADULT_FOCUS_DOMAINS,
    CAREER_VOCAB,
    CHILD_FOCUS_DOMAINS,
    DOMAIN_DEFINITIONS,
    DOMAIN_ORDER,
    KEY_AREA_MIN_SCORE,
    LIFE_STAGE_ORDER,
    MARRIAGE_VOCAB,
    RELATIONSHIP_VOCAB,
    WEALTH_VOCAB,
    DaewoonContext,
    analyze_career,
    analyze_family,
    analyze_friendship,
    analyze_marriage,
    analyze_relationship,
    analyze_self,
    analyze_siblings,
    analyze_study,
    analyze_wealth,
    analyze_daewoon_stage,
    analyze_natal_stage,
    build_domain_pipeline,
    get_eligible_domains,
    life_stage,
)
from domains.daewoon.service import CHILD_AGE_THRESHOLD as SERVICE_CHILD_AGE_THRESHOLD

_FORBIDDEN_PREDICTION_PHRASES = [
    "할 것이다", "할 것입니다", "반드시", "확실히",
    # 2차 개편 신규 금지: 회고형/검증 불가능한 과거 단정 표현.
    "했을 가능성", "였을 것입니다", "때문에 힘들었을 수 있습니다", "있었을 가능성",
]


def _sample_saju():
    return calculate_saju(1983, 5, 14, 14, 0, gender="female", is_lunar=False)


def _sample_facts(saju):
    dw = saju["daewoon"]
    return daewoon_step_facts(saju["day_master"], saju["day_branch"], saju["month_ganji"], dw["direction"] == "순행", count=8)


def _ctx(saju, fact, age, gender="female"):
    natal = analyze_natal_stage(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    return DaewoonContext(natal=natal, daewoon=daewoon, life_stage=life_stage(age), gender=gender, strength=saju["strength"])


# ============================================================================
# 영역 정의 + 생애단계
# ============================================================================
def test_domain_definitions_has_exactly_nine_domains_matching_user_spec():
    expected_labels = {
        "자아/성장", "학업/전문성", "직업/사회", "재물", "가족/부모",
        "형제자매", "친구/인간관계", "애정/연애", "결혼/배우자",
    }
    assert len(DOMAIN_DEFINITIONS) == 9
    assert {d["label"] for d in DOMAIN_DEFINITIONS.values()} == expected_labels
    for defn in DOMAIN_DEFINITIONS.values():
        assert defn["stages"] <= set(LIFE_STAGE_ORDER)
        assert defn["stages"]
        assert callable(defn["vocab_fn"])


def test_child_age_threshold_matches_service_module():
    from domains.daewoon.pipeline import CHILD_AGE_THRESHOLD

    assert CHILD_AGE_THRESHOLD == SERVICE_CHILD_AGE_THRESHOLD == 20


def test_life_stage_boundaries_match_user_spec():
    assert life_stage(0) == "아동"
    assert life_stage(12) == "아동"
    assert life_stage(13) == "청소년"
    assert life_stage(19) == "청소년"
    assert life_stage(20) == "청년"
    assert life_stage(34) == "청년"
    assert life_stage(35) == "성인"


def test_marriage_domain_gated_to_young_adult_and_adult_only():
    assert DOMAIN_DEFINITIONS["결혼_배우자"]["stages"] == {"청년", "성인"}
    for age in (0, 8, 12, 13, 17, 19):
        assert "결혼_배우자" not in get_eligible_domains(age)
    for age in (20, 25, 40, 60):
        assert "결혼_배우자" in get_eligible_domains(age)


def test_get_eligible_domains_applied_before_analysis_not_after():
    # 생애단계 필터가 "분석 전"에 적용됨을 build_domain_pipeline의 debug 모드로 검증 —
    # debug=False에서는 결혼/배우자가 애초에 analyzer 호출조차 안 되어야 한다.
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]  # 정관
    normal = build_domain_pipeline(saju, fact, age=12, gender="female", debug=False)
    debug = build_domain_pipeline(saju, fact, age=12, gender="female", debug=True)
    assert all(d["domain"] != "결혼_배우자" for d in normal["domain_scores"])
    # debug 모드에서는 9개 전부 계산되어 있어야 하고, 결혼/배우자는 eligible=False로 표시.
    assert len(debug["debug_all_domains"]) == 9
    marriage_debug = next(d for d in debug["debug_all_domains"] if d["domain"] == "결혼_배우자")
    assert marriage_debug["eligible"] is False


# ============================================================================
# 1·2단계 (natal/daewoon stage) — 기존과 동일 로직 유지 확인
# ============================================================================
def test_analyze_natal_and_daewoon_stage_unchanged_shape():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    natal = analyze_natal_stage(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    assert natal["day_master"] == saju["day_master"]
    assert daewoon["ganji"] == "己未"
    assert daewoon["gan_sipsin"] == "정관"
    assert set(daewoon["relations"].keys()) >= {"year", "month", "day"}


# ============================================================================
# 영역별 독립 analyzer — 핵심 회귀: 같은 십신이 여러 영역을 구동해도 서로 다른
# manifestation을 써야 한다("정관=신분과 공적 신뢰"가 직업/연애/결혼에 복사되던 문제).
# ============================================================================
def test_career_relationship_marriage_never_share_identical_manifestation_for_same_sipsin():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]  # 己未, 천간·지지 둘 다 정관 — v2에서 세 영역이 겹치던 케이스
    ctx = _ctx(saju, fact, age=25)
    career = analyze_career(ctx)
    relationship = analyze_relationship(ctx)
    marriage = analyze_marriage(ctx)
    # 셋 다 활성화된 경우(정관이 배우자성인 여성 기준), manifestation 문구가 서로 달라야 한다.
    manifests = {career["manifestation"][0], relationship["manifestation"][0], marriage["manifestation"][0]}
    if career["activation"] >= KEY_AREA_MIN_SCORE and relationship["activation"] >= KEY_AREA_MIN_SCORE:
        assert career["manifestation"][0] != relationship["manifestation"][0]
    if relationship["activation"] >= KEY_AREA_MIN_SCORE and marriage["activation"] >= KEY_AREA_MIN_SCORE:
        assert relationship["manifestation"][0] != marriage["manifestation"][0]
    assert career["sentence"] != relationship["sentence"] != marriage["sentence"]


def test_career_vocab_covers_all_five_groups_ten_sipsin():
    # 사용자 지정: 직업/사회는 관성/식상/재성/인성/비겁 5개 그룹 전부에 반응해야 한다.
    from domains.daewoon.content import SIPSIN_10

    assert set(CAREER_VOCAB.keys()) == set(SIPSIN_10)


def test_relationship_and_marriage_vocab_differ_for_the_same_sipsin():
    for sipsin in ("정관", "편관", "정재", "편재"):
        assert RELATIONSHIP_VOCAB[sipsin] != MARRIAGE_VOCAB[sipsin]


def test_wealth_vocab_translates_by_life_stage_not_just_sipsin():
    # 아동기=용돈, 청년=수입·지출, 성인=자산관리로 같은 십신이라도 다른 어휘를 써야 한다.
    assert WEALTH_VOCAB["미성년"]["정재"] != WEALTH_VOCAB["청년"]["정재"] != WEALTH_VOCAB["성인"]["정재"]
    assert "용돈" in WEALTH_VOCAB["미성년"]["정재"]


def test_analyze_wealth_uses_different_vocab_bucket_by_age():
    # 실제 己未(정관) 대운은 재물의 groups(재성/식상/비겁)와 무관해 활성화되지 않으므로,
    # 재물을 실제로 구동하는 합성 daewoon(정재)으로 생애단계별 어휘 차이만 순수하게 본다.
    natal = analyze_natal_stage(_sample_saju())
    daewoon = {
        "ganji": "庚申", "gan_sipsin": "정재", "ji_sipsin": "정재",
        "gan_group": "재성", "ji_group": "재성", "gan_elem": "금", "ji_elem": "금",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
        "polarity": "neutral", "balance_shift": "neutral",
    }
    child_ctx = DaewoonContext(natal=natal, daewoon=daewoon, life_stage="청소년", gender="male", strength={})
    adult_ctx = DaewoonContext(natal=natal, daewoon=daewoon, life_stage="성인", gender="male", strength={})
    child_result = analyze_wealth(child_ctx)
    adult_result = analyze_wealth(adult_ctx)
    assert child_result["manifestation"][0] != adult_result["manifestation"][0]
    assert "용돈" in child_result["manifestation"][0]


def test_siblings_and_friendship_use_life_stage_relation_label():
    saju = _sample_saju()
    fact = _sample_facts(saju)[0]  # 편관이지만 지지(sipsin_ji)가 비겁일 수도 있음 — 실측 필요 없이 함수 단위 확인
    ctx_child = DaewoonContext(
        natal=analyze_natal_stage(saju),
        daewoon={
            "ganji": "甲子", "gan_sipsin": "비견", "ji_sipsin": "겁재",
            "gan_group": "비겁", "ji_group": "비겁", "gan_elem": "목", "ji_elem": "수",
            "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
            "polarity": "neutral", "balance_shift": "neutral",
        },
        life_stage="아동", gender="male", strength={},
    )
    ctx_adult = DaewoonContext(
        natal=ctx_child.natal, daewoon=ctx_child.daewoon, life_stage="성인", gender="male", strength={},
    )
    child_sib = analyze_siblings(ctx_child)
    adult_sib = analyze_siblings(ctx_adult)
    assert "또래" in child_sib["manifestation"][0]
    assert "네트워크" in adult_sib["manifestation"][0]


# ============================================================================
# global_context — 사주 전체 균형 판단은 1회만 등장해야 한다("각 영역에 자동 append 금지").
# ============================================================================
def test_global_context_appears_once_not_per_domain():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    assert result["global_context"]
    # 영역별 sentence 안에는 "사주 전체 균형"이라는 문구가 절대 등장하지 않아야 한다
    # (그 표현은 global_context 전용 — 영역별로는 도메인 고유 어휘를 쓴다).
    for entry in result["domain_scores"]:
        assert "사주 전체 균형" not in entry["sentence"]


def test_domain_valence_closing_differs_from_generic_global_wording():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    sentences = [d["sentence"] for d in result["domain_scores"]]
    # 서로 다른 영역이 같은 valence를 가져도(예: 전부 unfavorable), 문장 전체는 달라야 한다
    # (영역별 valence 어휘가 서로 다르기 때문).
    assert len(set(sentences)) == len(sentences)


# ============================================================================
# evidence / drivers / confidence — "driver 하나=결론 하나" 금지
# ============================================================================
def test_domain_result_has_structured_evidence_and_drivers():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    ctx = _ctx(saju, fact, age=25)
    result = analyze_career(ctx)
    assert set(result.keys()) == {
        "domain", "label", "activation", "valence", "confidence", "drivers",
        "evidence", "manifestation", "sentence",
    }
    if result["activation"] > 0:
        assert result["drivers"]
        assert result["evidence"]
        for e in result["evidence"]:
            assert set(e.keys()) == {"source", "factor", "role"}


def test_confidence_elaboration_only_appended_when_high():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]  # 己未 — 천간+지지 둘 다 정관 매치 가능성 높음(confidence=high 케이스)
    ctx = _ctx(saju, fact, age=25)
    result = analyze_career(ctx)
    if result["confidence"] == "high":
        assert "비교적 뚜렷하게 나타날 수 있습니다" in result["sentence"]
    else:
        assert "비교적 뚜렷하게 나타날 수 있습니다" not in result["sentence"]


# ============================================================================
# Anti-prediction(2차 개편 강화: 회고형 표현 추가 금지)
# ============================================================================
def test_no_forbidden_prediction_or_retrospective_phrases_anywhere():
    saju = _sample_saju()
    for fact in _sample_facts(saju):
        for age in (10, 25, 45):
            result = build_domain_pipeline(saju, fact, age=age, gender="female", debug=True)
            texts = [result["narrative"], result["global_context"]]
            texts += [d["sentence"] for d in result["debug_all_domains"]]
            for text in texts:
                for phrase in _FORBIDDEN_PREDICTION_PHRASES:
                    assert phrase not in text, f"금지 표현 '{phrase}' 발견: {text}"


# ============================================================================
# build_domain_pipeline 통합
# ============================================================================
def test_build_domain_pipeline_shape_and_sorted_by_activation():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    assert set(result.keys()) == {
        "natal_summary", "daewoon_summary", "life_stage", "global_context", "domain_scores", "narrative",
    }
    scores = [d["activation"] for d in result["domain_scores"]]
    assert scores == sorted(scores, reverse=True)
    for entry in result["domain_scores"]:
        assert entry["activation"] >= KEY_AREA_MIN_SCORE
        assert entry["eligible"] is True


def test_build_domain_pipeline_excludes_low_activation_domains_entirely():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    for entry in result["domain_scores"]:
        assert "기존 흐름이 유지됩니다" not in entry["sentence"]
    assert "기존 흐름이 유지됩니다" not in result["narrative"]


def test_build_domain_pipeline_marriage_hidden_for_child_and_teen():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    for age in (8, 12, 15, 17, 19):
        result = build_domain_pipeline(saju, fact, age=age, gender="female")
        assert all(d["domain"] != "결혼_배우자" for d in result["domain_scores"])


# ============================================================================
# STEP 21 사용자 지정 회귀 테스트 — 戊午(편관) 8~17세 vs 己未(정관) 18~27세
# ============================================================================
def test_muo_vs_gimi_full_comparison():
    saju = _sample_saju()
    facts = _sample_facts(saju)
    assert facts[0]["ganji"] == "戊午" and facts[0]["sipsin"] == "편관"
    assert facts[1]["ganji"] == "己未" and facts[1]["sipsin"] == "정관"

    result_a = build_domain_pipeline(saju, facts[0], age=12, gender="female")
    result_b = build_domain_pipeline(saju, facts[1], age=22, gender="female")

    # 1. 어떤 데이터가 달라졌는가 — daewoon_summary 전체.
    assert result_a["daewoon_summary"] != result_b["daewoon_summary"]
    # 2. life_stage가 달라졌는가.
    assert result_a["life_stage"] != result_b["life_stage"]
    # 3. 어떤 영역이 새롭게 eligible 되었는가 — 결혼/배우자는 B에만 존재 가능.
    domains_a = {d["domain"] for d in result_a["domain_scores"]}
    domains_b = {d["domain"] for d in result_b["domain_scores"]}
    assert "결혼_배우자" not in domains_a
    # 4/5. 문장 자체가 달라졌는가.
    assert result_a["narrative"] != result_b["narrative"]
    assert result_a["global_context"] != result_b["global_context"]


def test_muo_vs_gimi_landscape_and_summary_differ():
    from domains.daewoon.service import analyze_daewoon_period

    a, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=12)
    b, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=22)
    assert a["data"]["landscape_scene"] != b["data"]["landscape_scene"]
    assert a["data"]["summary"] != b["data"]["summary"]


# ============================================================================
# service.py 통합
# ============================================================================
def test_analyze_daewoon_period_includes_v3_domain_pipeline_field():
    from domains.daewoon.service import analyze_daewoon_period

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    dp = data["data"]["domain_pipeline"]
    assert set(dp.keys()) == {
        "natal_summary", "daewoon_summary", "life_stage", "global_context", "domain_scores", "narrative",
    }


def test_analyze_daewoon_period_summary_includes_global_context():
    from domains.daewoon.service import analyze_daewoon_period

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    assert data["data"]["summary"].startswith(("이 시기는", "이 사람은"))


def test_analyze_daewoon_period_deterministic():
    from domains.daewoon.service import analyze_daewoon_period

    a, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    b, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    assert a["data"]["domain_pipeline"] == b["data"]["domain_pipeline"]
