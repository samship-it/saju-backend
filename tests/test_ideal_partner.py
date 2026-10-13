"""인연 가이드: 정적 룰, 프로필 조회, 복콩 차감, 응답 속도."""
import gc
import inspect
import itertools
import time

from fastapi.testclient import TestClient

import main
from core.constants import GAN, JI
from domains.love.engine import build_ideal_partner, samhap_of, yukhap_of
from domains.love.profiles import delete_profile, upsert_profile
from domains.love.router import ideal_partner
from domains.love.service import _reading_cache

client = TestClient(main.app)

BANNED = (
    "십신", "용신", "희신", "기신", "신강", "신약", "중화",
    "비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인",
    "비겁", "식상", "재성", "관성", "인성",
    "일지", "일간", "육합", "삼합", "배우자", "원국", "천간", "지지", "오행",
    "결혼", "못 한다", "못합니다",
)
ELEMENTS = ("목", "화", "토", "금", "수")


def _chart(day_master="甲", day_branch="子", present=False, missing="금", complement="금", support="수"):
    power = {elem: (0.0 if elem == missing else 2.0) for elem in ELEMENTS}
    return {
        "day_master": day_master,
        "day_branch": day_branch,
        "spouse_star": {"present": present},
        "strength": {
            "day_master_elem": "목",
            "elem_power": power,
            "yongsin": [complement],
            "heesin": [support] if support else [],
        },
    }


def _texts(payload):
    found = []

    def walk(value):
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return found


def _cleanup(*user_ids):
    for user_id in user_ids:
        delete_profile(user_id)


def test_axes_map_to_static_copy():
    data, is_fallback = build_ideal_partner(_chart())
    assert is_fallback is False
    assert data["complement_element"]["element"] == "금"
    assert data["complement_element"]["support_element"] == "수"
    assert "비어" in data["user_diagnosis"]
    assert data["partner_personality"]["type"] == "리더형"
    assert "밥" in data["partner_synergy_tip"]  # 子 육합 → 토
    assert "서두르지 않아도" in data["partner_synergy_tip"]

    opened, _ = build_ideal_partner(_chart(present=True))
    assert "이미 열려" in opened["partner_synergy_tip"]

    wood, _ = build_ideal_partner(_chart(day_branch="寅"))
    assert "산책" in wood["partner_synergy_tip"]
    assert wood["partner_synergy_tip"] != data["partner_synergy_tip"]


def test_yukhap_and_samhap_cover_every_branch():
    for branch in JI:
        other, elem = yukhap_of(branch)
        assert other and other != branch
        assert elem in ELEMENTS
        assert samhap_of(branch) in ELEMENTS


def test_every_combo_hides_technical_terms():
    for stem, branch, present, missing, complement in itertools.product(
        GAN, JI, (True, False), ELEMENTS, ELEMENTS,
    ):
        data, is_fallback = build_ideal_partner(
            _chart(
                day_master=stem, day_branch=branch, present=present,
                missing=missing, complement=complement, support="화" if complement != "화" else "수",
            )
        )
        assert is_fallback is False
        assert data["partner_personality"]["type"] in ("리더형", "포용형", "친구형", "표현형", "실속형")
        blob = " ".join(_texts(data))
        for term in BANNED:
            assert term not in blob, (stem, branch, term)


def test_fallback_when_chart_is_incomplete():
    data, is_fallback = build_ideal_partner({})
    assert is_fallback is True
    assert data["partner_personality"]["type"] == "포용형"
    for term in BANNED:
        assert term not in " ".join(_texts(data))


def test_same_chart_is_deterministic():
    first, _ = build_ideal_partner(_chart(day_branch="寅", present=True))
    second, _ = build_ideal_partner(_chart(day_branch="寅", present=True))
    assert first == second


