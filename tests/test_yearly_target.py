"""연간 운세 — 등록된 인연 사주.

target_person_id 가 없으면 요청 본문의 생년월일로 계산한다.
있으면 그 사용자에게 등록된 인연의 사주만 읽고, 본문 생년월일은 쓰지 않는다.
인연의 연애/직업 상태가 없으면 싱글·직장인으로 둔다.
"""
import pytest
from fastapi.testclient import TestClient

import main
from domains.daily.partners import delete_partner, upsert_partner

client = TestClient(main.app)
API_KEY = {"x-api-key": "default-secret-key"}
OWNER = "yearly-target-owner"
PARTNER = "yearly-partner-minji"

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


def _post(category, body, headers=None):
    return client.post(f"/api/v1/yearly/{category}", json=body, headers=headers or {})


def test_self_yearly_ignores_missing_target_and_keeps_contract():
    res = _post("overall", {**SELF, "target_year": 2026})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["category"] == "overall"
    assert body["target_year"] == 2026
    assert body["target_person_id"] is None
    assert body["love_status"] is None
    assert body["job_status"] is None
    assert body["is_fallback"] is False


def test_target_yearly_uses_partner_chart_not_request_birth(partner):
    self_res = _post("overall", {**SELF, "target_year": 2026})
    res = _post("wealth", {
        "user_id": OWNER, "target_person_id": PARTNER, "target_year": 2027,
        **SELF, "love_status": "married", "job_status": "student",
    }, API_KEY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["target_person_id"] == PARTNER
    assert body["nickname"] == "민지"
    assert body["target_name"] == "민지님"
    assert body["target_year"] == 2027
    assert body["category"] == "wealth"
    assert body["love_status"] == "single"
    assert body["job_status"] == "employee"
    assert body["saju_info"]["day_ganji"] != self_res.json()["saju_info"]["day_ganji"]
    assert body["birth_time_known"] is True


@pytest.mark.parametrize("category", [
    "overall", "wealth", "love", "business", "career_change", "study", "health", "travel", "hobby",
])
def test_every_yearly_section_accepts_target(partner, category):
    res = _post(category, {
        "user_id": OWNER, "target_person_id": PARTNER, "target_year": 2028,
    }, API_KEY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["category"] == category
    assert body["target_year"] == 2028
    assert body["target_name"] == "민지님"
    assert body["analysis"] or body.get("overall_flow") or body.get("one_line")


def test_target_without_status_defaults_and_stored_status_wins(partner):
    upsert_partner(
        OWNER, PARTNER, nickname="민지",
        year=TARGET["year"], month=TARGET["month"], day=TARGET["day"],
        hour=None, minute=0, gender=TARGET["gender"],
        love_status="dating", job_status="job_seeker",
    )
    res = _post("love", {
        "user_id": OWNER, "target_person_id": PARTNER, "target_year": 2026,
        "hour": 12, "time_unknown": False,
        "love_status": "married", "job_status": "retired",
    }, API_KEY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["love_status"] == "dating"
    assert body["job_status"] == "job_seeker"
    assert body["birth_time_known"] is False


def test_travel_hobby_target_and_missing_partner(partner):
    ok = _post("travel-hobby", {
        "user_id": OWNER, "target_person_id": PARTNER, "target_year": 2026,
    }, API_KEY)
    assert ok.status_code == 200, ok.text
    assert ok.json()["target_name"] == "민지님"
    assert ok.json()["category"] == "travel_hobby"

    missing = _post("overall", {
        "user_id": OWNER, "target_person_id": "no-such", "target_year": 2026,
    }, API_KEY)
    assert missing.status_code == 404
    assert missing.json()["code"] == "PARTNER_NOT_FOUND"

    denied = _post("overall", {
        "user_id": OWNER, "target_person_id": PARTNER, "target_year": 2026,
    }, {"x-api-key": "nope"})
    assert denied.status_code == 403
