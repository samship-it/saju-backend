"""연간 총운의 월별 설명은 기회의 달·주의의 달과 맞추고, 문장을 복사하지 않는다."""
import datetime
from difflib import SequenceMatcher

from core.saju_base import calculate_saju
from domains.yearly.service import (
    _MONTH_TAG_NARRATIVES,
    _best_caution,
    _monthly_flow,
    _monthly_strength,
)


def _row(month_index, solar, strength, tag="재성"):
    return {
        "month_index": month_index,
        "solar_month_approx": solar,
        "ganji": "甲子",
        "strength": strength,
        "tag": tag,
    }


def test_flat_scores_do_not_invent_a_quiet_month():
    monthly = [_row(i, i, 60, "식상") for i in range(1, 13)]
    flow = _monthly_flow(monthly)
    assert flow == []
    assert _best_caution(monthly)[0] == ["1월", "2월", "3월"]
    assert _best_caution(monthly)[1] == ["10월", "11월", "12월"]


def test_only_months_separated_from_the_rest_are_described():
    strengths = [80, 80, 70, 70, 60, 60, 60, 60, 55, 50, 50, 40]
    monthly = [_row(i + 1, i + 1, strengths[i], "인성" if i < 3 else "관성") for i in range(12)]
    flow = _monthly_flow(monthly)
    assert [item["month"] for item in flow] == [1, 2, 3, 10, 11, 12]
    assert [item["band"] for item in flow] == ["best", "best", "best", "caution", "caution", "caution"]
    assert [item["narrative"] for item in flow[:3]] == list(_MONTH_TAG_NARRATIVES[("인성", "best")])
    assert flow[-1]["narrative"] == _MONTH_TAG_NARRATIVES[("관성", "caution")][2]
    assert all("기복" not in item["narrative"] for item in flow)
    assert len(flow) < 12
    assert len({item["narrative"] for item in flow}) == len(flow)


def test_real_chart_keeps_the_score_and_skips_undescribed_months():
    saju = calculate_saju(1994, 7, 12, 14, 30, gender="female", target_date=datetime.date(2026, 1, 1))
    monthly = _monthly_strength(saju, 2026)
    again = _monthly_strength(saju, 2026)
    assert [row["strength"] for row in monthly] == [row["strength"] for row in again]
    assert len(monthly) == 12
    flow = _monthly_flow(monthly)
    described = {item["month"] for item in flow}
    assert len(described) == len(flow)
    assert len(flow) <= 6
    assert all(item["band"] in ("best", "caution") for item in flow)
    assert all("기복" not in item["narrative"] for item in flow)
    assert len({item["narrative"] for item in flow}) == len(flow)
    by_band = {
        "best": {line for (tag, band), lines in _MONTH_TAG_NARRATIVES.items() if band == "best" for line in lines},
        "caution": {line for (tag, band), lines in _MONTH_TAG_NARRATIVES.items() if band == "caution" for line in lines},
    }
    for item in flow:
        assert item["narrative"] in by_band[item["band"]]
    best, caution = _best_caution(monthly)
    assert len(best) == 3 and len(caution) == 3
    if len({row["strength"] for row in monthly}) > 1:
        chips = {int(label[:-1]) for label in best + caution}
        assert described == chips


def test_month_lines_are_not_copied_across_the_catalog():
    lines = [line for options in _MONTH_TAG_NARRATIVES.values() for line in options]
    assert len(lines) == len(set(lines))
    assert all(len(options) >= 3 for options in _MONTH_TAG_NARRATIVES.values())
    banned = ("반드시 성공", "손실을 피할", "반드시 이룬", "무조건")
    assert all(word not in line for line in lines for word in banned)
    for left_index, left in enumerate(lines):
        for right in lines[left_index + 1:]:
            assert SequenceMatcher(None, left, right).ratio() < 0.72
