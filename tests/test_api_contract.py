"""API 응답 구조가 기획 문서 규격과 일치하는지 검증.

GEMINI_API_KEY 없이 실행되면 각 서비스는 폴백을 반환한다. 폴백도 동일한 스키마여야 하므로
이 테스트는 '구조' 계약을 검증한다 (문구 내용이 아니라 키/타입).
"""
import json
import re

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)
API_KEY = {"x-api-key": "default-secret-key"}

BIRTH_A = {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"}
BIRTH_B = {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}
BIRTH_NO_TIME = {"year": 1988, "month": 11, "day": 2, "gender": "female"}  # 출생시간 미상

FORBIDDEN_KEYS = {"lucky_items", "lucky_elements", "lucky_element", "lucky_financial_tips",
                  "lucky_color", "lucky_days_type", "market_context", "target_year_input"}


def _all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def _no_forbidden(payload):
    assert not (_all_keys(payload) & FORBIDDEN_KEYS), f"금지된 필드 발견: {_all_keys(payload) & FORBIDDEN_KEYS}"


# ------------------------------------------------------------------ 만세력 명식
def test_saju_chart_structure():
    r = client.post("/api/v1/saju/chart", json=BIRTH_A)
    assert r.status_code == 200, r.text
    body = r.json()
    si = body["saju_info"]
    assert si["day_master"] and si["day_ganji"]
    assert set(si["five_elements"].keys()) == {"목", "화", "토", "금", "수"}
    _assert_has_basis(si)
    _no_forbidden(body)


def test_saju_chart_birth_time_unknown():
    r = client.post("/api/v1/saju/chart", json=BIRTH_NO_TIME)
    assert r.status_code == 200
    assert r.json()["birth_time_known"] is False
    assert r.json()["saju_info"]["time_ganji"] == ""


# ------------------------------------------------------------------ 오늘의 운세
def test_daily_fortune_structure():
    r = client.post("/api/v1/daily/fortune", headers=API_KEY,
                    json={"user_id": "t1", **BIRTH_A, "target_date": "2026-09-03"})
    assert r.status_code == 200, r.text
    body = r.json()
    d = body["data"]
    for k in ("overall_score", "money_score", "love_score", "work_study_score"):
        assert isinstance(d[k], int) and 0 <= d[k] <= 100
    assert set(d["summary"].keys()) == {"overall", "money", "love_single", "love_couple", "work_study"}
    assert len(d["keywords"]) == 3
    assert isinstance(d["recommended_action"], str)
    assert d["score_emoji"] and re.match(r"^\d+-\d+$", d["score_band"])
    _no_forbidden(body)


def test_daily_fortune_score_consistency():
    payload = {"user_id": "t2", **BIRTH_A, "target_date": "2026-09-03"}
    r1 = client.post("/api/v1/daily/fortune", headers=API_KEY, json=payload).json()["data"]
    r2 = client.post("/api/v1/daily/fortune", headers=API_KEY, json=payload).json()["data"]
    assert r1["overall_score"] == r2["overall_score"]


def test_daily_birth_time_unknown():
    r = client.post("/api/v1/daily/fortune", headers=API_KEY,
                    json={"user_id": "t3", **BIRTH_NO_TIME, "target_date": "2026-09-03"})
    assert r.status_code == 200
    assert r.json()["birth_time_known"] is False


# ------------------------------------------------------------------ 오늘의 재테크 사주
def test_daily_finance_structure():
    r = client.post("/api/v1/wealth/analysis", json={**BIRTH_A, "target_date": "2026-09-03"})
    assert r.status_code == 200, r.text
    body = r.json()
    d = body["data"]
    for k in ("market_point", "investment_fortune", "consumption_fortune", "money_flow", "caution_point"):
        assert isinstance(d[k], str)
    assert set(d["investment_behavior"].keys()) == {"tendency", "aggressiveness", "chase_risk", "spending_tendency"}
    assert "overall_score" not in d  # 재테크 사주는 점수 없음
    _no_forbidden(body)


# ------------------------------------------------------------------ 타로
@pytest.mark.parametrize("reading_type,finance", [("오늘의 타로", False), ("오늘의 재테크 타로", True)])
def test_tarot_structure(reading_type, finance):
    r = client.post("/api/v1/tarot/read",
                    json={"question": "요즘 고민이 많아요", "reading_type": reading_type,
                          "card_id": 3, "is_reversed": True})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["card"]["id"] == 3
    assert d["card"]["image_url"] == "/static/tarot_images/3.jpg"
    assert d["orientation"] == "역방향" and d["is_reversed"] is True
    assert d["card_meaning"] and d["advice"]
    assert d["reading_type"] == reading_type
    if finance:
        assert d["finance_summary"]


def test_tarot_cards_list():
    r = client.get("/api/v1/tarot/cards")
    cards = r.json()["cards"]
    assert len(cards) == 22
    assert cards[21]["image_url"] == "/static/tarot_images/21.jpg"


def test_tarot_all_cards_have_content():
    from domains.tarot.content import load_card_content
    data = load_card_content()
    assert set(data.keys()) == set(range(22))
    for cid, variants in data.items():
        for key in ("upright", "reversed", "finance_upright", "finance_reversed"):
            assert variants[key]["description"], f"card {cid} {key} 설명 없음"
            assert variants[key]["advice"], f"card {cid} {key} 조언 없음"


# ------------------------------------------------------------------ 나의 성격 / 적성
def test_character_structure():
    r = client.post("/api/v1/personality/character", json=BIRTH_A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["content_type"] == "나의 성격"
    assert set(body["report"].keys()) == {
        "base_nature", "strengths", "weaknesses", "supplement", "relationships", "work_style"}
    _no_forbidden(body)


def test_aptitude_structure():
    r = client.post("/api/v1/personality/aptitude", json=BIRTH_A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["content_type"] == "나의 적성"
    assert set(body["report"].keys()) == {
        "fit_task", "fit_field", "good_env", "org_style", "tiring_env", "favorable_direction"}


# ------------------------------------------------------------------ 궁합
def test_compatibility_structure_and_band():
    r = client.post("/api/v1/compatibility/analyze",
                    json={"person1": BIRTH_A, "person2": BIRTH_B, "relation_type": "romantic"})
    assert r.status_code == 200, r.text
    body = r.json()
    sc = body["scores"]
    for k in ("total", "overall", "love", "communication", "conflict", "economy"):
        assert isinstance(sc[k], int) and 0 <= sc[k] <= 100
    # 8단계 한줄평 테이블 검증
    from core.constants import compat_band
    expected = compat_band(sc["total"])
    assert body["relation_type_label"] == expected["relation_type"]
    assert body["one_liner"] == expected["one_liner"]
    assert set(body["report"].keys()) == {
        "overall", "love", "communication", "conflict", "conflict_resolution", "economy", "relationship_advice"}
    _no_forbidden(body)


def test_compatibility_partner_missing_birthtime_ok():
    r = client.post("/api/v1/compatibility/analyze",
                    json={"person1": BIRTH_A, "person2": BIRTH_NO_TIME})
    assert r.status_code == 200
    assert r.json()["person2"]["birth_time_known"] is False


# ------------------------------------------------------------------ 재회 / 짝사랑 / 결혼
@pytest.mark.parametrize("path", ["reunion", "crush"])
def test_love_flow_single(path):
    r = client.post(f"/api/v1/relationship/{path}", json={"person": BIRTH_B})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["partner_exists"] is False
    assert isinstance(body["overall"], str) and len(body["overall"]) > 50
    assert "strategy_3months" not in body


@pytest.mark.parametrize("path", ["reunion", "crush"])
def test_love_flow_with_partner_has_3month(path):
    r = client.post(f"/api/v1/relationship/{path}",
                    json={"person": BIRTH_B, "partner": BIRTH_A, "target_date": "2026-11-15"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["partner_exists"] is True
    strat = body["strategy_3months"]
    assert len(strat) == 3
    # 3개월 자동 계산: 2026-11 기준 -> 2026-12, 2027-01, 2027-02
    assert strat[0]["month"] == "2026년 12월"
    assert strat[1]["month"] == "2027년 1월"
    assert strat[2]["month"] == "2027년 2월"


def test_marriage_single():
    r = client.post("/api/v1/relationship/marriage",
                    json={"person": BIRTH_B, "target_year": 2026})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window"] == [2026, 2035]
    assert len(body["year_strengths"]) == 10
    assert len(body["best_years"]) == 3
    assert isinstance(body["overall_score"], int) and 0 <= body["overall_score"] <= 100
    assert body["best_period_label"]
    _no_forbidden(body)


def test_marriage_with_partner():
    r = client.post("/api/v1/relationship/marriage",
                    json={"person": BIRTH_B, "partner": BIRTH_A, "target_year": 2026})
    body = r.json()
    assert body["partner_exists"] is True
    assert isinstance(body["couple_best_year"], int)
    assert "partner_best_years" in body


def test_marriage_year_dynamic_default():
    r = client.post("/api/v1/relationship/marriage", json={"person": BIRTH_B}).json()
    import datetime
    assert r["target_year"] == datetime.date.today().year


# ------------------------------------------------------------------ 연간 운세 9종
YEARLY_CATS = ["overall", "wealth", "love", "business", "career_change",
               "study", "health", "travel", "hobby"]


@pytest.mark.parametrize("cat", YEARLY_CATS)
def test_yearly_category_structure(cat):
    r = client.post(f"/api/v1/yearly/{cat}", json={**BIRTH_A, "target_year": 2026})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == cat
    assert body["target_year"] == 2026
    assert isinstance(body["analysis"], str) and body["analysis"]
    _no_forbidden(body)


def test_yearly_overall_has_monthly_and_keywords():
    r = client.post("/api/v1/yearly/overall", json={**BIRTH_A, "target_year": 2026}).json()
    assert len(r["monthly"]) == 12
    assert len(r["keywords"]) == 3
    assert len(r["best_months"]) == 3 and len(r["caution_months"]) == 3
    assert r["one_line"]


def test_yearly_study_age_branching():
    young = client.post("/api/v1/yearly/study", json={"year": 2010, "month": 3, "day": 1, "gender": "male", "target_year": 2026}).json()
    old = client.post("/api/v1/yearly/study", json={"year": 1970, "month": 3, "day": 1, "gender": "male", "target_year": 2026}).json()
    assert young["age"] != old["age"]
    assert young["life_stage"] != old["life_stage"]


def test_yearly_year_is_dynamic_not_hardcoded():
    import datetime
    r = client.post("/api/v1/yearly/overall", json=BIRTH_A).json()
    assert r["target_year"] == datetime.date.today().year


def test_yearly_travel_hobby_recommendation():
    t = client.post("/api/v1/yearly/travel", json={**BIRTH_A, "target_year": 2026}).json()
    assert isinstance(t["recommendation"], dict)
    h = client.post("/api/v1/yearly/hobby", json={**BIRTH_A, "target_year": 2026}).json()
    assert isinstance(h["recommendation"], list)


def test_yearly_categories_endpoint():
    r = client.get("/api/v1/yearly/categories").json()
    assert len(r["categories"]) == 9


def test_unknown_yearly_category_404():
    r = client.post("/api/v1/yearly/nonsense", json=BIRTH_A)
    assert r.status_code == 404


# ------------------------------------------------------------------ 제거된 엔드포인트
def test_comprehensive_endpoint_removed():
    r = client.post("/api/v1/comprehensive/report", json=BIRTH_A)
    assert r.status_code == 404


# ------------------------------------------------------------------ 용신/격국 근거 노출
def _assert_has_basis(saju_info):
    assert saju_info["strength"]["basis"], "용신 근거(basis) 없음"
    assert saju_info["strength"]["yongsin"] is not None
    assert saju_info["strength"]["method"]
    assert saju_info["gyeokguk"]["basis"], "격국 근거(basis) 없음"


def test_yongsin_basis_exposed_in_responses():
    r = client.post("/api/v1/daily/fortune", headers=API_KEY,
                    json={"user_id": "b1", **BIRTH_A, "target_date": "2026-09-03"})
    _assert_has_basis(r.json()["saju_info"])

    r = client.post("/api/v1/personality/character", json=BIRTH_A)
    _assert_has_basis(r.json()["saju_info"])

    r = client.post("/api/v1/yearly/wealth", json={**BIRTH_A, "target_year": 2026})
    _assert_has_basis(r.json()["saju_info"])

    r = client.post("/api/v1/relationship/marriage", json={"person": BIRTH_B, "target_year": 2026})
    _assert_has_basis(r.json()["person1"])


def test_score_emoji_bands_cover_full_range():
    from core.constants import score_to_emoji, SCORE_EMOJI_BANDS
    assert len(SCORE_EMOJI_BANDS) == 10
    for s in range(0, 101):
        assert score_to_emoji(s)  # 모든 점수에 이모지 존재
    assert score_to_emoji(0) != score_to_emoji(100)
