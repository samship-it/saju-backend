"""평생운세 섹션1 '사주적 풍경' — AI/DB 없이 실시간 오행 조합인지 검증."""
import datetime

import pytest

from core.saju_base import calculate_saju
from domains.lifelong.landscape import SUBJECT_IMAGE, ENV_IMAGE, TIP, build_landscape
from domains.lifelong.service import analyze_lifelong_fortune

ELEMENTS = ["목", "화", "토", "금", "수"]


def test_tables_cover_all_five_elements():
    assert set(SUBJECT_IMAGE.keys()) == set(ELEMENTS)
    assert set(ENV_IMAGE.keys()) == set(ELEMENTS)
    assert set(TIP.keys()) == set(ELEMENTS)


def test_build_landscape_uses_day_master_and_strongest_elem_power():
    saju = {
        "day_master_elem": "목",
        "strength": {"elem_power": {"목": 1.0, "화": 3.0, "토": 0.5, "금": 0.2, "수": 0.8}, "yongsin": ["수"]},
    }
    out = build_landscape(saju)
    assert out["day_master_elem"] == "목"
    assert out["env_elem"] == "화"  # elem_power 최댓값
    assert out["scene"] == f"{ENV_IMAGE['화']} 아래 {SUBJECT_IMAGE['목']}"
    assert out["tip"] == TIP["수"]


def test_build_landscape_no_yongsin_falls_back():
    saju = {"day_master_elem": "금", "strength": {"elem_power": {"금": 1.0}, "yongsin": []}}
    out = build_landscape(saju)
    assert out["tip"] == "지금의 균형을 잘 유지하는 것만으로도 충분해요."


@pytest.mark.parametrize(
    "birth",
    [
        dict(year=1983, month=5, day=14, hour=14, minute=0, gender="female", is_lunar=False),
        dict(year=1990, month=1, day=1, hour=8, minute=0, gender="male", is_lunar=False),
        dict(year=2000, month=8, day=7, hour=3, minute=0, gender="female", is_lunar=False),
    ],
)
def test_full_pipeline_landscape_is_internally_consistent(birth):
    saju = calculate_saju(**birth, target_date=datetime.date.today())
    out = build_landscape(saju)
    assert SUBJECT_IMAGE[out["day_master_elem"]] in out["scene"]
    assert ENV_IMAGE[out["env_elem"]] in out["scene"]
    if out["yongsin"]:
        assert out["tip"] == TIP[out["yongsin"][0]]


def test_three_different_people_get_different_landscapes():
    births = [
        dict(year=1983, month=5, day=14, hour=14, minute=0, gender="female", is_lunar=False),
        dict(year=1990, month=1, day=1, hour=8, minute=0, gender="male", is_lunar=False),
        dict(year=2000, month=8, day=7, hour=3, minute=0, gender="female", is_lunar=False),
    ]
    scenes = set()
    for b in births:
        saju = calculate_saju(**b, target_date=datetime.date.today())
        scenes.add(build_landscape(saju)["scene"])
    assert len(scenes) == 3  # 셋 다 달라야 함


def test_analyze_lifelong_fortune_includes_landscape():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False)
    landscape = data["data"]["landscape"]
    assert landscape["scene"] and landscape["tip"]
