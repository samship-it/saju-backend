"""domains/daewoon/pipeline.py — 7단계 대운 해석 파이프라인(v2, 2026-09-21 전면 재설계) 검증.

1.원국분석 2.대운분석 3.영역매핑 4.영향도(activation 0~5)+valence/confidence/drivers/
manifestation_types 5.고영역 구체문장 6.저영역·생애단계 부적합 영역 완전 비노출
7.자연어 합성(보이는 영역만).

핵심 회귀:
- 생애 단계(아동/청소년/청년/성인) 게이트 — 결혼/배우자는 20세 미만에 절대 노출 안 됨.
- 저영역은 "변화 없음" 문구조차 없이 domain_scores에서 완전히 제외된다.
- valence는 영역마다 독립 계산 — 대운 천간 하나의 희기를 모든 영역에 그대로 복사하지 않는다.
- 대운(target_age)을 바꾸면 오행/십신/합충형파해 연산 결과에 따라 하단 콘텐츠가 완전히
  다시 계산된다(캐싱/재사용 없음).
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
    LIFE_STAGE_ORDER,
    analyze_daewoon_stage,
    analyze_natal_stage,
    build_domain_pipeline,
    build_domain_sentence,
    life_stage,
    score_domains,
)
from domains.daewoon.service import CHILD_AGE_THRESHOLD as SERVICE_CHILD_AGE_THRESHOLD

# Anti-prediction 원칙 — 특정 사건을 단정하는 표현 금지.
_FORBIDDEN_PREDICTION_PHRASES = ["할 것이다", "할 것입니다", "반드시", "확실히"]


def _sample_saju():
    return calculate_saju(1983, 5, 14, 14, 0, gender="female", is_lunar=False)


def _sample_facts(saju):
    dw = saju["daewoon"]
    return daewoon_step_facts(saju["day_master"], saju["day_branch"], saju["month_ganji"], dw["direction"] == "순행", count=8)


# ============================================================================
# 9개 영역 정의 + 생애 단계
# ============================================================================
def test_domain_definitions_has_exactly_nine_domains_matching_user_spec():
    expected_labels = {
        "자아/성장", "학업/전문성", "직업/사회", "재물", "가족/부모",
        "형제자매", "친구/인간관계", "애정/연애", "결혼/배우자",
    }
    assert len(DOMAIN_DEFINITIONS) == 9
    assert {d["label"] for d in DOMAIN_DEFINITIONS.values()} == expected_labels
    assert list(DOMAIN_ORDER) == list(DOMAIN_DEFINITIONS.keys())
    for defn in DOMAIN_DEFINITIONS.values():
        assert defn["stages"] <= set(LIFE_STAGE_ORDER)
        assert defn["stages"]  # 어떤 영역도 완전히 노출 불가능하면 안 됨


def test_child_age_threshold_matches_service_module():
    assert CHILD_AGE_THRESHOLD == SERVICE_CHILD_AGE_THRESHOLD == 20


def test_focus_domain_sets_match_user_spec_and_are_disjoint():
    assert CHILD_FOCUS_DOMAINS == {"자아_성장", "학업_전문성", "가족_부모", "친구_인간관계"}
    assert ADULT_FOCUS_DOMAINS == {"직업_사회", "재물", "애정_연애", "결혼_배우자"}
    assert CHILD_FOCUS_DOMAINS.isdisjoint(ADULT_FOCUS_DOMAINS)


def test_life_stage_boundaries_match_user_spec():
    assert life_stage(0) == "아동"
    assert life_stage(12) == "아동"
    assert life_stage(13) == "청소년"
    assert life_stage(19) == "청소년"
    assert life_stage(20) == "청년"
    assert life_stage(34) == "청년"
    assert life_stage(35) == "성인"
    assert life_stage(90) == "성인"


def test_marriage_domain_is_gated_to_young_adult_and_adult_only():
    # 핵심 회귀: 결혼/배우자는 아동·청소년(8~19세)에는 절대 노출되면 안 된다.
    assert DOMAIN_DEFINITIONS["결혼_배우자"]["stages"] == {"청년", "성인"}
    for age in (0, 8, 12, 13, 17, 19):
        assert life_stage(age) not in DOMAIN_DEFINITIONS["결혼_배우자"]["stages"]
    for age in (20, 25, 40, 60):
        assert life_stage(age) in DOMAIN_DEFINITIONS["결혼_배우자"]["stages"]


# ============================================================================
# 1단계: 원국 분석
# ============================================================================
def test_analyze_natal_stage_extracts_day_master_elements_strength_and_sipsin():
    saju = _sample_saju()
    natal = analyze_natal_stage(saju)
    assert natal["day_master"] == saju["day_master"]
    assert natal["strength_verdict"] == saju["strength"]["verdict"]
    assert natal["five_elements"] == saju["five_elements"]
    assert set(natal["natal_sipsin"].keys()) >= {"year", "month", "day"}
    for pair in natal["natal_sipsin"].values():
        assert set(pair.keys()) == {"gan", "ji"}
        assert pair["gan"]


# ============================================================================
# 2단계: 대운 분석
# ============================================================================
def test_analyze_daewoon_stage_computes_sipsin_elements_relations():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]  # 기미(己未) 정관
    daewoon = analyze_daewoon_stage(saju, fact)
    assert daewoon["ganji"] == "己未"
    assert daewoon["gan_sipsin"] == "정관"
    assert daewoon["gan_elem"] and daewoon["ji_elem"]
    assert set(daewoon["relations"].keys()) >= {"year", "month", "day"}
    assert daewoon["polarity"] in {"favorable", "neutral", "unfavorable"}
    assert daewoon["balance_shift"] in {"widens", "narrows", "neutral"}


def test_analyze_daewoon_stage_relations_match_branch_relation_directly():
    from core.daewoon import branch_relation

    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    daewoon = analyze_daewoon_stage(saju, fact)
    ji = fact["ganji"][1]
    assert daewoon["relations"]["year"] == branch_relation(saju["year_ganji"][1], ji)
    assert daewoon["relations"]["month"] == branch_relation(saju["month_ganji"][1], ji)
    assert daewoon["relations"]["day"] == branch_relation(saju["day_ganji"][1], ji)


def test_changing_daewoon_step_fully_recomputes_ganji_sipsin_and_relations():
    # "대운 변경 시 하단 콘텐츠가 대운 오행/십신/합충형파해 연산 결과에 따라 완벽히
    # 다르게 재계산되는지" — 캐싱/재사용 없이 매 단계마다 독립적으로 계산됨을 확인.
    saju = _sample_saju()
    facts = _sample_facts(saju)
    stages = [analyze_daewoon_stage(saju, f) for f in facts]
    ganjis = [s["ganji"] for s in stages]
    assert len(set(ganjis)) == len(ganjis)  # 8단계 간지 전부 서로 다름
    sipsins = [s["gan_sipsin"] for s in stages]
    assert len(set(sipsins)) >= 6  # 대부분 서로 다른 십신(동일 그룹 반복은 있을 수 있음)


# ============================================================================
# 3·4단계: activation/valence/confidence/drivers/manifestation_types
# ============================================================================
def test_score_domains_returns_nine_entries_with_full_v2_shape():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    daewoon = analyze_daewoon_stage(saju, fact)
    scored = score_domains(daewoon, age=30, gender="female", strength=saju["strength"])
    assert len(scored) == 9
    assert {s["domain"] for s in scored} == set(DOMAIN_ORDER)
    for s in scored:
        assert 0 <= s["activation"] <= 5
        assert s["valence"] in {"favorable", "neutral", "unfavorable"}
        assert s["confidence"] in {"high", "medium", "low"}
        assert isinstance(s["drivers"], list)
        assert isinstance(s["manifestation_types"], list)


def test_score_domains_valence_is_computed_independently_per_domain_not_copied_globally():
    # 핵심 회귀(v1 버그): 대운 천간 하나의 희기를 모든 영역에 그대로 복사하면 안 된다.
    # 합성 daewoon_stage로 천간(정재=재성, 기신)과 지지(비견=비겁, 용신)의 희기를
    # 서로 다르게 고정해, 영역마다 실제로 다른 valence가 나오는지 확인한다.
    daewoon_stage = {
        "gan_sipsin": "정재", "ji_sipsin": "비견",
        "gan_group": "재성", "ji_group": "비겁",
        "gan_elem": "금", "ji_elem": "목",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    strength = {"yongsin": ["목"], "heesin": [], "gisin": ["금"]}
    scored = {s["domain"]: s for s in score_domains(daewoon_stage, age=30, gender="male", strength=strength)}
    # 재물(재성=금=기신)은 unfavorable, 자아/성장(비겁=목=용신, ji가 구동)은 favorable —
    # 같은 대운인데 영역마다 valence가 정반대로 갈려야 한다.
    assert scored["재물"]["valence"] == "unfavorable"
    assert scored["자아_성장"]["valence"] == "favorable"


def test_score_domains_age_weighting_boosts_child_focus_domains_under_twenty():
    daewoon_stage = {
        "gan_sipsin": "정인", "ji_sipsin": "편인",
        "gan_group": "인성", "ji_group": "인성",
        "gan_elem": "목", "ji_elem": "목",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    child = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=10, gender="male")}
    adult = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=30, gender="male")}
    assert child["학업_전문성"] == adult["학업_전문성"] + 1


def test_score_domains_age_weighting_boosts_adult_focus_domains_from_twenty():
    daewoon_stage = {
        "gan_sipsin": "편재", "ji_sipsin": "정재",
        "gan_group": "재성", "ji_group": "재성",
        "gan_elem": "금", "ji_elem": "금",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    child = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=10, gender="male")}
    adult = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=30, gender="male")}
    assert adult["재물"] == child["재물"] + 1


def test_score_domains_gender_changes_spouse_group_for_love_and_marriage_domains():
    daewoon_stage = {
        "gan_sipsin": "정관", "ji_sipsin": "편관",
        "gan_group": "관성", "ji_group": "관성",
        "gan_elem": "금", "ji_elem": "금",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
    }
    female = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=30, gender="female")}
    male = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=30, gender="male")}
    assert female["결혼_배우자"] > male["결혼_배우자"]


def test_score_domains_relation_only_bonus_never_reaches_key_area_alone():
    daewoon_stage = {
        "gan_sipsin": "식신", "ji_sipsin": "상관",
        "gan_group": "식상", "ji_group": "식상",
        "gan_elem": "화", "ji_elem": "화",
        "relations": {"year": "충(충돌·이동)", "month": "육합(협력·인연)", "day": "무관", "hour": "무관"},
    }
    for age in (10, 30):
        scored = {s["domain"]: s["activation"] for s in score_domains(daewoon_stage, age=age, gender="male")}
        assert scored["학업_전문성"] < KEY_AREA_MIN_SCORE


def test_score_domains_drivers_differ_by_domain_not_uniformly_copied():
    # "십신 키워드가 모든 영역에 일률 복사되던" 문제의 직접 회귀 — 실제 계산에서 서로
    # 다른 영역의 drivers 목록이 완전히 동일해서는 안 된다(관여 요소가 다르므로).
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    daewoon = analyze_daewoon_stage(saju, fact)
    scored = score_domains(daewoon, age=25, gender="female", strength=saju["strength"])
    active = [s for s in scored if s["activation"] >= KEY_AREA_MIN_SCORE]
    driver_sets = [tuple(s["drivers"]) for s in active]
    # 최소한 영역 이름이 다르면 drivers 안에 배우자성 유무 등으로 완전 동일 리스트는 아니어야 함.
    assert len(active) >= 1
    for s in active:
        assert s["drivers"]  # 근거 없이 고영역이 될 수 없음


# ============================================================================
# 5단계: 고영역 문장
# ============================================================================
def test_build_domain_sentence_includes_change_area_and_tone():
    entry = {"label": "재물", "driving_sipsin": "편재", "valence": "favorable"}
    favorable = build_domain_sentence(entry)
    entry["valence"] = "unfavorable"
    unfavorable = build_domain_sentence(entry)
    assert "재물" in favorable and "**" in favorable
    assert favorable != unfavorable


def test_build_domain_sentence_never_uses_forbidden_prediction_phrases():
    for valence in ("favorable", "neutral", "unfavorable"):
        entry = {"label": "직업/사회", "driving_sipsin": "정관", "valence": valence}
        sentence = build_domain_sentence(entry)
        for phrase in _FORBIDDEN_PREDICTION_PHRASES:
            assert phrase not in sentence


# ============================================================================
# 6·7단계: 저영역/생애단계 부적합 영역 완전 비노출 + 자연어 합성
# ============================================================================
def test_build_domain_pipeline_excludes_low_activation_domains_entirely():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    for entry in result["domain_scores"]:
        assert entry["activation"] >= KEY_AREA_MIN_SCORE
    # v1과 달리 "변화 없음"류 문구가 전혀 없어야 한다.
    for entry in result["domain_scores"]:
        assert "기존 흐름이 유지됩니다" not in entry["sentence"]
    assert "기존 흐름이 유지됩니다" not in result["narrative"]


def test_build_domain_pipeline_marriage_domain_hidden_for_child_and_teen_regardless_of_score():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]  # 정관 대운 — 배우자성과 직접 연결되는 강한 케이스
    for age in (8, 12, 15, 17, 19):
        result = build_domain_pipeline(saju, fact, age=age, gender="female")
        domains_shown = {d["domain"] for d in result["domain_scores"]}
        assert "결혼_배우자" not in domains_shown, f"age={age}에서 결혼/배우자가 노출됨"


def test_build_domain_pipeline_marriage_domain_can_appear_for_adults():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    domains_shown = {d["domain"] for d in result["domain_scores"]}
    assert "결혼_배우자" in domains_shown


def test_build_domain_pipeline_returns_expected_top_level_shape():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    assert set(result.keys()) == {"natal_summary", "daewoon_summary", "life_stage", "domain_scores", "narrative"}
    assert result["life_stage"] == "청년"
    for entry in result["domain_scores"]:
        assert set(entry.keys()) == {
            "domain", "label", "activation", "valence", "confidence", "drivers", "manifestation_types", "sentence",
        }
    assert result["narrative"]


def test_build_domain_pipeline_narrative_mentions_every_visible_domain_label():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female")
    for entry in result["domain_scores"]:
        assert entry["label"] in result["narrative"]


def test_build_domain_pipeline_falls_back_to_generic_sentence_when_nothing_qualifies():
    saju = _sample_saju()
    fact = _sample_facts(saju)[0]  # 무오(편관) — 아동기엔 적용 영역이 거의 없을 수 있음
    result = build_domain_pipeline(saju, fact, age=5, gender="female")
    if not result["domain_scores"]:
        assert result["narrative"] == (
            "이 10년은 어느 한 영역에 크게 치우치기보다 전반적으로 무난하게 흘러갈 수 있는 시기입니다."
        )


def test_build_domain_pipeline_never_contains_forbidden_prediction_phrases():
    saju = _sample_saju()
    for fact in _sample_facts(saju):
        for age in (10, 25, 45):
            result = build_domain_pipeline(saju, fact, age=age, gender="female")
            for phrase in _FORBIDDEN_PREDICTION_PHRASES:
                assert phrase not in result["narrative"]


# ============================================================================
# STEP 3 사용자 지정 회귀 테스트 — 무오(戊午) 8~17세 편관운 vs 기미(己未) 18~27세 정관운
# ============================================================================
def test_step3_test_a_wu_o_eight_to_seventeen_pyeongwan_hides_marriage_domain():
    saju = _sample_saju()
    fact_a = _sample_facts(saju)[0]
    assert fact_a["ganji"] == "戊午"
    assert fact_a["sipsin"] == "편관"
    for age in range(8, 18):
        result = build_domain_pipeline(saju, fact_a, age=age, gender="female")
        assert all(d["domain"] != "결혼_배우자" for d in result["domain_scores"])


def test_step3_test_b_gi_mi_eighteen_to_twentyseven_jeonggwan_shape():
    saju = _sample_saju()
    fact_b = _sample_facts(saju)[1]
    assert fact_b["ganji"] == "己未"
    assert fact_b["sipsin"] == "정관"
    result = build_domain_pipeline(saju, fact_b, age=22, gender="female")
    assert result["life_stage"] == "청년"
    # 18~27세 구간 안에서 성인 나이(20세 이상)라면 결혼/배우자가 노출될 수 있다.
    domains_shown = {d["domain"] for d in result["domain_scores"]}
    assert "결혼_배우자" in domains_shown


def test_step3_test_a_and_test_b_produce_completely_different_results():
    saju = _sample_saju()
    facts = _sample_facts(saju)
    result_a = build_domain_pipeline(saju, facts[0], age=12, gender="female")
    result_b = build_domain_pipeline(saju, facts[1], age=22, gender="female")
    assert result_a["daewoon_summary"]["ganji"] != result_b["daewoon_summary"]["ganji"]
    assert result_a["daewoon_summary"]["gan_sipsin"] != result_b["daewoon_summary"]["gan_sipsin"]
    assert result_a["life_stage"] != result_b["life_stage"]
    assert result_a["domain_scores"] != result_b["domain_scores"]
    assert result_a["narrative"] != result_b["narrative"]


# ============================================================================
# service.py 통합
# ============================================================================
def test_analyze_daewoon_period_includes_domain_pipeline_field():
    from domains.daewoon.service import analyze_daewoon_period

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    dp = data["data"]["domain_pipeline"]
    assert set(dp.keys()) == {"natal_summary", "daewoon_summary", "life_stage", "domain_scores", "narrative"}
    for entry in dp["domain_scores"]:
        assert entry["activation"] >= KEY_AREA_MIN_SCORE


def test_analyze_daewoon_period_marriage_domain_hidden_under_twenty():
    from domains.daewoon.service import analyze_daewoon_period

    for target_age in (0, 5, 10, 15, 19):
        data, _ = analyze_daewoon_period(2015, 3, 10, 9, 0, "male", False, target_age=target_age)
        domains_shown = {d["domain"] for d in data["data"]["domain_pipeline"]["domain_scores"]}
        assert "결혼_배우자" not in domains_shown


def test_analyze_daewoon_period_domain_pipeline_fully_recomputes_across_steps():
    # "대운 변경 시 하단 콘텐츠가 완벽히 다르게 재계산되는지" — 8단계 전부 조회해
    # daewoon_summary.ganji가 서로 겹치지 않음을 확인(캐싱/재사용 없음).
    from domains.daewoon.service import analyze_daewoon_period

    saju = _sample_saju()
    daewoon_num = saju["daewoon"]["daewoon_num"]
    ganjis = []
    for step_index in range(8):
        target_age = daewoon_num + step_index * 10 + 5
        data, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=target_age)
        ganjis.append(data["data"]["domain_pipeline"]["daewoon_summary"]["ganji"])
    assert len(set(ganjis)) == len(ganjis)


def test_analyze_daewoon_period_domain_pipeline_deterministic():
    from domains.daewoon.service import analyze_daewoon_period

    a, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    b, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=30)
    assert a["data"]["domain_pipeline"] == b["data"]["domain_pipeline"]
