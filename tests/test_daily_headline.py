"""오늘의 운세 한줄평(headline) 가드레일 + 점수대별 Fallback 매핑 검증.

LLM 이 "안녕하세요.", "와!" 같은 무의미한 한줄평을 반환하는 경우를 막기 위한
검증 가드레일(is_valid_headline)과, 검증 실패 시 100% 대체되는 점수대별
기본 문구(daily_headline_fallback / DAILY_HEADLINE_BANDS)를 검증한다.
"""
import pytest

from core.constants import DAILY_HEADLINE_BANDS, daily_headline_fallback
from shared.text_format import is_valid_headline
from domains.daily.service import _shape


# ------------------------------------------------------------------ 점수대별 Fallback 매핑
EXPECTED_BANDS = [
    (0, 9, "내일은 내일의 태양이 뜬다"),
    (10, 19, "오늘은 에너지 절약 모드"),
    (20, 29, "괜찮아, 잘될 거야"),
    (30, 39, "천천히, 나답게"),
    (40, 49, "중간은 반 이상 간다"),
    (50, 59, "이 정도면 선방"),
    (60, 69, "작은 행운이 오는 하루가 될 거예요"),
    (70, 79, "바라던 좋은 하루"),
    (80, 89, "나 이런 사람이야~~"),
    (90, 100, "오늘의 주인공은 바로 나"),
]


def test_bands_table_matches_spec():
    assert DAILY_HEADLINE_BANDS == EXPECTED_BANDS


@pytest.mark.parametrize("lo,hi,text", EXPECTED_BANDS)
def test_fallback_returns_exact_text_at_band_boundaries(lo, hi, text):
    assert daily_headline_fallback(lo) == text
    assert daily_headline_fallback(hi) == text
    mid = (lo + hi) // 2
    assert daily_headline_fallback(mid) == text


def test_fallback_clamps_out_of_range_scores():
    assert daily_headline_fallback(-10) == "내일은 내일의 태양이 뜬다"
    assert daily_headline_fallback(150) == "오늘의 주인공은 바로 나"


# ------------------------------------------------------------------ 유효성 검증 가드레일
VALID_HEADLINES = [
    "오늘은 뜻밖의 좋은 소식이 찾아올 거예요.",
    "차분하게 정리하면 흐름이 매끄러워지는 하루입니다.",
    "작은 선택이 큰 흐름을 바꾸는 날이에요.",
]

INVALID_TOO_SHORT = ["좋아요", "괜찮음", "네", ""]

INVALID_GREETING_OR_INTERJECTION = [
    "안녕하세요.",
    "안녕하세요",
    "반갑습니다.",
    "와!",
    "아...",
    "휴~",
    "음...",
]

INVALID_SPECIAL_CHARS_ONLY = ["!!!???", "~~~~~~~~~~", "...........", "★☆★☆★☆★☆"]

INVALID_INCOMPLETE_SENTENCE = [
    "오늘은 뭔가 좋은 일이 생기고",
    "돈 문제는 조심해야 하지만",
    "사람들과의 관계에서 그런데",
]


@pytest.mark.parametrize("text", VALID_HEADLINES)
def test_valid_headline_passes(text):
    assert is_valid_headline(text) is True


@pytest.mark.parametrize("text", INVALID_TOO_SHORT)
def test_too_short_fails(text):
    assert is_valid_headline(text) is False


@pytest.mark.parametrize("text", INVALID_GREETING_OR_INTERJECTION)
def test_greeting_or_interjection_only_fails(text):
    assert is_valid_headline(text) is False


@pytest.mark.parametrize("text", INVALID_SPECIAL_CHARS_ONLY)
def test_special_chars_only_fails(text):
    assert is_valid_headline(text) is False


@pytest.mark.parametrize("text", INVALID_INCOMPLETE_SENTENCE)
def test_incomplete_sentence_fails(text):
    assert is_valid_headline(text) is False


