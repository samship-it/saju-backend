"""재테크 하루 캐시 + Gemini 에러 로그 분류 — 실제 Gemini/운영 DB 없이 검증."""
import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
import core.database as database
from domains.wealth import service as wealth
from shared import ai_client

BIRTH = dict(year=1990, month=5, day=15, hour=14, minute=30, gender="female", is_lunar=False)


@pytest.fixture
def mem_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(database, "db_session", session)
    yield session
    session.close()


@pytest.fixture
def fake_gemini(monkeypatch):
    state = {"calls": 0, "fallback": False}

    def fake(prompt, fallback_data, system_instruction=None):
        state["calls"] += 1
        if state["fallback"]:
            return fallback_data, True
        return {**fallback_data, "investment_fortune": f"AI 생성 #{state['calls']}"}, False

    monkeypatch.setattr(wealth, "call_gemini_json", fake)
    return state


def test_same_user_same_day_hits_cache(mem_db, fake_gemini):
    r1, fb1 = wealth.analyze_daily_finance(**BIRTH, target_date="2026-09-26")
    r2, fb2 = wealth.analyze_daily_finance(**BIRTH, target_date="2026-09-26")
    assert (fb1, fb2) == (False, False)
    assert fake_gemini["calls"] == 1
    assert r1["data"]["investment_fortune"] == r2["data"]["investment_fortune"] == "AI 생성 #1"


def test_different_day_or_user_regenerates(mem_db, fake_gemini):
    wealth.analyze_daily_finance(**BIRTH, target_date="2026-09-26")
    wealth.analyze_daily_finance(**BIRTH, target_date="2026-09-27")
    wealth.analyze_daily_finance(**{**BIRTH, "day": 16}, target_date="2026-09-26")
    assert fake_gemini["calls"] == 3


def test_fallback_is_not_cached(mem_db, fake_gemini):
    fake_gemini["fallback"] = True
    _, fb = wealth.analyze_daily_finance(**BIRTH, target_date="2026-09-26")
    assert fb is True
    fake_gemini["fallback"] = False
    _, fb = wealth.analyze_daily_finance(**BIRTH, target_date="2026-09-26")
    assert fb is False
    assert fake_gemini["calls"] == 2


def test_missing_key_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    with caplog.at_level(logging.WARNING, logger="shared.ai_client"):
        _, fb = ai_client.call_gemini_json("p", {"x": 1})
    assert fb is True
    assert "GEMINI_API_KEY 환경변수 미설정" in caplog.text


@pytest.mark.parametrize("msg,expected", [
    ("400 API key not valid. Please pass a valid API key. [reason: API_KEY_INVALID]", "인증 실패"),
    ("404 models/gemini-x is not found", "404 모델 없음"),
    ("429 Quota exceeded for metric", "429"),
    ("503 The service is currently unavailable", "5xx"),
])
def test_classify_error(msg, expected):
    assert expected in ai_client._classify_error(Exception(msg))
