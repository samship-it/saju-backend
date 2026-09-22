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
    _VALENCE_CLOSING,
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


def test_career_vocab_covers_all_five_groups_ten_sipsin_across_all_stage_buckets():
    # 사용자 지정: 직업/사회는 관성/식상/재성/인성/비겁 5개 그룹 전부에 반응해야 한다.
    # STEP3(2026-09-21): CAREER_VOCAB이 {미성년,청년,성인} 3버킷 구조로 바뀌었으므로
    # 버킷마다 10종을 전부 커버하는지 확인한다.
    from domains.daewoon.content import SIPSIN_10

    assert set(CAREER_VOCAB.keys()) == {"미성년", "청년", "성인"}
    for bucket in CAREER_VOCAB.values():
        assert set(bucket.keys()) == set(SIPSIN_10)


def test_career_vocab_differs_by_life_stage_for_the_same_sipsin():
    assert CAREER_VOCAB["미성년"]["정관"] != CAREER_VOCAB["청년"]["정관"] != CAREER_VOCAB["성인"]["정관"]


def test_relationship_and_marriage_vocab_differ_for_the_same_sipsin_and_stage():
    for bucket in ("미성년", "청년", "성인"):
        for sipsin in ("정관", "편관", "정재", "편재"):
            assert RELATIONSHIP_VOCAB[bucket][sipsin] != MARRIAGE_VOCAB[bucket][sipsin]


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


def test_friendship_uses_life_stage_relation_label():
    """친구_인간관계는 여전히 _relation_label(또래/동료/네트워크) prefix를 쓴다 —
    이 단어 자체가 "사회적 관계망" 맥락이라 이 domain에는 그대로 맞는다(STEP6-1)."""
    ctx_child = DaewoonContext(
        natal={}, daewoon={
            "ganji": "甲子", "gan_sipsin": "비견", "ji_sipsin": "겁재",
            "gan_group": "비겁", "ji_group": "비겁", "gan_elem": "목", "ji_elem": "수",
            "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
            "polarity": "neutral", "balance_shift": "neutral",
        },
        life_stage="아동", gender="male", strength={},
    )
    ctx_adult = DaewoonContext(
        natal={}, daewoon=ctx_child.daewoon, life_stage="성인", gender="male", strength={},
    )
    child_fr = analyze_friendship(ctx_child)
    adult_fr = analyze_friendship(ctx_adult)
    assert "또래" in child_fr["manifestation"][0]
    assert "네트워크" in adult_fr["manifestation"][0]


def test_siblings_no_longer_shares_friendship_relation_label():
    """STEP6-1: 형제자매는 더 이상 _relation_label(또래/동료/네트워크) prefix를 쓰지
    않는다 — 그 prefix가 친구_인간관계와 동일해 중복의 원인이었다(STEP6 감사)."""
    ctx_child = DaewoonContext(
        natal={}, daewoon={
            "ganji": "甲子", "gan_sipsin": "비견", "ji_sipsin": "겁재",
            "gan_group": "비겁", "ji_group": "비겁", "gan_elem": "목", "ji_elem": "수",
            "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
            "polarity": "neutral", "balance_shift": "neutral",
        },
        life_stage="아동", gender="male", strength={},
    )
    ctx_adult = DaewoonContext(
        natal={}, daewoon=ctx_child.daewoon, life_stage="성인", gender="male", strength={},
    )
    child_sib = analyze_siblings(ctx_child)
    adult_sib = analyze_siblings(ctx_adult)
    for text in (child_sib["manifestation"][0], adult_sib["manifestation"][0]):
        assert "또래" not in text and "네트워크" not in text and "동료" not in text
    # 미성년/성인 각각 다른 문구여야 하고(생애단계 분화 유지), 형제자매 맥락이 직접 드러나야 한다.
    assert child_sib["manifestation"][0] != adult_sib["manifestation"][0]
    assert "형제자매" in child_sib["manifestation"][0]
    assert "형제자매" in adult_sib["manifestation"][0]


