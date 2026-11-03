"""혼자 보는 결혼운 뒤에 붙는 세 문단.

기존 본문·점수·사유 라벨은 그대로이고, 새 문단만 원국과 이미 계산된 연도 사유로 조립한다.
"""
from domains.relationship import content_db
from domains.relationship.service import analyze_marriage
from shared.text_format import paragraphize

_KEYS = ("marriage_disposition", "spouse_fortune", "timing_depth")
_BANNED = (
    "십신", "오행", "천간", "지지", "일간", "일지", "원국", "용신", "신강", "신약",
    "도화", "육합", "삼합", "배우자성", "정관", "편관", "정재", "편재", "재성", "관성",
    "비견", "식신", "식상", "식살", "세운", "대운", "부부 자리", "배우자 기운",
    "해의 아래", "달의 위", "반드시", "실패", "불운",
)


def _solo(gender="female", hour=14, minute=30, year=1996, month=5, day=20):
    person = {
        "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute, "gender": gender, "is_lunar": False,
    }
    data, is_fallback = analyze_marriage(person, None, 2026, "2026-11-02")
    return data, is_fallback


def _new_text(data):
    return "\n".join(data[key] for key in _KEYS)


def test_jeongsa_female_keeps_stored_prose_and_scores():
    data, is_fallback = _solo()
    stored = content_db.lookup("丁巳", None, "marriage")
    assert is_fallback is False
    for key in ("overall", "marriage_timing", "spouse_type", "prep_strategy"):
        assert data[key] == paragraphize(stored[key])
    assert data["headline"] == "인연을 매듭짓기에 더없이 좋은, 결혼운이 무르익은 흐름"
    assert data["best_year"] == 2033
    assert data["overall_score"] == 86
    assert [(row["year"], row["strength"]) for row in data["best_years"]] == [
        (2033, 86), (2032, 74), (2028, 72),
    ]
    assert data["best_years"][0]["reasons_ko"] == [
        "인연이 들어오는 기운이 강한 해",
        "배우자 자리가 활발하게 움직이는 해",
        "전반적으로 나에게 유리한 흐름의 해",
    ]


def test_jeongsa_female_depth_uses_chart_facts_without_jargon():
    data, _ = _solo()
    text = _new_text(data)
    for key in _KEYS:
        assert data[key].strip()
    assert "태어난 해의 기둥에서 아래쪽 글자" in data["marriage_disposition"]
    assert "태어난 달의 기둥에서 위쪽 글자" in data["marriage_disposition"]
    assert "태어난 시각의 기둥" in text
    assert "2033년은 86점입니다" in data["timing_depth"]
    assert "한 번만 더합니다" in data["timing_depth"]
    assert "확정된다는 뜻은 아닙니다" in data["timing_depth"]
    assert "나쁜 해로 본 것은 아닙니다" in data["timing_depth"]
    assert "어디서 만나는지를 알려 주지 않습니다" in data["spouse_fortune"]
    for word in _BANNED:
        assert word not in text


def test_same_birth_male_is_not_the_female_text():
    female, _ = _solo(gender="female")
    male, _ = _solo(gender="male")
    assert female["marriage_disposition"] != male["marriage_disposition"]
    assert female["timing_depth"] != male["timing_depth"]
    assert "2033년은 86점입니다" not in male["timing_depth"]
    assert "2028년은 88점입니다" in male["timing_depth"]
    assert "결혼이 어렵다는 뜻은 아닙니다" in male["marriage_disposition"]
    assert "책임과 명분" not in _new_text(male)
    assert "2028년, 2029년, 2030년과 2031년" in male["spouse_fortune"]
    for word in _BANNED:
        assert word not in _new_text(male)


def test_unknown_birth_time_does_not_use_the_hour_pillar():
    data, _ = _solo(hour=None, minute=None)
    text = _new_text(data)
    assert "시각" not in text
    assert "2033년은 78점입니다" in data["timing_depth"]
    assert "86점" not in data["timing_depth"]
    assert "거슬립니다" not in data["marriage_disposition"]


def test_couple_response_does_not_gain_the_solo_sections():
    person = {
        "year": 1996, "month": 5, "day": 20,
        "hour": 14, "minute": 30, "gender": "female", "is_lunar": False,
    }
    partner = {
        "year": 1994, "month": 1, "day": 2,
        "hour": 10, "minute": 0, "gender": "male", "is_lunar": False,
    }
    data, _ = analyze_marriage(person, partner, 2026, "2026-11-02")
    assert data["partner_exists"] is True
    assert data["overall"]
    for key in _KEYS:
        assert key not in data


def test_other_charts_stay_plain_and_skip_unknown_hour():
    samples = (
        ("female", 1988, 3, 12, 9),
        ("male", 1992, 11, 2, None),
        ("female", 2001, 7, 8, 21),
    )
    for gender, year, month, day, hour in samples:
        data, _ = _solo(gender=gender, hour=hour, minute=0, year=year, month=month, day=day)
        text = _new_text(data)
        assert data["overall"]
        for word in _BANNED:
            assert word not in text, (gender, year, word)
        if hour is None:
            assert "시각" not in text
