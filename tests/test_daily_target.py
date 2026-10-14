"""오늘의 운세 — 본인 사주와 등록된 인연 사주.

target_person_id 가 없으면 요청 본문의 생년월일로 계산한다.
있으면 그 사용자에게 등록된 인연의 사주만 읽고, 본문 생년월일은 쓰지 않는다.
"""
import datetime
import gc
import time

import pytest
from fastapi.testclient import TestClient

import main
from core.saju_base import calculate_saju
from domains.daily.ilju_image import ilju_profile_image
from domains.daily.partners import delete_partner, upsert_partner
from domains.daily.router import DailyFortuneRequest, _cached_daily_reading, get_daily_fortune_endpoint
from domains.daily.service import generate_daily_fortune
from domains.love.profiles import delete_profile, upsert_profile

client = TestClient(main.app)
API_KEY = {"x-api-key": "default-secret-key"}
OWNER = "daily-target-owner"
OTHER = "daily-target-other"
PARTNER = "partner-minji"
DATE = "2026-09-03"

SELF = {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"}
TARGET = {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}


@pytest.fixture()
def partner():
    upsert_partner(
        OWNER, PARTNER, nickname="민지",
        year=TARGET["year"], month=TARGET["month"], day=TARGET["day"],
        hour=TARGET["hour"], minute=TARGET["minute"], gender=TARGET["gender"],
    )
    yield
    delete_partner(OWNER, PARTNER)


def _fortune(saju_birth):
    saju = calculate_saju(
        saju_birth["year"], saju_birth["month"], saju_birth["day"],
        saju_birth["hour"], saju_birth["minute"],
        gender=saju_birth["gender"], target_date=datetime.date(2026, 9, 3),
    )
    result, is_fallback = generate_daily_fortune(saju)
    return saju, result, is_fallback


def test_self_uses_request_birth_and_returns_ilju(partner):
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, **SELF, "target_date": DATE, "nickname": "상현",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    saju, result, is_fallback = _fortune(SELF)
    assert body["target_person_id"] is None
    assert body["nickname"] == "상현"
    assert body["target_name"] == "상현님"
    assert body["ilju_profile_image"] == ilju_profile_image(saju["day_ganji"])
    assert body["ilju_animal_icon"] == body["ilju_profile_image"]
    assert len(body["ilju_animal_icon"]) == 2
    assert body["saju_info"]["day_ganji"] == saju["day_ganji"]
    assert body["data"]["overall_score"] == result["overall_score"]
    assert body["is_fallback"] is is_fallback
    assert body["data"]["love_status"] is None


def test_target_uses_registered_partner_not_body_birth(partner):
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, **SELF, "target_date": DATE,
        "target_person_id": PARTNER, "nickname": "상현",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    self_saju, _, _ = _fortune(SELF)
    target_saju, result, is_fallback = _fortune(TARGET)
    assert self_saju["day_ganji"] != target_saju["day_ganji"]
    assert body["target_person_id"] == PARTNER
    assert body["nickname"] == "민지"
    assert body["target_name"] == "민지님"
    assert body["saju_info"]["day_ganji"] == target_saju["day_ganji"]
    assert body["ilju_animal_icon"] == ilju_profile_image(target_saju["day_ganji"])
    assert body["ilju_profile_image"] == body["ilju_animal_icon"]
    assert body["ilju_animal_icon"] != ilju_profile_image(self_saju["day_ganji"])
    assert body["data"]["overall_score"] == result["overall_score"]
    assert body["data"]["woon_score_delta"] == result["woon_score_delta"]
    assert body["is_fallback"] is is_fallback


def test_target_does_not_require_body_birth(partner):
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, "target_person_id": PARTNER, "target_date": DATE,
    })
    assert res.status_code == 200, res.text
    assert res.json()["saju_info"]["day_ganji"] == _fortune(TARGET)[0]["day_ganji"]


def test_unknown_or_other_users_partner_is_404(partner):
    missing = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, **SELF, "target_person_id": "no-such", "target_date": DATE,
    })
    assert missing.status_code == 404
    assert missing.json()["code"] == "PARTNER_NOT_FOUND"
    stolen = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OTHER, **SELF, "target_person_id": PARTNER, "target_date": DATE,
    })
    assert stolen.status_code == 404
    assert stolen.json()["code"] == "PARTNER_NOT_FOUND"


