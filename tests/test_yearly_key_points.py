"""총운은 월별 사건 서술 대신 영역 세 장의 핵심 포인트를 낸다."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from domains.yearly.key_points import AREAS, build_key_points
from domains.yearly.service import generate_yearly

_ROOT = Path(__file__).resolve().parents[1]
_OVERALL = _ROOT / "domains" / "yearly" / "data" / "yearly_overall_db.json"
_TITLES = {area.title for area in AREAS}
_BANNED = ("반드시", "무조건", "손실을 피", "투자하면", "여러분", "십신", "신강", "신약", "용신")
_MONTH = re.compile(r"(?:[1-9]|1[0-2])월|몇 월")


def _points(entry, seed):
    return build_key_points(
        one_line=str(entry.get("one_line") or ""),
        keywords=entry.get("keywords") or [],
        overall_flow=str(entry.get("overall_flow") or ""),
        seed=seed,
        avoid=(
            str(entry.get("overall_flow") or ""),
            str(entry.get("first_half") or ""),
            str(entry.get("second_half") or ""),
            str(entry.get("advice") or ""),
            str(entry.get("cheat_key") or ""),
            str(entry.get("trap_warning") or ""),
            str(entry.get("opportunity_month") or ""),
            str(entry.get("caution_month") or ""),
        ),
    )


def test_every_overall_chart_gets_three_distinct_cards():
    data = json.loads(_OVERALL.read_text(encoding="utf-8"))
    seen_sets = set()
    for seed, entry in data.items():
        if not isinstance(entry, dict):
            continue
        points = _points(entry, seed)
        assert [item["index"] for item in points] == ["01", "02", "03"]
        areas = [item["area"] for item in points]
        assert len(set(areas)) == 3
        assert set(areas) <= _TITLES
        seen_sets.add(tuple(areas))
        bodies = [item["body"] for item in points]
        assert len(set(bodies)) == 3
        for left_index, left in enumerate(bodies):
            assert not _MONTH.search(left)
            assert all(word not in left for word in _BANNED)
            for right in bodies[left_index + 1:]:
                assert SequenceMatcher(None, left, right).ratio() < 0.55
        others = "\n".join(
            str(entry.get(name) or "")
            for name in (
                "overall_flow", "first_half", "second_half", "advice",
                "cheat_key", "trap_warning", "opportunity_month", "caution_month",
            )
        )
        for body in bodies:
            core = body.split("가까워요. ", 1)[-1]
            assert core[:18] not in others
    assert len(seen_sets) > 1


def test_theme_changes_which_areas_are_chosen():
    calm = build_key_points(
        one_line="익숙한 길 위에서 내면이 깊어지는 잔잔한 해",
        keywords=["잔잔한 일상", "익숙한 편안함", "깊어지는 내면"],
        overall_flow="일상과 내면, 생활의 속도를 낮추는 해",
        seed="calm",
    )
    leap = build_key_points(
        one_line="뜨거운 열정과 끈기로 내 무대를 넓히는 해",
        keywords=["열정", "성취", "도약"],
        overall_flow="도전과 도약, 새로운 시작이 일에 실리는 해",
        seed="leap",
    )
    assert {item["area"] for item in calm} != {item["area"] for item in leap}
    assert "생활과 환경" in {item["area"] for item in calm}
    assert "커리어와 도전" in {item["area"] for item in leap}


def test_overall_response_hides_month_stories_and_keeps_scores():
    data, _ = generate_yearly(
        "overall", 1994, 7, 12, 14, 30, gender="female", target_year=2026,
    )
    assert data["monthly_flow"] == []
    assert len(data["monthly"]) == 12
    assert len(data["best_months"]) == 3
    assert len(data["caution_months"]) == 3
    assert [item["index"] for item in data["key_points"]] == ["01", "02", "03"]
    wealth, _ = generate_yearly(
        "wealth", 1994, 7, 12, 14, 30, gender="female", target_year=2026,
    )
    assert "key_points" not in wealth
    assert "monthly_flow" not in wealth
