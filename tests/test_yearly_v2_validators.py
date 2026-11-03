"""yearly(연간 운세) v2 검증 로직 — 성향-적성 그라운딩 + 순번/서수 이중 검증기.

실제 Gemini 호출 없음. generate_content_db 의 순수 함수만 테스트.
"""
from scripts.generate_content_db import (
    _YEARLY_PERSONALITY_GROUNDED,
    _yearly_v2_item_block,
    _yearly_v2_valid,
    has_cycle_repetition_claim,
    has_relative_year_comparison,
    verdict_score_consistent,
)


# ------------------------------------------------------------------ has_relative_year_comparison
def test_has_relative_year_comparison_catches_real_comparison_claims():
    assert has_relative_year_comparison("들어오는 돈의 규모가 작년보다 훨씬 커집니다")
    assert has_relative_year_comparison("재작년에 비해 훨씬 단단해진 상태")
    assert has_relative_year_comparison("지난해와 비슷한 흐름이 이어져요")


def test_has_relative_year_comparison_allows_forward_looking_mentions():
    """'내년을 준비' 류의 단순 미래 지향 언급은 검증 불가능한 '비교 주장'이 아니라 통과."""
    assert not has_relative_year_comparison("연말에는 내년을 준비하는 시간을 가집니다")
    assert not has_relative_year_comparison("다음 해를 기약하며 마무리합니다")
    assert not has_relative_year_comparison("상반기와 하반기의 결이 다릅니다")


# ------------------------------------------------------------------ has_cycle_repetition_claim
def test_has_cycle_repetition_claim_catches_repetition_count_claims():
    assert has_cycle_repetition_claim("이 기운을 두 번째로 맞이하는 해입니다")
    assert has_cycle_repetition_claim("환갑을 맞아 다시 돌아온 기운이에요")
    assert has_cycle_repetition_claim("육십갑자가 한 바퀴 돌아 갑자를 다시 만납니다")


def test_has_cycle_repetition_claim_allows_normal_year_language():
    assert not has_cycle_repetition_claim("올해는 새로운 시작의 해입니다")
    assert not has_cycle_repetition_claim("처음 도전하는 분야라 설레는 마음이 큽니다")


# ------------------------------------------------------------------ verdict_score_consistent
def test_verdict_score_consistent_flags_backwards_verdict():
    assert verdict_score_consistent(
        {"stay_vs_move": {"stay_score": 5, "move_score": 4, "verdict": "이직 추천"}}
    ) is False
    assert verdict_score_consistent(
        {"stay_vs_move": {"stay_score": 2, "move_score": 4, "verdict": "이직 추천"}}
    ) is True
    assert verdict_score_consistent(
        {"stay_vs_move": {"stay_score": 4, "move_score": 2, "verdict": "유지 권장"}}
    ) is True


def test_verdict_score_consistent_ignores_ties_and_missing_field():
    assert verdict_score_consistent(
        {"stay_vs_move": {"stay_score": 3, "move_score": 3, "verdict": "이직 추천"}}
    ) is True
    assert verdict_score_consistent({}) is True
    assert verdict_score_consistent({"stay_vs_move": {}}) is True


# ------------------------------------------------------------------ _yearly_v2_item_block 그라운딩
def test_yearly_v2_item_block_injects_personality_grounding_for_work_categories():
    for category in _YEARLY_PERSONALITY_GROUNDED:
        block = _yearly_v2_item_block("己卯_丙午", category)
        assert "이미 확정된 '타고난 성향/적성'" in block
        assert "기질 축" in block


def test_yearly_v2_item_block_skips_grounding_for_non_work_categories():
    block = _yearly_v2_item_block("己卯_丙午", "travel")
    assert "이미 확정된 '타고난 성향/적성'" not in block


# ------------------------------------------------------------------ _yearly_v2_valid 통합
_BASE_CAREER_ENTRY = {
    "one_line": "안정 속에서 새 기회를 저울질하는 한 해",
    "keywords": ["저울질"],
    "concept_object": "서류가방",
    "overall_flow": "x" * 220,
    "job_change_eval": "x" * 150,
    "opportunity_style": "x" * 120,
    "ideal_environment": "x" * 120,
    "timing_flow": "x" * 100,
    "stay_vs_move": {
        "stay_score": 4, "move_score": 2,
        "stay_summary": "지금 자리에서 안정적으로 경력을 쌓을 수 있어요.",
        "move_summary": "이직하면 새 환경 적응에 시간이 걸릴 수 있어요.",
        "verdict": "유지 권장",
    },
}


def test_yearly_v2_valid_rejects_verdict_score_contradiction():
    bad = dict(_BASE_CAREER_ENTRY)
    bad["stay_vs_move"] = dict(_BASE_CAREER_ENTRY["stay_vs_move"], verdict="이직 추천")
    assert _yearly_v2_valid("career_change", bad) is False
    assert _yearly_v2_valid("career_change", _BASE_CAREER_ENTRY) is True


def test_yearly_v2_valid_rejects_relative_year_comparison_in_text_field():
    bad = dict(_BASE_CAREER_ENTRY)
    bad["overall_flow"] = "올해는 이런저런 흐름이 이어집니다. " * 10 + "업무량이 작년보다 훨씬 늘어납니다."
    assert _yearly_v2_valid("career_change", bad) is False


def test_yearly_v2_valid_rejects_cycle_repetition_claim_in_compare_field():
    bad = dict(_BASE_CAREER_ENTRY)
    bad["stay_vs_move"] = dict(
        _BASE_CAREER_ENTRY["stay_vs_move"],
        stay_summary="이 기운을 두 번째로 맞이하는 만큼 안정적으로 자리를 지키는 편이 유리해요.",
    )
    assert _yearly_v2_valid("career_change", bad) is False