def test_self_without_birth_is_422():
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={"user_id": OWNER})
    assert res.status_code == 422
    assert res.json()["code"] == "BIRTH_REQUIRED"


def test_partner_sync_then_fortune(partner):
    saved = client.put("/api/v1/daily/partners", headers=API_KEY, json={
        "user_id": OWNER, "partner_id": "partner-sync", "nickname": "하늘",
        "year": 1988, "month": 11, "day": 2, "gender": "male",
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["nickname"] == "하늘"
    try:
        res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
            "user_id": OWNER, "target_person_id": "partner-sync", "target_date": DATE,
        })
        assert res.status_code == 200, res.text
        assert res.json()["nickname"] == "하늘"
        assert res.json()["birth_time_known"] is False
    finally:
        delete_partner(OWNER, "partner-sync")


def test_partner_list_returns_id_nickname_and_icon(partner):
    listed = client.get("/api/v1/daily/partners", headers=API_KEY, params={"user_id": OWNER})
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert len(rows) == 1
    assert set(rows[0]) == {"id", "nickname", "ilju_animal_icon"}
    assert rows[0]["id"] == PARTNER
    assert rows[0]["nickname"] == "민지"
    icon = ilju_profile_image(_fortune(TARGET)[0]["day_ganji"])
    assert rows[0]["ilju_animal_icon"] == icon
    assert rows[0]["ilju_animal_icon"]
    other = client.get("/api/v1/daily/partners", headers=API_KEY, params={"user_id": OTHER})
    assert other.status_code == 200
    assert other.json()["data"] == []


def test_partner_list_requires_user():
    res = client.get("/api/v1/daily/partners", headers=API_KEY, params={"user_id": " "})
    assert res.status_code == 422
    assert res.json()["code"] == "USER_REQUIRED"


def test_self_profile_status_customizes_love_and_job_text():
    user_id = "daily-status-self"
    upsert_profile(
        user_id, year=SELF["year"], month=SELF["month"], day=SELF["day"],
        hour=SELF["hour"], minute=SELF["minute"], gender=SELF["gender"],
        love_status="dating", job_status="homemaker",
    )
    try:
        res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
            "user_id": user_id, **SELF, "target_date": DATE,
            "love_status": "married", "job_status": "student",
        })
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        expected, _ = generate_daily_fortune(_fortune(SELF)[0], love_status="dating", job_status="homemaker")
        assert data["love_status"] == "dating"
        assert data["job_status"] == "homemaker"
        assert data["summary"]["love"] == expected["summary"]["love"]
        assert data["summary"]["job_levelup"] == expected["summary"]["job_levelup"]
        assert data["overall_score"] == expected["overall_score"]
    finally:
        delete_profile(user_id)


def test_target_without_status_defaults_to_single_employee(partner):
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, **SELF, "target_person_id": PARTNER, "target_date": DATE,
        "love_status": "married", "job_status": "student",
    })
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    chart = _fortune(TARGET)[0]
    expected, _ = generate_daily_fortune(chart, love_status="single", job_status="employee")
    viewer, _ = generate_daily_fortune(chart, love_status="married", job_status="student")
    assert data["love_status"] == "single"
    assert data["job_status"] == "employee"
    assert data["summary"]["love"] == expected["summary"]["love"]
    assert data["summary"]["job_levelup"] == expected["summary"]["job_levelup"]
    assert data["summary"]["love"] != viewer["summary"]["love"]
    assert data["overall_score"] == expected["overall_score"]


