"""천간 십성 대분류가 이어지면 20년 묶음이다. 지지가 달라도 나누지 않는다."""
import json

from core.daewoon import mark_twenty_year_runs
from domains.daewoon.service import analyze_daewoon_period
from domains.daewoon.twenty_year import ARC_DB, ARC_DB_PATH, core_continues


def test_same_element_pair_bundles_and_leftover_stays_ten_years():
    facts = [
        {"step": 1, "sipsin_group": "비겁", "ganji": "甲寅"},
        {"step": 2, "sipsin_group": "비겁", "ganji": "乙卯"},
        {"step": 3, "sipsin_group": "비겁", "ganji": "甲寅"},
        {"step": 4, "sipsin_group": "재성", "ganji": "丙午"},
    ]
    mark_twenty_year_runs(facts)
    assert facts[0]["twenty_role"] == "front" and facts[0]["price_beans"] == 3
    assert facts[1]["twenty_role"] == "back" and facts[1]["badge_text"] == "비겁운이 20년 동안 이어져요"
    assert facts[2]["is_twenty_years"] is False
    assert facts[2]["price_beans"] == 2 and facts[2]["badge_text"] is None
    assert facts[3]["is_twenty_years"] is False


def test_same_stem_group_bundles_even_when_branch_element_differs():
    """을해와 갑술은 지지 오행이 달라도 비겁이 이어지면 20년·3콩이다."""
    facts = [
        {"step": 1, "sipsin_group": "비겁", "ganji": "乙亥"},
        {"step": 2, "sipsin_group": "비겁", "ganji": "甲戌"},
    ]
    mark_twenty_year_runs(facts)
    assert facts[0]["is_twenty_years"] is True and facts[0]["twenty_role"] == "front"
    assert facts[1]["is_twenty_years"] is True and facts[1]["twenty_role"] == "back"
    assert facts[0]["price_beans"] == facts[1]["price_beans"] == 3
    assert facts[0]["badge_text"] == "비겁운이 20년 동안 이어져요"


def test_eulhae_gapsul_share_one_bigyeop_story():
    """1975-02-18 10시 남성. 25세 을해와 35세 갑술은 지지가 달라도 비겁 20년이다."""
    first, _ = analyze_daewoon_period(1975, 2, 18, 10, 0, "male", False, target_age=25)
    second, _ = analyze_daewoon_period(1975, 2, 18, 10, 0, "male", False, target_age=35)
    assert first["data"]["age_range"] == [25, 34]
    assert second["data"]["age_range"] == [35, 44]
    story = first["data"]["twenty_year_story"]
    assert first["data"]["is_twenty_years"] is True and second["data"]["is_twenty_years"] is True
    assert first["data"]["price_beans"] == 3
    assert story["section_common"] == "20년의 공통 흐름"
    assert story["section_front"].startswith("첫 번째 10년")
    assert story["section_back"].startswith("두 번째 10년")
    assert story["front"] != story["back"]
    assert first["data"]["twenty_year_story"]["overview"] == second["data"]["twenty_year_story"]["overview"]


def test_wood_on_wood_decades_stay_one_twenty_year_story():
    """갑인·을묘는 천간과 지지가 모두 목이라 20년 한 묶음이다."""
    front, _ = analyze_daewoon_period(1977, 7, 8, 8, 0, "female", False, target_age=70)
    back, _ = analyze_daewoon_period(1977, 7, 8, 8, 0, "female", False, target_age=80)
    assert front["data"]["is_twenty_years"] is True and back["data"]["is_twenty_years"] is True
    assert front["data"]["price_beans"] == back["data"]["price_beans"] == 3
    assert front["data"]["badge_text"] == back["data"]["badge_text"]
    assert front["data"]["badge_text"].endswith("운이 20년 동안 이어져요")
    assert front["data"]["twenty_year_story"]["age_range"] == [70, 89]
    assert front["data"]["twenty_year_story"]["front"] != back["data"]["twenty_year_story"]["back"]


def test_1983_pyeongwan_jeonggwan_is_one_officer_story():
    """무오 편관과 기미 정관은 지지가 달라도 관성 20년이고, 각 10년 문장은 다르다."""
    front, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, target_age=8)
    story = front["data"]["twenty_year_story"]
    assert front["data"]["is_twenty_years"] is True
    assert front["data"]["price_beans"] == 3
    assert front["data"]["badge_text"] == "관성운이 20년 동안 이어져요"
    assert story["section_common"] == "20년의 공통 흐름"
    assert story["section_front"] == "첫 번째 10년 (편관운)"
    assert story["section_back"] == "두 번째 10년 (정관운)"
    assert "압박" in story["front"]
    assert "책임" in story["back"]
    assert story["front"] != story["back"]
    assert "편관" not in story["overview"]
    assert "정관" not in story["overview"]
    assert story["action_title"] == "이 20년을 잘 보내기 위한 행동 지침"
    assert "역할" in story["action_guide"]
    assert "자격" not in story["action_guide"]
    assert "소속의 이름" not in story["action_guide"]
    assert "관성" not in story["action_guide"]
    readings = [item.get("sentence") or "" for item in story["core_front"] + story["core_back"]]
    assert any(readings)
    for reading in readings:
        assert "천간" not in reading
        assert "구조가 나타납니다" not in reading
    assert story["tasks_title"] == "20년간 중요했던 일"
    assert story["core_mode"] == "split"
    assert story["core_front"] and story["core_back"]


def test_standalone_decade_stays_ten_years():
    # 1980-03-12 여성은 1번째 대운 천간이 원소 쌍의 끝이라 다음 대운과 그룹이 갈린다.
    data, _ = analyze_daewoon_period(1980, 3, 12, 8, 0, "female", False, target_age=30)
    phases = data["data"]["timeline_phases"]
    solo = next(phase for phase in phases if not phase["is_twenty_years"])
    opened, _ = analyze_daewoon_period(
        1980, 3, 12, 8, 0, "female", False, target_age=solo["age_range"][0],
    )
    body = opened["data"]
    assert body["is_twenty_years"] is False
    assert body["price_beans"] == 2
    assert body["badge_text"] is None
    assert body["twenty_year_story"] is None
    assert "이 20년은" not in body["decade_theme"]["sentence"]


def test_same_environment_and_domains_share_one_core():
    assert core_continues("합", "합", ("career", "wealth"), ("career", "wealth")) is True


def test_changed_environment_splits_core_areas():
    assert core_continues("충", "합", ("career",), ("career",)) is False
    assert core_continues("합", "합", ("career",), ("wealth",)) is False


def test_arc_db_file_matches_source():
    with open(ARC_DB_PATH, encoding="utf-8") as handle:
        stored = json.load(handle)
    assert stored == ARC_DB