# ============================================================================
# STEP6-1: 형제자매 ↔ 친구_인간관계 manifestation 의미 분리(semantic-marker 기반).
# 단일 단어 하나에 의존하는 brittle 테스트를 피하기 위해 "카테고리 소속"(가족/혈연 맥락
# 단어 집합 vs 사회적 관계망 맥락 단어 집합)으로 검증한다.
# ============================================================================
_FAMILY_MARKERS = {"형제", "자매", "가족", "혈연", "부모", "가정"}
_SOCIAL_MARKERS = {"친구", "동료", "네트워크", "모임", "커뮤니티", "인맥", "인연", "무리", "집단", "또래"}


def _sibling_friendship_ctx(sipsin: str, stage: str) -> DaewoonContext:
    group = "비겁"
    daewoon = {
        "ganji": "甲子", "gan_sipsin": sipsin, "ji_sipsin": sipsin,
        "gan_group": group, "ji_group": group, "gan_elem": "목", "ji_elem": "수",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
        "polarity": "neutral", "balance_shift": "neutral",
    }
    return DaewoonContext(natal={}, daewoon=daewoon, life_stage=stage, gender="male", strength={})


def test_siblings_and_friendship_manifestation_use_disjoint_semantic_markers():
    """비견/겁재 각각, 미성년/청년/성인 각각에서 형제자매는 가족맥락 마커만,
    친구_인간관계는 사회적관계망 마커만 포함해야 한다(섹션 6-1/6-2/6-3)."""
    for sipsin in ("비견", "겁재"):
        for stage in LIFE_STAGE_ORDER:
            ctx = _sibling_friendship_ctx(sipsin, stage)
            sib_text = analyze_siblings(ctx)["manifestation"][0]
            fr_text = analyze_friendship(ctx)["manifestation"][0]

            sib_family_hit = any(m in sib_text for m in _FAMILY_MARKERS)
            sib_social_hit = any(m in sib_text for m in _SOCIAL_MARKERS)
            fr_family_hit = any(m in fr_text for m in _FAMILY_MARKERS)
            fr_social_hit = any(m in fr_text for m in _SOCIAL_MARKERS)

            assert sib_family_hit, f"형제자매({sipsin},{stage})에 가족맥락 마커가 없음: {sib_text}"
            assert not sib_social_hit, f"형제자매({sipsin},{stage})에 사회관계망 마커가 섞임: {sib_text}"
            assert fr_social_hit, f"친구_인간관계({sipsin},{stage})에 사회관계망 마커가 없음: {fr_text}"
            assert not fr_family_hit, f"친구_인간관계({sipsin},{stage})에 가족맥락 마커가 섞임: {fr_text}"
            # 섹션 6-4: 동일 대운에서 두 domain이 함께 활성화되어도 같은 문장을 반복하지 않는다.
            assert sib_text != fr_text


def test_siblings_manifestation_differs_across_life_stages():
    for sipsin in ("비견", "겁재"):
        texts = {stage: analyze_siblings(_sibling_friendship_ctx(sipsin, stage))["manifestation"][0]
                 for stage in ("아동", "청년", "성인")}
        assert len(set(texts.values())) == len(texts), f"{sipsin}: 생애단계별 문구가 겹침: {texts}"


def test_friendship_manifestation_differs_across_life_stages():
    for sipsin in ("비견", "겁재"):
        texts = {stage: analyze_friendship(_sibling_friendship_ctx(sipsin, stage))["manifestation"][0]
                 for stage in ("아동", "청년", "성인")}
        assert len(set(texts.values())) == len(texts), f"{sipsin}: 생애단계별 문구가 겹침: {texts}"