def test_target_uses_its_own_status_when_stored(partner):
    upsert_partner(
        OWNER, PARTNER, nickname="민지",
        year=TARGET["year"], month=TARGET["month"], day=TARGET["day"],
        hour=TARGET["hour"], minute=TARGET["minute"], gender=TARGET["gender"],
        love_status="dating", job_status="job_seeker",
    )
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, "target_person_id": PARTNER, "target_date": DATE,
        "love_status": "married", "job_status": "retired",
    })
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    expected, _ = generate_daily_fortune(
        _fortune(TARGET)[0], love_status="dating", job_status="job_seeker",
    )
    assert data["love_status"] == "dating"
    assert data["job_status"] == "job_seeker"
    assert data["summary"]["love"] == expected["summary"]["love"]
    assert data["summary"]["job_levelup"] == expected["summary"]["job_levelup"]


def test_time_unknown_uses_three_pillars_even_if_hour_is_sent():
    flagged = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": "time-unknown-self", **SELF, "time_unknown": True, "target_date": DATE,
    })
    assert flagged.status_code == 200, flagged.text
    body = flagged.json()
    info = body["saju_info"]
    assert body["birth_time_known"] is False
    assert info["time_ganji"] == ""
    assert len(info["day_ganji"]) == 2
    assert sum(info["five_elements"].values()) == 6
    assert body["ilju_animal_icon"] == ilju_profile_image(info["day_ganji"])
    assert isinstance(body["data"]["overall_score"], int)

    omitted = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": "time-unknown-self",
        "year": SELF["year"], "month": SELF["month"], "day": SELF["day"],
        "gender": SELF["gender"], "target_date": DATE,
    })
    assert omitted.status_code == 200, omitted.text
    other = omitted.json()
    assert other["saju_info"]["day_ganji"] == info["day_ganji"]
    assert other["data"]["overall_score"] == body["data"]["overall_score"]
    assert other["ilju_animal_icon"] == body["ilju_animal_icon"]


def test_partner_registered_without_time_still_returns_fortune(partner):
    saved = client.put("/api/v1/daily/partners", headers=API_KEY, json={
        "user_id": OWNER, "partner_id": "partner-no-time", "nickname": "하늘",
        "year": 1988, "month": 11, "day": 2, "hour": 14, "time_unknown": True, "gender": "male",
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["hour"] is None
    try:
        res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
            "user_id": OWNER, "target_person_id": "partner-no-time", "target_date": DATE,
            "hour": 14, "time_unknown": False,
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["birth_time_known"] is False
        assert body["saju_info"]["time_ganji"] == ""
        assert sum(body["saju_info"]["five_elements"].values()) == 6
        assert body["ilju_animal_icon"]
        assert body["target_name"] == "하늘님"
    finally:
        delete_partner(OWNER, "partner-no-time")


def test_bad_api_key_is_403(partner):
    res = client.post("/api/v1/daily/fortune", headers={"x-api-key": "nope"}, json={
        "user_id": OWNER, **SELF, "target_date": DATE,
    })
    assert res.status_code == 403


def test_no_runtime_llm(monkeypatch, partner):
    def boom(*_a, **_k):
        raise AssertionError("runtime llm")

    monkeypatch.setattr("shared.ai_client.generate_gemini_analysis", boom)
    monkeypatch.setattr("shared.ai_client.call_gemini_json", boom)
    res = client.post("/api/v1/daily/fortune", headers=API_KEY, json={
        "user_id": OWNER, "target_person_id": PARTNER, "target_date": DATE,
    })
    assert res.status_code == 200, res.text


def test_p95_under_20ms_after_warmup(partner):
    _cached_daily_reading.cache_clear()
    req = DailyFortuneRequest(
        user_id=OWNER, target_person_id=PARTNER, target_date=DATE,
        year=SELF["year"], month=SELF["month"], day=SELF["day"],
    )
    first = get_daily_fortune_endpoint(req, "default-secret-key")
    assert first["nickname"] == "민지"
    assert first["target_name"] == "민지님"
    assert first["ilju_animal_icon"]
    assert first["ilju_animal_icon"] == first["ilju_profile_image"]
    gc.collect()
    samples = []
    for _ in range(40):
        started = time.perf_counter()
        again = get_daily_fortune_endpoint(req, "default-secret-key")
        samples.append(time.perf_counter() - started)
        assert again["data"]["overall_score"] == first["data"]["overall_score"]
        assert again["ilju_animal_icon"] == first["ilju_animal_icon"]
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 0.02, p95