def test_no_runtime_llm_on_the_path():
    import domains.love.engine as engine
    import domains.love.service as service
    source = inspect.getsource(engine) + inspect.getsource(service)
    lowered = source.lower()
    assert "gemini" not in lowered
    assert "generativeai" not in lowered


def test_missing_user_and_profile_are_403():
    no_user = client.post("/api/v1/love/ideal-partner")
    assert no_user.status_code == 403
    assert no_user.json()["code"] == "USER_REQUIRED"

    missing = client.post("/api/v1/love/ideal-partner", headers={"X-User-Id": "ideal-nobody"})
    assert missing.status_code == 403
    assert missing.json()["code"] == "PROFILE_NOT_FOUND"
    _cleanup("ideal-nobody")


def test_insufficient_bokkong_is_402_and_does_not_deduct():
    user_id = "ideal-poor"
    try:
        upsert_profile(user_id, year=1990, month=5, day=15, hour=14, minute=30, gender="female", bokkong=10)
        res = client.post("/api/v1/love/ideal-partner", headers={"X-User-Id": user_id})
        assert res.status_code == 402
        body = res.json()
        assert body["code"] == "INSUFFICIENT_BOKKONG"
        assert body["remaining_bokkong"] == 10
    finally:
        _cleanup(user_id)


def test_success_deducts_and_repeats_the_same_reading():
    user_id = "ideal-ok"
    _reading_cache.cache_clear()
    try:
        synced = client.put(
            "/api/v1/love/profile",
            headers={"X-User-Id": user_id},
            json={
                "year": 1990, "month": 5, "day": 15, "hour": 14, "minute": 30,
                "gender": "female", "is_lunar": False, "bokkong": 60,
            },
        )
        assert synced.status_code == 200
        assert synced.json()["data"]["bokkong"] == 60

        first = client.post("/api/v1/love/ideal-partner", headers={"X-User-Id": user_id})
        assert first.status_code == 200
        body = first.json()
        assert body["status"] == "success"
        assert body["content_type"] == "ideal_partner"
        assert body["is_fallback"] is False
        data = body["data"]
        for key in (
            "user_diagnosis", "complement_element", "partner_personality",
            "partner_synergy_tip", "remaining_bokkong", "is_fallback",
        ):
            assert key in data
        assert data["remaining_bokkong"] == 30
        assert data["is_fallback"] is False
        assert data["complement_element"]["element"] in ELEMENTS
        assert data["partner_personality"]["type"] in ("리더형", "포용형", "친구형", "표현형", "실속형")
        blob = " ".join(_texts(data))
        for term in BANNED:
            assert term not in blob

        second = client.post("/api/v1/love/ideal-partner", headers={"X-User-Id": user_id})
        assert second.status_code == 200
        again = second.json()["data"]
        assert again["remaining_bokkong"] == 0
        assert again["user_diagnosis"] == data["user_diagnosis"]
        assert again["partner_synergy_tip"] == data["partner_synergy_tip"]
        assert again["complement_element"] == data["complement_element"]
        assert again["partner_personality"] == data["partner_personality"]

        third = client.post("/api/v1/love/ideal-partner", headers={"X-User-Id": user_id})
        assert third.status_code == 402
        assert third.json()["remaining_bokkong"] == 0
    finally:
        _cleanup(user_id)


def test_p95_under_20ms_after_warmup():
    user_id = "ideal-speed"
    _reading_cache.cache_clear()
    try:
        upsert_profile(
            user_id, year=1992, month=11, day=3, hour=9, minute=0,
            gender="male", bokkong=100000,
        )
        assert ideal_partner(x_user_id=user_id)["status"] == "success"
        gc.collect()

        samples = []
        for _ in range(40):
            started = time.perf_counter()
            res = ideal_partner(x_user_id=user_id)
            samples.append(time.perf_counter() - started)
            assert res["status"] == "success"
        samples.sort()
        p95 = samples[int(len(samples) * 0.95) - 1]
        assert p95 < 0.02, p95
    finally:
        _cleanup(user_id)