def test_siblings_and_friendship_still_activate_together_when_bigyeop_fires():
    """domain definition(groups/palace)은 이번 STEP에서 건드리지 않았으므로, 비겁이 뜨면
    두 domain이 여전히 함께 meaningful(활성화)될 수 있어야 한다 — 활성화 자체를 없애는
    게 아니라 활성화됐을 때의 문장 의미만 분리하는 것이 이번 수정의 목적."""
    ctx = _sibling_friendship_ctx("비견", "성인")
    sib = analyze_siblings(ctx)
    fr = analyze_friendship(ctx)
    assert sib["is_primary"] and fr["is_primary"]
    assert sib["driving_sipsin"] == fr["driving_sipsin"] == "비견"
    assert sib["manifestation"][0] != fr["manifestation"][0]


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
_DOMAIN_RESULT_SCHEMA = {
    "domain", "label", "eligible", "life_stage", "activation", "is_primary", "source",
    "driving_sipsin", "driving_group", "specificity",
    "valence", "confidence", "drivers", "evidence", "manifestation", "sentence",
}
# domain_scores(build_domain_pipeline()의 최종 출력)에 담기는 항목만 추가로 갖는 필드 —
# _assign_priority_tiers()를 거친 것만 priority_tier가 채워진다(STEP5-A §10/Test8).
_DOMAIN_SCORES_SCHEMA = _DOMAIN_RESULT_SCHEMA | {"priority_tier"}


def test_domain_result_has_structured_evidence_and_drivers():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    ctx = _ctx(saju, fact, age=25)
    result = analyze_career(ctx)
    assert set(result.keys()) == _DOMAIN_RESULT_SCHEMA
    assert result["source"] == "domain_pipeline"
    assert result["is_primary"] == (result["activation"] >= KEY_AREA_MIN_SCORE)
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
# STEP8-B: sentence engine(_VALENCE_CLOSING/_build_sentence/_confidence_elaboration)
# 재설계 검증 — STEP8-A 감사에서 확인된 "형제자매/친구_인간관계 neutral closing 완전
# 동일", "core+closing이 구조/흐름입니다를 기계적으로 반복", "confidence 부연이 9개
# domain 전부 동일 문구"라는 3개 문제가 실제로 해소됐는지 코드 레벨에서 고정한다.
# ============================================================================
def _bigyeop_ctx(sipsin, stage="성인", gender="male"):
    daewoon = {
        "ganji": "甲子", "gan_sipsin": sipsin, "ji_sipsin": sipsin,
        "gan_group": "비겁", "ji_group": "비겁", "gan_elem": "목", "ji_elem": "수",
        "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
        "polarity": "neutral", "balance_shift": "neutral",
    }
    return DaewoonContext(natal={}, daewoon=daewoon, life_stage=stage, gender=gender, strength={})


def test_siblings_and_friendship_closing_no_longer_identical():
    """STEP8-A에서 발견된 형제자매/친구_인간관계 neutral closing 100% 동일 버그가
    STEP8-B로 해소됐는지 확인 — 두 domain 모두 groups={비겁}(친구는 +식상)을 공유해
    비겁이 뜨면 거의 항상 동시활성화되므로, closing이 같으면 실사용자가 그대로 본다."""
    ctx = _bigyeop_ctx("비견")
    sib = analyze_siblings(ctx)
    fr = analyze_friendship(ctx)
    assert sib["valence"] == fr["valence"] == "neutral"
    assert sib["sentence"] != fr["sentence"]
    # closing(두 번째 문장)까지 서로 달라야 한다 — manifestation만 다르고 closing이
    # 같으면 STEP8-A가 지적한 문제가 그대로 남는다.
    sib_closing = sib["sentence"].split(". ")[1]
    fr_closing = fr["sentence"].split(". ")[1]
    assert sib_closing != fr_closing


def test_all_domain_closings_pairwise_distinct_per_valence():
    """9개 domain의 _VALENCE_CLOSING 27개 항목 중 완전히 동일한 문자열이 하나도 없어야
    한다(favorable/neutral/unfavorable 각각 내에서 전부 pairwise 비교)."""
    for valence in ("favorable", "neutral", "unfavorable"):
        texts = [_VALENCE_CLOSING[dom][valence] for dom in DOMAIN_ORDER]
        assert len(texts) == len(set(texts)), f"{valence} closing에 완전 동일 문구 존재: {texts}"