# ------------------------------------------------------------------ 파이프라인(service._shape) 통합
# social 필드는 saju_data(십신군 × 지지관계)로 별도 계산되므로, _shape 호출 시 최소한의
# saju_data 더미를 함께 넘긴다(day_master/day_branch/today_ganji 없으면 SOCIAL_FALLBACK).
_SAJU_DATA = {"day_master": "壬", "day_branch": "寅", "today_ganji": {"day": "戊辰"}}

# |score_delta| < 임계값이라 woon 기반 오버라이드가 발동하지 않는, 이 파일 테스트들의 기본값.
_NO_WOON_OVERRIDE = {"state_label": "", "score_delta": 0}


def _ai(overall_score, headline=None, overall_summary="정상적인 요약 문장입니다."):
    return {
        "overall_score": overall_score,
        "money_score": overall_score,
        "love_score": overall_score,
        "work_study_score": overall_score,
        **({"headline": headline} if headline is not None else {}),
        "summary": {
            "overall": overall_summary,
            "money": "본문",
            "love_single": "본문",
            "love_couple": "본문",
            "work_study": "본문",
        },
        "keywords": ["a", "b", "c"],
        "recommended_action": "오늘 해볼 행동입니다.",
    }


def test_shape_uses_valid_llm_headline_as_is():
    ai = _ai(75, headline="오늘은 마무리에 강한 하루가 될 거예요.")
    out = _shape(ai, _SAJU_DATA, _NO_WOON_OVERRIDE)
    assert out["headline"] == "오늘은 마무리에 강한 하루가 될 거예요."


@pytest.mark.parametrize("lo,hi,text", EXPECTED_BANDS)
def test_shape_falls_back_to_band_text_when_headline_and_summary_invalid(lo, hi, text):
    score = (lo + hi) // 2
    # headline 자체가 가드레일 실패("와!") + summary 첫 문장도 인사말이라 이중으로 무효.
    ai = _ai(score, headline="와!", overall_summary="안녕하세요. 오늘 하루도 힘내봐요.")
    out = _shape(ai, _SAJU_DATA, _NO_WOON_OVERRIDE)
    assert out["headline"] == text
    assert out["overall_score"] == score


def test_shape_extracts_first_sentence_when_headline_missing_but_summary_valid():
    ai = _ai(65, headline=None, overall_summary="차분하게 정리하면 흐름이 매끄러워지는 하루입니다. 그리고 이어지는 문장.")
    out = _shape(ai, _SAJU_DATA, _NO_WOON_OVERRIDE)
    assert out["headline"] == "차분하게 정리하면 흐름이 매끄러워지는 하루입니다."


# ------------------------------------------------------------------ woon_state 기반 headline 오버라이드
def test_shape_overrides_headline_when_delta_large_positive():
    ai = _ai(75, headline="원본 static headline 문장입니다.")
    out = _shape(ai, _SAJU_DATA, {"state_label": "명예/승진운", "score_delta": 12})
    assert out["headline"] == "오늘의 핵심 기운: 명예/승진운"


def test_shape_overrides_headline_when_delta_large_negative():
    ai = _ai(75, headline="원본 static headline 문장입니다.")
    out = _shape(ai, _SAJU_DATA, {"state_label": "지출/구설 주의", "score_delta": -15})
    assert out["headline"] == "오늘의 핵심 기운: 지출/구설 주의"


def test_shape_keeps_original_headline_when_delta_below_threshold():
    ai = _ai(75, headline="원본 static headline 문장입니다.")
    out = _shape(ai, _SAJU_DATA, {"state_label": "무난한 흐름", "score_delta": 9})
    assert out["headline"] == "원본 static headline 문장입니다."


def test_headline_threshold_is_exactly_ten():
    from domains.daily.service import _headline

    assert _headline({}, 70, "지출/구설 주의", 10) == "오늘의 핵심 기운: 지출/구설 주의"
    assert _headline({}, 70, "지출/구설 주의", -10) == "오늘의 핵심 기운: 지출/구설 주의"
    original = "오늘은 차분하게 하루를 마무리하는 게 좋은 날이에요."
    assert _headline({"headline": original}, 70, "지출/구설 주의", 9) == original
