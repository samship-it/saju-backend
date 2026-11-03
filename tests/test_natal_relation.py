"""격국과 오행 합계가 같을 때만 공통 관계를 쓰고, 0.1 차이는 1위로 인정한다."""
from core.strength import analyze_gyeokguk, analyze_strength
from domains.daewoon.content import STUDY_GROWTH
from domains.daewoon.natal_relation import (
    agreed_natal_group,
    decade_relation,
    element_group_totals,
    relation_between,
    relation_sentence,
    scrub_smooth,
    unique_group_leader,
    without_smooth_clauses,
)
from domains.daewoon.pipeline import KEY_AREA_MIN_SCORE, build_domain_pipeline
from domains.daewoon.service import analyze_daewoon_period

_RESPONSE_KEYS = {
    "daewoon_header", "landscape_scene", "saju_relation", "summary", "keywords",
    "domain_analysis", "decade_theme", "timeline_phases", "decade_tasks",
    "action_title", "action_guide", "step", "age_range", "target_age", "target",
    "is_current_decade", "is_past_decade", "is_twenty_years", "price_beans",
    "badge_text", "twenty_year_story", "strength_verdict", "polarity", "domain_pipeline",
}
_SCORE_KEYS = {
    "domain", "label", "eligible", "life_stage", "activation", "is_primary", "source",
    "driving_sipsin", "driving_group", "interpretation_key", "specificity",
    "valence", "confidence", "drivers", "evidence", "manifestation", "sentence",
    "priority_tier",
}


def _chart(day_master, pillars):
    return {
        "day_master": day_master,
        "strength": analyze_strength(day_master, pillars, False),
        "gyeokguk": analyze_gyeokguk(day_master, pillars),
    }


def _gap(totals):
    ranked = sorted(totals.values(), reverse=True)
    return round(ranked[0] - ranked[1], 2)


def test_agreeing_geok_and_element_leader_uses_shared_relation():
    """壬子·甲寅·甲寅. 건록격과 비겁 1위가 같다."""
    pillars = {"year": "壬子", "month": "甲寅", "day": "甲寅"}
    saju = _chart("甲", pillars)
    totals = element_group_totals("甲", saju["strength"]["elem_power"])
    assert saju["gyeokguk"]["name"] == "건록격"
    assert agreed_natal_group(saju) == "비겁"
    assert totals["비겁"] > totals["인성"]
    assert _gap(totals) == 1.2
    assert decade_relation(saju, "관성") == "규제"
    text = relation_sentence("규제", "10년", "favorable")
    assert "바깥 기준이 올라섭니다" in text
    assert "순탄" not in text and "순하게" not in text
    assert "비겁" not in text and "신강" not in text


def test_disagreeing_geok_and_element_leader_picks_neither():
    """戊辰·庚申·甲午. 편관격이지만 오행 1위는 재성이다."""
    pillars = {"year": "戊辰", "month": "庚申", "day": "甲午"}
    saju = _chart("甲", pillars)
    totals = element_group_totals("甲", saju["strength"]["elem_power"])
    assert saju["gyeokguk"]["name"] == "편관격"
    assert unique_group_leader(totals) == "재성"
    assert agreed_natal_group(saju) is None
    assert decade_relation(saju, "재성") is None
    assert decade_relation(saju, "관성") is None


def test_one_tenth_lead_still_counts_as_unique_first():
    """庚申·戊辰·甲子. 재성 1.7, 관성 1.6. 0.1 컷으로 1위를 버리지 않는다."""
    pillars = {"year": "庚申", "month": "戊辰", "day": "甲子"}
    saju = _chart("甲", pillars)
    totals = element_group_totals("甲", saju["strength"]["elem_power"])
    assert saju["gyeokguk"]["sipsin"] == "편재"
    assert round(totals["재성"] - totals["관성"], 2) == 0.1
    assert unique_group_leader(totals) == "재성"
    assert agreed_natal_group(saju) == "재성"
    assert relation_between("재성", "관성") == "표출"
    assert decade_relation(saju, "관성") == "표출"