def test_core_sentence_no_longer_forces_heureum_ibnida_suffix():
    """core 문장이 더 이상 '~구조가 나타나는 흐름입니다'로 고정되지 않는다 — manifestation
    이 이미 '...하는 구조'로 끝나는데 core가 '흐름입니다'를 또 붙이고, favorable/
    unfavorable closing도 '~흐름입니다'로 끝나던 6개 domain에서 '구조'·'흐름입니다'가
    한 문단에 각 2회씩 반복되던 문제(STEP8-A)가 해소됐는지 확인."""
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    ctx = _ctx(saju, fact, age=25)
    result = analyze_career(ctx)
    core = result["sentence"].split(". ")[0]
    assert core.endswith("나타납니다")
    assert not core.endswith("흐름입니다")


def test_confidence_elaboration_differs_across_domains():
    """STEP8-A에서 확인된 '9개 domain 전부 confidence 부연이 완전 동일 문구'였던 문제가
    해소됐는지 확인 — 동일 evidence 패턴(gan+ji 매치)이어도 domain마다 다른 영역어가
    들어가 문장이 달라야 한다. 단 평가 대상은 '신호 선명도'라는 메타 정보뿐이지 새
    WHAT을 만들면 안 되므로, 문장 앞부분(근거 종류)은 domain과 무관하게 동일해도 된다."""
    ctx = _bigyeop_ctx("비견")
    self_r = analyze_self(ctx)
    career_r = analyze_career(ctx)
    assert self_r["confidence"] == career_r["confidence"] == "high"
    self_conf = self_r["sentence"].split(". ")[-1]
    career_conf = career_r["sentence"].split(". ")[-1]
    assert self_conf != career_conf
    assert "판단과 선택" in self_conf
    assert "역할과 책임" in career_conf


def test_no_exact_duplicate_sentence_when_bigyeop_drives_five_domains():
    """비견 하나가 자아/직업/재물/형제자매/친구 5개 domain을 동시에 구동하는 실측
    패턴(STEP7 감사 辛酉/庚申 사례)에서 5개 sentence가 전부 서로 달라야 한다."""
    ctx = _bigyeop_ctx("비견")
    sentences = [
        analyze_self(ctx)["sentence"], analyze_career(ctx)["sentence"], analyze_wealth(ctx)["sentence"],
        analyze_siblings(ctx)["sentence"], analyze_friendship(ctx)["sentence"],
    ]
    assert len(sentences) == len(set(sentences))


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
        # STEP3 정책 §1/§3: 사용자에게 노출되는 domain_scores는 전부 is_primary=True이고
        # source="domain_pipeline"이어야 한다(legacy_fallback이 섞이지 않는다).
        assert entry["is_primary"] is True
        assert entry["source"] == "domain_pipeline"


# ============================================================================
# STEP3 정책 검증 — activation<3 비노출, life_stage 전역 확장, 십신명 노출 fallback 제거
# ============================================================================
def test_low_activation_domains_are_not_primary_and_excluded_from_domain_scores():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=25, gender="female", debug=True)
    low = [d for d in result["debug_all_domains"] if d["activation"] < KEY_AREA_MIN_SCORE]
    assert low  # 이 케이스엔 최소 하나는 저활성 영역이 있어야 테스트가 의미 있음
    for d in low:
        assert d["is_primary"] is False
        assert d["domain"] not in {e["domain"] for e in result["domain_scores"]}


def test_fallback_manifestation_never_leaks_raw_sipsin_name():
    # STEP3 항목5: *_VOCAB에 없는 십신이 원문 그대로("정관 기운이 작용하는 구조") 노출되던
    # fallback을 5분류 안전망으로 교체했다 — 어떤 domain/십신 조합에서도 십신 10종 이름이
    # manifestation 문구에 그대로 등장하면 안 된다.
    from domains.daewoon.content import SIPSIN_10

    saju = _sample_saju()
    for fact in _sample_facts(saju):
        for age in (5, 15, 25, 45):
            result = build_domain_pipeline(saju, fact, age=age, gender="female", debug=True)
            for entry in result["debug_all_domains"]:
                phrase = entry["manifestation"][0]
                for sipsin in SIPSIN_10:
                    assert sipsin not in phrase, f"{entry['domain']}에 십신명 '{sipsin}' 노출: {phrase}"


