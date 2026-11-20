"""혼자 보는 결혼운의 성향과 배우자 운.

기존 본문·점수·사유 라벨은 그대로이고, 두 문단만 원국으로 조립한다.
시기 심층 분석은 응답에 넣지 않는다.
"""
from domains.relationship import content_db
from domains.relationship.service import analyze_marriage
from shared.text_format import paragraphize

_KEYS = ("marriage_disposition", "spouse_fortune")
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


_PLACE = ("기둥", "글자", "위쪽", "아래쪽", "태어난 해", "태어난 달", "태어난 날", "태어난 시각")


def _sentences(text):
    return {part.strip() for part in text.replace("\n", " ").split(".") if part.strip()}


def test_jeongsa_female_depth_uses_chart_facts_without_jargon():
    data, _ = _solo()
    text = _new_text(data)
    for key in _KEYS:
        assert data[key].strip()
    disposition = data["marriage_disposition"]
    spouse = data["spouse_fortune"]
    assert "책임감과 현실적인 조건도 중요하게 생각합니다" in disposition
    assert "서로 맡은 역할을 존중하고 안정적인 생활을 꾸려가기를 바랍니다" in disposition
    assert "타협하는 데 시간이 걸릴 수 있습니다" in disposition
    assert "자신의 감정과 생각을 분명하게 표현하는 편" in spouse
    assert "현실적인 문제를 차분하게 해결하는 성향이 잘 어울립니다" in spouse
    assert "행동으로 신뢰를 보여주며" in spouse
    assert "생활 방식과 독립성을 존중하는 사람" in spouse
    assert not _sentences(disposition) & _sentences(spouse)
    for word in _PLACE:
        assert word not in disposition
        assert word not in spouse
    assert "timing_depth" not in data
    for word in _BANNED:
        assert word not in text


def test_same_birth_male_is_not_the_female_text():
    female, _ = _solo(gender="female")
    male, _ = _solo(gender="male")
    assert female["marriage_disposition"] != male["marriage_disposition"]
    assert "timing_depth" not in female
    assert "timing_depth" not in male
    assert male["overall_score"] == 88
    assert male["best_year"] == 2028
    assert "매일의 생활이 서로에게 편한지" in male["marriage_disposition"]
    assert "책임감과 현실적인 조건" not in male["marriage_disposition"]
    assert "책임과 명분" not in _new_text(male)
    assert "2028년" not in male["spouse_fortune"]
    assert male["spouse_fortune"] != female["spouse_fortune"]
    assert "계획과 현실적인 정리는 상대가 맡아 주면" in male["spouse_fortune"]
    for word in _BANNED:
        assert word not in _new_text(male)


def test_unknown_birth_time_does_not_use_the_hour_pillar():
    data, _ = _solo(hour=None, minute=None)
    text = _new_text(data)
    assert "시각" not in text
    assert "timing_depth" not in data
    assert data["overall_score"] == 78
    assert data["best_year"] == 2033
    assert "거슬립니다" not in data["marriage_disposition"]


def test_couple_joint_table_uses_the_lower_score_for_five_years():
    person = {
        "year": 2002, "month": 7, "day": 8, "hour": 14, "minute": 0,
        "gender": "female", "is_lunar": False, "name": "새하",
    }
    partner = {
        "year": 1983, "month": 12, "day": 15, "hour": 10, "minute": 0,
        "gender": "male", "is_lunar": False, "name": "민경",
    }
    data, _ = analyze_marriage(person, partner, 2026, "2026-11-20")
    assert data["overall_score"] == 70
    assert data["self_name"] == "새하"
    assert data["partner_name"] == "민경"
    assert data["joint_years"] == [
        {"year": 2026, "self_score": 56, "partner_score": 56, "joint_score": 56},
        {"year": 2027, "self_score": 36, "partner_score": 36, "joint_score": 36},
        {"year": 2028, "self_score": 58, "partner_score": 74, "joint_score": 58},
        {"year": 2029, "self_score": 70, "partner_score": 86, "joint_score": 70},
        {"year": 2030, "self_score": 58, "partner_score": 74, "joint_score": 58},
    ]
    assert data["joint_best_year"] == 2029
    assert data["overall_score"] == next(
        row["joint_score"] for row in data["joint_years"] if row["year"] == data["joint_best_year"]
    )
    assert "joint_years" not in analyze_marriage(person, None, 2026, "2026-11-20")[0]


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
        assert data["marriage_disposition"] != data["spouse_fortune"]
        assert not _sentences(data["marriage_disposition"]) & _sentences(data["spouse_fortune"])
        for word in _PLACE:
            assert word not in data["marriage_disposition"]
            assert word not in data["spouse_fortune"]
        for word in _BANNED:
            assert word not in text, (gender, year, word)
        if hour is None:
            assert "시각" not in text
