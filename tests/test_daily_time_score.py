"""시간 모름 점수 정규화와 점수 구간별 본문.

태어난 시를 모르면 시주를 넣지 않고, 년·월·일 여섯 글자가 균형에서 벗어난 정도만
점수 보정에 남긴다. 최종 점수 구간이 오늘 일진 칸과 다르면 같은 일주의 가까운 칸 본문을 쓴다.
"""
import datetime

from core.saju_base import calculate_saju
from domains.daily.service import generate_daily_fortune

DATE = datetime.date(2026, 10, 14)


def _read(year, month, day, hour, gender="female"):
    saju = calculate_saju(year, month, day, hour, 0, gender=gender, target_date=DATE)
    fortune, is_fallback = generate_daily_fortune(
        saju, love_status="single", job_status="employee"
    )
    return saju, fortune, is_fallback


def test_balanced_three_pillars_do_not_jump_away_from_noon():
    noon_chart, noon, _ = _read(1990, 3, 15, 12, "male")
    unknown, fortune, is_fallback = _read(1990, 3, 15, None, "male")
    assert unknown["birth_time_known"] is False
    assert unknown["time_ganji"] == ""
    assert sum(unknown["five_elements"].values()) == 6
    assert "polarity_scale" not in unknown["strength"]
    assert fortune["overall_score"] == noon["overall_score"] == 65
    assert fortune["woon_score_delta"] == 0
    assert fortune["summary"]["overall"] == noon["summary"]["overall"]
    assert is_fallback is False
    assert noon_chart["birth_time_known"] is True


def test_unknown_hour_delta_stays_inside_the_six_char_ratio():
    unknown, fortune, is_fallback = _read(2000, 4, 14, None)
    _, noon, _ = _read(2000, 4, 14, 12)
    assert unknown["birth_time_known"] is False
    assert sum(unknown["five_elements"].values()) == 6
    assert abs(fortune["woon_score_delta"]) <= 12
    assert abs(fortune["overall_score"] - noon["overall_score"]) <= 20
    assert fortune["score_band"] != noon["score_band"]
    assert fortune["summary"]["overall"] != noon["summary"]["overall"]
    assert fortune["summary"]["money"] != noon["summary"]["money"]
    assert is_fallback is False


def test_bad_and_good_score_bands_use_different_text():
    _, noon, _ = _read(1994, 10, 25, 12)
    unknown, fortune, _ = _read(1994, 10, 25, None)
    assert noon["overall_score"] == 29
    assert noon["woon_score_delta"] == -31
    assert fortune["overall_score"] >= 50
    assert abs(fortune["woon_score_delta"]) <= 12
    assert unknown["strength"]["verdict"] == "중화"
    assert noon["score_band"] != fortune["score_band"]
    assert noon["summary"]["overall"] != fortune["summary"]["overall"]
    assert noon["headline"] != fortune["headline"]