def test_life_stage_translation_expanded_beyond_wealth_to_priority_one_domains():
    # STEP2 정책 확정: life_stage 번역이 재물 하나가 아니라 1순위 4개 domain(직업/재물/
    # 애정/결혼) 전부에 적용돼야 한다. 합성 daewoon으로 각 domain을 실제로 구동시켜
    # life_stage(미성년/청년/성인)에 따라 manifestation이 달라지는지 직접 확인한다.
    natal = analyze_natal_stage(_sample_saju())

    def _daewoon(sipsin, group, elem):
        return {
            "ganji": "甲子", "gan_sipsin": sipsin, "ji_sipsin": sipsin,
            "gan_group": group, "ji_group": group, "gan_elem": elem, "ji_elem": elem,
            "relations": {"year": "무관", "month": "무관", "day": "무관", "hour": "무관"},
            "polarity": "neutral", "balance_shift": "neutral",
        }

    cases = [
        (analyze_career, _daewoon("정관", "관성", "토"), "청소년", "성인"),
        (analyze_wealth, _daewoon("정재", "재성", "금"), "청소년", "성인"),
        (analyze_relationship, _daewoon("정관", "관성", "토"), "청소년", "성인"),
        (analyze_marriage, _daewoon("정관", "관성", "토"), "청년", "성인"),
    ]
    for analyzer, daewoon, stage_a, stage_b in cases:
        ctx_a = DaewoonContext(natal=natal, daewoon=daewoon, life_stage=stage_a, gender="female", strength={})
        ctx_b = DaewoonContext(natal=natal, daewoon=daewoon, life_stage=stage_b, gender="female", strength={})
        result_a, result_b = analyzer(ctx_a), analyzer(ctx_b)
        assert result_a["manifestation"][0] != result_b["manifestation"][0], analyzer.__name__


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


def test_muo_vs_gimi_debug_all_domains_traceable_via_drivers_and_evidence():
    # 사용자 지정 STEP1 성공 조건: "왜 career/wealth/friendship 결과가 같거나 다른가"를
    # drivers/evidence로 코드 수준에서 설명할 수 있어야 한다. debug=True로 생애단계 게이트
    # 없이 9개 전부(eligible 플래그 포함) 계산해 domain별로 직접 비교한다.
    saju = _sample_saju()
    facts = _sample_facts(saju)
    debug_a = build_domain_pipeline(saju, facts[0], age=12, gender="female", debug=True)["debug_all_domains"]
    debug_b = build_domain_pipeline(saju, facts[1], age=22, gender="female", debug=True)["debug_all_domains"]
    by_domain_a = {d["domain"]: d for d in debug_a}
    by_domain_b = {d["domain"]: d for d in debug_b}

    for domain in DOMAIN_ORDER:
        a, b = by_domain_a[domain], by_domain_b[domain]
        assert a["life_stage"] == "아동" and b["life_stage"] == "청년"
        # eligible/life_stage는 항상 표준 스키마에 존재한다(호출 경로와 무관). is_primary
        # 인 항목은 _assign_priority_tiers()를 거쳐 priority_tier가 추가로 붙는다(STEP5-A).
        expected_a = _DOMAIN_SCORES_SCHEMA if a["eligible"] and a["is_primary"] else _DOMAIN_RESULT_SCHEMA
        expected_b = _DOMAIN_SCORES_SCHEMA if b["eligible"] and b["is_primary"] else _DOMAIN_RESULT_SCHEMA
        assert set(a.keys()) == expected_a
        assert set(b.keys()) == expected_b

    # career: 편관(A, 아동이라 eligible=False)과 정관(B, 청년이라 eligible=True + 실제 driver
    # 있음)의 activation/eligible/drivers가 달라야 하고, 그 이유가 evidence에 그대로 있다.
    career_a, career_b = by_domain_a["직업_사회"], by_domain_b["직업_사회"]
    assert career_a["eligible"] is False  # 아동기는 직업/사회 자체가 부적합
    assert career_b["eligible"] is True
    assert career_a["drivers"] != career_b["drivers"]

    # wealth: 편관/정관 둘 다 재물의 groups(재성/식상/비겁)와 무관 — activation이 낮고
    # drivers가 비어있다시피 한 것도 evidence 부재로 설명 가능해야 한다.
    wealth_a, wealth_b = by_domain_a["재물"], by_domain_b["재물"]
    assert wealth_a["activation"] < KEY_AREA_MIN_SCORE
    assert wealth_b["activation"] < KEY_AREA_MIN_SCORE

    # friendship: 편관/정관 둘 다 친구의 groups(비겁/식상)와 무관 — 그래서 결과가 "같다"면
    # 그 이유(둘 다 해당 사항 없음)가 evidence 비어있음으로 추적 가능해야 한다.
    friend_a, friend_b = by_domain_a["친구_인간관계"], by_domain_b["친구_인간관계"]
    if friend_a["activation"] == friend_b["activation"] == 0:
        assert friend_a["evidence"] == friend_b["evidence"] == []


