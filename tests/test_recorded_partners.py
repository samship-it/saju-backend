"""예전에 확인한 인연 5명은 같은 ID로만 다시 채운다."""
from fastapi.testclient import TestClient

import main
from domains.daily.partners import (
    RECORDED_PARTNERS,
    delete_partner,
    ensure_recorded_partners,
    partner_of,
    partners_of,
    upsert_partner,
)

client = TestClient(main.app)
API_KEY = {"x-api-key": "default-secret-key"}
OWNER = "app-user"


def _clear():
    for spec in RECORDED_PARTNERS:
        delete_partner(OWNER, spec["partner_id"])


def _birth(row):
    return (row["nickname"], row["year"], row["month"], row["day"], row["hour"], row["gender"])


def test_missing_recorded_partners_come_back_with_the_same_ids():
    _clear()
    assert partners_of(OWNER) == []
    ensure_recorded_partners()
    rows = {row["partner_id"]: row for row in partners_of(OWNER)}
    assert set(rows) == {spec["partner_id"] for spec in RECORDED_PARTNERS}
    for spec in RECORDED_PARTNERS:
        row = rows[spec["partner_id"]]
        assert _birth(row) == (
            spec["nickname"], spec["year"], spec["month"], spec["day"], spec["hour"], spec["gender"],
        )
        assert row["owner_user_id"] == OWNER


def test_existing_row_is_not_replaced_and_the_others_stay():
    ensure_recorded_partners()
    changed = "mvxoeewu-c1b083"
    upsert_partner(
        OWNER, changed, nickname="DY",
        year=1986, month=4, day=4, hour=10, gender="female",
    )
    before = {row["partner_id"]: _birth(row) for row in partners_of(OWNER)}
    ensure_recorded_partners()
    after = {row["partner_id"]: _birth(row) for row in partners_of(OWNER)}
    assert after == before
    assert after[changed][3] == 4
    delete_partner(OWNER, changed)
    ensure_recorded_partners()
    restored = partner_of(OWNER, changed)
    assert restored["day"] == 3
    assert restored["nickname"] == "DY"


def test_partner_list_returns_the_five_recorded_people():
    ensure_recorded_partners()
    listed = client.get("/api/v1/daily/partners", headers=API_KEY, params={"user_id": OWNER})
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert [row["id"] for row in rows] == [spec["partner_id"] for spec in RECORDED_PARTNERS]
    by_id = {row["id"]: row for row in rows}
    assert by_id["mv815kyv-ehz7y3"]["time_unknown"] is True
    assert by_id["mv815kyv-ehz7y3"]["hour"] is None
    assert by_id["mvxoeewu-c1b083"]["hour"] == 10
    assert by_id["mv81h8a0-z404bg"]["nickname"] == "유유"
