"""여행·취미 통합: 여섯 섹션 분배, 혼자/함께 모순 제거, 정적 조회."""
import inspect
import time

from fastapi.testclient import TestClient

import main
from domains.yearly.service import _cached_travel_hobby, generate_travel_hobby
from domains.yearly.travel_hobby import _COMPANY, _OPENING, assemble, read_axes

client = TestClient(main.app)

BANNED = (
    "십신", "용신", "희신", "기신", "신강", "신약", "역마", "식상",
    "원국", "세운", "오행", "배우자", "육합", "삼합",
)
FIELDS = (
    "symbol",
    "section_1_overall_flow",
    "section_2_travel_style",
    "section_3_recommended_spot",
    "section_4_matched_activity",
    "section_5_solo_vs_together",
    "section_6_final_reward",
)


def _travel():
    return {
        "one_line": "TLINE",
        "keywords": ["이동", "바람"],
        "concept_object": "지도",
        "overall_flow": "TFLOW",
        "travel_style": "TSTYLE",
        "travel_luck": "TLUCK",
        "recommended_spots": "TSPOT",
    }


def _hobby(solo="혼자 걷는 시간이 필요해요. 함께보다 혼자예요."):
    return {
        "one_line": "HLINE",
        "keywords": ["몰입"],
        "concept_object": "그림",
        "overall_flow": "HFLOW",
        "active_activities": "HACT",
        "solo_vs_group": solo,
        "benefits": "HGAIN",
    }


def test_rule_copy_has_no_technical_terms():
    blob = " ".join(_OPENING.values()) + " " + " ".join(_COMPANY.values())
    for term in BANNED:
        assert term not in blob


def test_fields_do_not_reuse_the_same_source_paragraph():
    moved = assemble(_travel(), _hobby(), move_high=True, play_high=False, company="solo", timing_months=["4월", "9월"])
    assert "TFLOW" in moved["section_1_overall_flow"]
    assert "HFLOW" not in moved["section_1_overall_flow"]
    assert "TSTYLE" in moved["section_2_travel_style"]
    assert "TSPOT" in moved["section_3_recommended_spot"]
    assert "TLUCK" not in moved["section_3_recommended_spot"]
    assert "4월" in moved["section_3_recommended_spot"]
    assert "HACT" in moved["section_4_matched_activity"]
    assert "HFLOW" not in moved["section_4_matched_activity"]
    assert "HGAIN" in moved["section_6_final_reward"]
    assert "TLUCK" in moved["section_6_final_reward"]
    assert moved["symbol"]["keywords"][0] == "#이동"
    assert moved["symbol"]["object"] == "지도"
    assert moved["symbol"]["headline"] == "TLINE"

    both = assemble(_travel(), _hobby(), move_high=True, play_high=True, company="either", timing_months=["5월"])
    assert "TFLOW" in both["section_1_overall_flow"]
    assert "HFLOW" in both["section_1_overall_flow"]
    assert "HFLOW" not in both["section_4_matched_activity"]

    stayed = assemble(_travel(), _hobby(), move_high=False, play_high=True, company="together", timing_months=["6월"])
    assert "HFLOW" in stayed["section_1_overall_flow"]
    assert "TFLOW" not in stayed["section_1_overall_flow"]
    assert stayed["symbol"]["headline"] == "HLINE"
    assert "HGAIN" in stayed["section_6_final_reward"].split("TLUCK")[0]


def test_solo_verdict_drops_the_opposite_hobby_paragraph():
    data = assemble(
        _travel(),
        _hobby("함께 동호회에서 같이 배우면 좋아요."),
        move_high=True, play_high=False, company="solo", timing_months=["3월"],
    )
    text = data["section_5_solo_vs_together"]
    assert "혼자 움직이는" in text
    assert "동호회" not in text


def test_axes_separate_movement_and_company():
    solo = read_axes({
        "day_branch": "子",
        "sinsal": {"has_yeokma": True},
        "derived": {"group_power": {"식상": 0, "비겁": 0}},
        "sewoon_sipsin": {"gan": "정재", "ji": "정인"},
    }, "甲午")
    assert solo["move_high"] is True
    assert solo["company"] == "solo"

    together = read_axes({
        "day_branch": "子",
        "sinsal": {"has_yeokma": False},
        "derived": {"group_power": {"식상": 0, "비겁": 2}},
        "sewoon_sipsin": {"gan": "비견", "ji": "정인"},
    }, "乙丑")
    assert together["move_high"] is False
    assert together["company"] == "together"


def test_no_runtime_llm_on_the_module():
    import domains.yearly.travel_hobby as mod
    source = inspect.getsource(mod)
    assert "gemini" not in source.lower()
    assert "call_gemini" not in source


def test_endpoint_returns_six_sections_from_static_db():
    res = client.post(
        "/api/v1/yearly/travel-hobby",
        json={"year": 1990, "month": 5, "day": 15, "hour": 14, "minute": 30, "gender": "female", "target_year": 2026},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["is_fallback"] is False
    assert body["category"] == "travel_hobby"
    assert body["target_year"] == 2026
    for key in FIELDS:
        assert body[key]
    assert all(word.startswith("#") for word in body["symbol"]["keywords"])
    kept = client.post(
        "/api/v1/yearly/travel",
        json={"year": 1990, "month": 5, "day": 15, "hour": 14, "gender": "female", "target_year": 2026},
    )
    assert kept.status_code == 200
    assert kept.json()["category"] == "travel"
    assert "travel_style" in kept.json()


def test_p95_under_20ms_after_warmup():
    _cached_travel_hobby.cache_clear()
    args = dict(year=1992, month=11, day=3, hour=9, minute=0, gender="male", target_year=2026)
    first, fb = generate_travel_hobby(**args)
    assert fb is False
    assert first["section_1_overall_flow"]
    samples = []
    for _ in range(40):
        started = time.perf_counter()
        again, _ = generate_travel_hobby(**args)
        samples.append(time.perf_counter() - started)
        assert again["symbol"]["keywords"] == first["symbol"]["keywords"]
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 0.02, p95