def test_muo_vs_gimi_landscape_and_summary_differ():
    from domains.daewoon.service import analyze_daewoon_period

    a, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=12)
    b, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=22)
    assert a["data"]["landscape_scene"] != b["data"]["landscape_scene"]
    assert a["data"]["summary"] != b["data"]["summary"]


# ============================================================================
# STEP5-A: priority_tier 구현 검증(Test 1~9, 사용자 지정 그대로)
# ============================================================================
def _tiers_of(saju, fact, age, gender="female"):
    result = build_domain_pipeline(saju, fact, age=age, gender=gender)
    return {d["domain"]: d["priority_tier"] for d in result["domain_scores"]}


def test_step5a_test1_jikeop_sahoe_mechanism_can_demote_below_primary():
    # Test 1: 사용자 지정 원래 문구는 "직업_사회가 activation>=3이라고 항상 primary가
    # 되지 않는 구조인지 확인"이었으나, 1983-05-14 14:00 여성의 실제 8개 대운
    # 중년 표본에서는 직업_사회가 **8/8 전부 primary**로 나왔다(실측 확인, 아래 테스트로
    # 고정) — activation 공식(Formula D)을 이번 STEP에서 바꾸지 않았기 때문에, 직업_사회의
    # "천간+지지 매치가 구조적으로 항상 base=3 보장"(STEP4-A-2 증명) 특성이 여전히 남아
    # 있어 이 특정 원국에서는 다른 domain에 밀리는 사례가 관찰되지 않았다. 이건 버그가
    # 아니라 "activation 공식을 안 바꾸기로 한 이번 STEP의 정책적 귀결"이다(보고서 참고).
    saju = _sample_saju()
    facts = _sample_facts(saju)
    tier_counts = {"primary": 0, "secondary": 0, "supporting": 0, "missing": 0}
    for f in facts:
        step = f["step"]
        age = saju["daewoon"]["daewoon_num"] + (step - 1) * 10 + 5
        tiers = _tiers_of(saju, f, age)
        tier_counts[tiers.get("직업_사회", "missing")] += 1
    assert tier_counts == {"primary": 8, "secondary": 0, "supporting": 0, "missing": 0}


