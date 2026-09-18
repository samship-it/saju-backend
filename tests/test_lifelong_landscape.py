"""평생운세 섹션1 '사주적 풍경' — AI/DB 없이 실시간 오행 조합인지 검증.

reason(풍경 근거) 서술과, daily풍 단발성 행동 팁이 섞이지 않는지도 함께 검증한다.
개운법(TIP)은 섹션2(core_nature)로 이동했으므로 build_tip() 으로 별도 검증한다.
"""
import datetime

import pytest

from core.saju_base import calculate_saju
from domains.lifelong.landscape import SUBJECT_IMAGE, ENV_IMAGE, TIP, build_landscape, build_reason, build_tip
from domains.lifelong.service import analyze_lifelong_fortune

ELEMENTS = ["목", "화", "토", "금", "수"]

# daily woon_modifier 쪽에서 쓰던 "오늘 하루" 단발성 행동 지시 어휘 — 평생운세 TIP엔
# 절대 섞이면 안 된다(예전에 "책상 정리처럼 작은 정돈부터" 같은 문구가 섞여 있었음).
_DAILY_STYLE_PHRASES = ["책상 정리", "오늘 하루", "오늘은", "당장"]


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
    assert "tip" not in out
    assert build_tip(saju) == TIP["수"]


def test_build_landscape_no_yongsin_falls_back():
    saju = {"day_master_elem": "금", "strength": {"elem_power": {"금": 1.0}, "yongsin": []}}
    assert build_tip(saju) == "지금의 균형을 오래도록 잘 유지해 나가는 것만으로도 충분합니다."


def test_tip_text_has_no_daily_style_action_phrases():
    for elem, text in TIP.items():
        for phrase in _DAILY_STYLE_PHRASES:
            assert phrase not in text, f"{elem} 팁에 daily풍 문구 잔존: {phrase!r}"


def test_reason_cites_month_season_and_env_elem():
    saju = {
        "day_master": "壬", "day_master_elem": "수",
        "month_ganji": "丁巳", "time_ganji": "丁未", "birth_time_known": True,
    }
    reason = build_reason(saju, env_elem="화", yongsin=["금", "수"])
    assert reason is not None
    assert "壬" in reason and "수" in reason
    assert "여름" in reason  # 巳월 = 여름
    assert "미" in reason  # 시지(未) 한글 표기
    assert "화" in reason  # env_elem
    assert "금·수" in reason  # yongsin 결합 표기


def test_reason_skips_hour_sentence_when_birth_time_unknown():
    saju = {
        "day_master": "壬", "day_master_elem": "수",
        "month_ganji": "丁巳", "time_ganji": "", "birth_time_known": False,
    }
    reason = build_reason(saju, env_elem="화", yongsin=["금"])
    assert reason is not None
    assert "시(時)생" not in reason


def test_build_landscape_includes_reason():
    saju = {
        "day_master": "壬", "day_master_elem": "수",
        "month_ganji": "丁巳", "time_ganji": "丁未", "birth_time_known": True,
        "strength": {"elem_power": {"목": 1.1, "화": 3.1, "토": 0.8, "금": 0.3, "수": 2.7}, "yongsin": ["금", "수"]},
    }
    out = build_landscape(saju)
    assert out["reason"]
    assert "여름" in out["reason"]


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
        assert build_tip(saju) == TIP[out["yongsin"][0]]


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
    assert landscape["scene"] and landscape["reason"]
    assert "tip" not in landscape


def test_analyze_lifelong_fortune_core_nature_has_strength_weakness_tip_order():
    data, _ = analyze_lifelong_fortune(1983, 5, 14, 14, 0, "female", False)
    core = data["data"]["core_nature"]
    assert list(core.keys()) == ["personality", "life_theme", "weaknesses", "tip"]
    assert core["personality"] and core["life_theme"] and core["weaknesses"] and core["tip"]
