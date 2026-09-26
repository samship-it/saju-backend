"""Gemini 호출 실패 원인 로그 분류 — 실제 Gemini 호출 없이 검증."""
import logging

import pytest

import config
from shared import ai_client


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