def test_step5a_test1b_priority_tier_mechanism_can_demote_jikeop_sahoe_when_outmatched():
    # Test1의 실측(8/8 primary)이 "메커니즘 결함"이 아니라 "이 사람 데이터의 우연"임을
    # 증명하기 위한 합성 케이스. 직업_사회(palace=월주)와 애정_연애(palace=일주, 여성
    # 배우자성=관성)를 둘 다 관성으로 구동하되, 월주 관계는 "무관", 일주 관계만 "충"으로
    # 강하게 줘서 직업_사회는 구조적 최소(base=3+관계0)에 머물고 애정_연애만 relation
    # 보너스를 받아 앞서도록 만든다 — 두 domain 다 ADULT_FOCUS_DOMAINS라 age_focus는
    # 동일하게 받으므로 순수하게 relation 차이만으로 activation이 갈린다.
    natal = analyze_natal_stage(_sample_saju())
    daewoon = {
        "ganji": "丁巳", "gan_sipsin": "정관", "ji_sipsin": "편관",
        "gan_group": "관성", "ji_group": "관성", "gan_elem": "화", "ji_elem": "화",
        "relations": {"year": "무관", "month": "무관", "day": "충(충돌·이동)", "hour": "무관"},
        "polarity": "neutral", "balance_shift": "neutral",
    }
    ctx = DaewoonContext(natal=natal, daewoon=daewoon, life_stage="성인", gender="female", strength={})
    career = analyze_career(ctx)        # base=3(관성, 월주=무관, +age_focus1) = 4
    relationship = analyze_relationship(ctx)  # base=3(식상은 매치 안 하지만 배우자성=관성 매치, 일주=충 +2, +age_focus1) = 6->5
    assert relationship["activation"] > career["activation"]
    assert career["activation"] == KEY_AREA_MIN_SCORE + 1  # 4(구조적 floor 3 + age_focus 1, relation 없음)


def test_step5a_test2_gyeongsin_three_domains_all_primary():
    # Test 2: 庚申 — 학업_전문성/가족_부모/직업_사회 activation=5 동률 -> 셋 다 primary.
    saju = _sample_saju()
    fact = _sample_facts(saju)[2]
    assert fact["ganji"] == "庚申"
    tiers = _tiers_of(saju, fact, age=33)
    assert tiers["학업_전문성"] == "primary"
    assert tiers["가족_부모"] == "primary"
    assert tiers["직업_사회"] == "primary"


def test_step5a_test3_gyehae_tier_structure():
    # Test 3: 癸亥 — 자아_성장/형제자매/재물/직업_사회=primary, 친구_인간관계=secondary.
    saju = _sample_saju()
    fact = _sample_facts(saju)[5]
    assert fact["ganji"] == "癸亥"
    tiers = _tiers_of(saju, fact, age=63)
    assert tiers["자아_성장"] == "primary"
    assert tiers["형제자매"] == "primary"
    assert tiers["재물"] == "primary"
    assert tiers["직업_사회"] == "primary"
    assert tiers["친구_인간관계"] == "secondary"


def test_step5a_test4_giwi_three_domains_all_primary():
    # Test 4: 己未 — 결혼_배우자/애정_연애/직업_사회 셋 다 primary.
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    assert fact["ganji"] == "己未"
    tiers = _tiers_of(saju, fact, age=23)
    assert tiers["결혼_배우자"] == "primary"
    assert tiers["애정_연애"] == "primary"
    assert tiers["직업_사회"] == "primary"


def test_step5a_test5_muo_age13_only_career_primary():
    # Test 5: 戊午 age13 — 직업_사회만 primary(억지로 다른 domain을 채우지 않음).
    saju = _sample_saju()
    fact = _sample_facts(saju)[0]
    assert fact["ganji"] == "戊午"
    tiers = _tiers_of(saju, fact, age=13)
    assert tiers == {"직업_사회": "primary"}