def test_tied_totals_have_no_leader():
    """庚申·丙巳·甲寅. 식상과 관성이 1.9로 같다."""
    pillars = {"year": "庚申", "month": "丙巳", "day": "甲寅"}
    saju = _chart("甲", pillars)
    totals = element_group_totals("甲", saju["strength"]["elem_power"])
    assert totals["식상"] == totals["관성"]
    assert unique_group_leader(totals) is None
    assert agreed_natal_group(saju) is None


def test_pressure_relation_does_not_keep_smooth_wording():
    """규제와 순탄·순하게는 같은 문장에 두지 않는다. 카드 키는 남긴다."""
    smooth = STUDY_GROWTH["정관"]["school_life"]["favorable"]
    assert "순탄하게" in smooth
    scrubbed = scrub_smooth({"study_growth": {"school_life": smooth, "exam_luck": "시험 범위가 또렷합니다."}})
    assert set(scrubbed["study_growth"]) == {"school_life", "exam_luck"}
    assert scrubbed["study_growth"]["exam_luck"] == "시험 범위가 또렷합니다."
    assert "순탄" not in scrubbed["study_growth"]["school_life"]
    assert "사건이 없" not in scrubbed["study_growth"]["school_life"]
    kept = without_smooth_clauses("성실한 태도가 인정받습니다. 조직 생활이 순탄하게 이어집니다.")
    assert kept == "성실한 태도가 인정받습니다."
    assert "순탄" not in kept
    sentence = relation_sentence("규제", "10년", "favorable")
    assert "버겁기만 한 것은 아니고" in sentence
    assert "순탄" not in sentence and "순하게" not in sentence


def test_real_chart_pressure_keeps_polarity_but_drops_smooth_tone():
    """1968-12-28 남성 45세. 비겁이 일치하고 정관 대운은 규제이며 극성은 favorable이다."""
    data, _ = analyze_daewoon_period(1968, 12, 28, 16, 0, "male", False, target_age=45)
    body = data["data"]
    assert body["polarity"] == "favorable"
    context = body["domain_pipeline"]["global_context"]
    assert "바깥 기준이 올라섭니다" in context
    assert "순탄" not in context and "순하게" not in context
    career = body["domain_analysis"]["career_or_study"]["core_change"]
    assert "순탄" not in career and "순하게" not in career


def test_existing_score_gate_and_response_keys_stay():
    data, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=8)
    body = data["data"]
    assert set(body.keys()) == _RESPONSE_KEYS
    scores = body["domain_pipeline"]["domain_scores"]
    for item in scores:
        assert set(item.keys()) == _SCORE_KEYS
        assert item["is_primary"] is (item["activation"] >= KEY_AREA_MIN_SCORE)
        assert item["activation"] >= KEY_AREA_MIN_SCORE
    assert body["is_twenty_years"] is True
    assert body["price_beans"] == 3
    assert body["badge_text"] == "관성운이 20년 동안 이어져요"
    story = body["twenty_year_story"]
    assert story["section_front"] == "첫 번째 10년 (편관운)"
    assert "압박" in story["front"]
    assert "책임" in story["back"]


def test_pipeline_activation_is_not_rewritten_by_relation_gate():
    """관계 문장은 서비스 문장만 바꾸고, 파이프라인 점수 함수는 그대로다."""
    from core.daewoon import daewoon_decade_count, daewoon_step_facts
    from core.saju_base import calculate_saju
    from domains.lifelong.life_periods import _step_covering_age

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, target_age=32)
    saju = calculate_saju(1990, 5, 15, 10, 0, "male", False)
    daewoon = saju.get("daewoon") or {}
    daewoon_num = daewoon.get("daewoon_num", 1)
    facts = daewoon_step_facts(
        saju.get("day_master", ""),
        saju.get("day_branch", ""),
        saju.get("month_ganji", ""),
        daewoon.get("direction") == "순행",
        count=daewoon_decade_count(daewoon_num),
    )
    step = _step_covering_age(facts, daewoon_num, 32)
    fact = next(item for item in facts if item["step"] == step)
    direct = build_domain_pipeline(saju, fact, 32, "male")
    served = data["data"]["domain_pipeline"]["domain_scores"]
    assert [(d["domain"], d["activation"], d["is_primary"]) for d in served] == [
        (d["domain"], d["activation"], d["is_primary"]) for d in direct["domain_scores"]
    ]
