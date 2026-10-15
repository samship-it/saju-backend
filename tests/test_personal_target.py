"""평생운세·성격·적성 — 등록된 인연 사주.

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
OWNER = "personal-target-owner"
PARTNER = "personal-partner-minji"

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


def test_self_character_ignores_missing_target():
    res = client.post("/api/v1/personality/character", json=SELF)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["content_type"] == "나의 성격"
    assert body["target_person_id"] is None
    assert body["love_status"] is None
    assert body["job_status"] is None
    assert body["is_fallback"] is False


@pytest.mark.parametrize("path,content_type", [
    ("/api/v1/personality/character", "나의 성격"),
    ("/api/v1/personality/aptitude", "나의 적성"),
    ("/api/v1/lifelong/analysis", "lifelong_fortune"),
])
def test_target_uses_partner_chart_and_default_status(partner, path, content_type):
    self_res = client.post(path, json=SELF)
    res = client.post(path, json={
        "user_id": OWNER, "target_person_id": PARTNER,
        **SELF, "love_status": "married", "job_status": "student",
    }, headers=API_KEY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["content_type"] == content_type
    assert body["target_person_id"] == PARTNER
    assert body["nickname"] == "민지"
    assert body["target_name"] == "민지님"
    assert body["love_status"] == "single"
    assert body["job_status"] == "employee"
    assert body["saju_info"]["day_ganji"] != self_res.json()["saju_info"]["day_ganji"]


def test_stored_partner_status_is_kept(partner):
    upsert_partner(
        OWNER, PARTNER, nickname="민지",
        year=TARGET["year"], month=TARGET["month"], day=TARGET["day"],
        hour=TARGET["hour"], minute=TARGET["minute"], gender=TARGET["gender"],
        love_status="dating", job_status="student",
    )
    res = client.post("/api/v1/personality/character", json={
        "user_id": OWNER, "target_person_id": PARTNER,
    }, headers=API_KEY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["love_status"] == "dating"
    assert body["job_status"] == "student"


def test_missing_partner_is_not_found(partner):
    res = client.post("/api/v1/personality/aptitude", json={
        "user_id": OWNER, "target_person_id": "no-such",
    }, headers=API_KEY)
    assert res.status_code == 404
    assert res.json()["code"] == "PARTNER_NOT_FOUND"


def test_target_without_key_is_rejected(partner):
    res = client.post("/api/v1/lifelong/analysis", json={
        "user_id": OWNER, "target_person_id": PARTNER,
    })
    assert res.status_code == 403