def test_step5a_test6_complete_tie_stays_co_primary_not_split_by_arbitrary_order():
    # Test 6: 완전 동률(activation+confidence+specificity 전부 동일) domain은 임의의
    # 4번째 기준으로 한쪽만 primary가 되지 않는다 — 癸亥의 자아_성장/형제자매가 실제로
    # activation/confidence/specificity 전부 동일함을 먼저 확인한 뒤, 둘 다 primary인지 검증.
    saju = _sample_saju()
    fact = _sample_facts(saju)[5]
    result = build_domain_pipeline(saju, fact, age=63, gender="female")
    by_domain = {d["domain"]: d for d in result["domain_scores"]}
    self_growth, siblings = by_domain["자아_성장"], by_domain["형제자매"]
    assert (self_growth["activation"], self_growth["confidence"], self_growth["specificity"]) == (
        siblings["activation"], siblings["confidence"], siblings["specificity"],
    )
    assert self_growth["priority_tier"] == siblings["priority_tier"] == "primary"


def test_step5a_test7_activation_never_reversed_by_specificity():
    # Test 7: activation 5와 4에서, specificity가 높은 4가 5를 역전시키지 않는다(항상
    # activation이 더 높은 쪽이 더 상위 또는 동일 tier, specificity로는 절대 안 역전).
    saju = _sample_saju()
    for f in _sample_facts(saju):
        step = f["step"]
        age = saju["daewoon"]["daewoon_num"] + (step - 1) * 10 + 5
        result = build_domain_pipeline(saju, f, age=age, gender="female")
        for d in result["domain_scores"]:
            higher_act = [x for x in result["domain_scores"] if x["activation"] > d["activation"]]
            for h in higher_act:
                assert _PRIORITY_TIER_RANK_FOR_TEST[h["priority_tier"]] <= _PRIORITY_TIER_RANK_FOR_TEST[d["priority_tier"]]


_PRIORITY_TIER_RANK_FOR_TEST = {"primary": 0, "secondary": 1, "supporting": 2}


def test_step5a_test8_low_activation_domain_never_gets_priority_tier():
    # Test 8: activation<3 domain은 specificity=1.0(scope=1)이라도 priority_tier를 못 받는다.
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]  # 己未
    result = build_domain_pipeline(saju, fact, age=23, gender="female", debug=True)
    for d in result["debug_all_domains"]:
        if d["activation"] < KEY_AREA_MIN_SCORE:
            assert "priority_tier" not in d, f"{d['domain']}(activation={d['activation']})가 priority_tier를 가짐"


def test_step5a_test9_life_stage_eligibility_unchanged():
    # Test 9: life-stage eligibility가 기존과 동일하게 유지된다 — 20세 미만에 결혼/배우자
    # 비노출(기존 v3 회귀 테스트와 동일 조건을 priority_tier 도입 후에도 재확인).
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    for age in (8, 12, 15, 17, 19):
        result = build_domain_pipeline(saju, fact, age=age, gender="female")
        assert all(d["domain"] != "결혼_배우자" for d in result["domain_scores"])


def test_step5a_domain_scores_sort_order_is_deterministic_tier_then_activation_then_specificity():
    saju = _sample_saju()
    fact = _sample_facts(saju)[5]  # 癸亥, 여러 tier가 섞인 케이스
    result = build_domain_pipeline(saju, fact, age=63, gender="female")
    scores = result["domain_scores"]
    tier_ranks = [_PRIORITY_TIER_RANK_FOR_TEST[d["priority_tier"]] for d in scores]
    assert tier_ranks == sorted(tier_ranks)
    # 같은 tier 안에서는 activation desc, 그 안에서 specificity desc.
    for i in range(len(scores) - 1):
        a, b = scores[i], scores[i + 1]
        if a["priority_tier"] == b["priority_tier"]:
            assert a["activation"] >= b["activation"]
            if a["activation"] == b["activation"]:
                assert a["specificity"] >= b["specificity"]


def test_step5a_is_primary_field_preserved_for_backward_compatibility():
    saju = _sample_saju()
    fact = _sample_facts(saju)[1]
    result = build_domain_pipeline(saju, fact, age=23, gender="female")
    for d in result["domain_scores"]:
        assert d["is_primary"] is True  # 기존 필드 의미 그대로 유지(activation>=3)
        assert d["priority_tier"] in ("primary", "secondary", "supporting")


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
