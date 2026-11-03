"""검수 모듈. 기본 스위치가 꺼져 있으면 기존 문장을 바꾸지 않는다."""
import os
import time
from pathlib import Path

import pytest

from shared.proofread import budget, store
from shared.proofread.apply import proofread_reading
from shared.proofread.guard import apply_edits
from shared.proofread.llm import LlmOutcome
from shared.proofread.policy import SERVER_HAS_PAYMENT_LEDGER, classify, llm_permitted
from shared.proofread.policy import ProductListPurchase
from shared.proofread.spell import correct
from shared.prose_quality import finish_reading

_PAID = {
    "content_type": "결혼운",
    "overall_score": 86,
    "overall": "2033년은 86점입니다. 오늘은 정말 좋았됬습니다. 甲 일주의 해석은 그대로 둡니다.",
}
_FREE = {
    "content_type": "daily_fortune",
    "overall_score": 70,
    "headline": "오늘은 정말 좋았됬습니다. 숫자 70은 그대로입니다.",
}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setenv("PROOFREAD_STORE", "memory")
    monkeypatch.setenv("PROOFREAD_ENABLED", "")
    monkeypatch.setenv("PROOFREAD_LLM_ENABLED", "")
    monkeypatch.setenv("PROOFREAD_LLM_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("PROOFREAD_MONTHLY_BUDGET_USD", "20")
    monkeypatch.setenv("PROOFREAD_PROMPT_VERSION", "1")
    monkeypatch.setenv("PROOFREAD_TIMEOUT_SEC", "5")
    store.reset_for_tests()
    yield
    store.reset_for_tests()


def _turn_on(monkeypatch, llm=False):
    monkeypatch.setenv("PROOFREAD_ENABLED", "true")
    monkeypatch.setenv("PROOFREAD_LLM_ENABLED", "true" if llm else "")


def _llm(edits, calls, input_tokens=100, output_tokens=20):
    def complete(text, model, output_tokens_limit):
        calls.append((text, model))
        return LlmOutcome(edits, input_tokens, output_tokens)

    return complete


def test_switches_default_off_and_payment_ledger_is_absent():
    assert os.environ["PROOFREAD_ENABLED"] == ""
    assert os.environ["PROOFREAD_LLM_ENABLED"] == ""
    assert SERVER_HAS_PAYMENT_LEDGER is False
    out, _ = finish_reading({"content_type": "결혼운", "overall": "좋았됬습니다."})
    assert out["overall"] == "좋았됬습니다."
    assert out["content_type"] == "결혼운"


def test_spellcheck_runs_for_free_and_paid_without_llm(monkeypatch):
    _turn_on(monkeypatch, llm=False)
    calls = []
    paid = proofread_reading(dict(_PAID), complete=_llm([], calls))
    free = proofread_reading(dict(_FREE), complete=_llm([], calls))
    assert calls == []
    assert "됐" in paid["overall"]
    assert "됬" not in paid["overall"]
    assert "됐" in free["headline"]
    assert paid["overall_score"] == 86
    assert free["overall_score"] == 70


def test_free_product_never_calls_llm(monkeypatch):
    _turn_on(monkeypatch, llm=True)
    monkeypatch.setenv("PROOFREAD_LLM_PAID_ONLY", "false")
    calls = []
    data = proofread_reading(dict(_FREE), complete=_llm([], calls))
    assert calls == []
    assert "됐" in data["headline"]
    assert classify({"content_type": "daily_finance"}) == "free"
    assert llm_permitted("free", ProductListPurchase()) is False
    assert llm_permitted("unknown", ProductListPurchase()) is False


def test_paid_product_calls_llm_once_and_reuses_cache(monkeypatch):
    _turn_on(monkeypatch, llm=True)
    calls = []
    edit = {
        "original": "좋았됐습니다",
        "suggestion": "좋았습니다",
        "error_type": "spelling",
        "confidence": 0.95,
    }
    first = proofread_reading(dict(_PAID), complete=_llm([edit], calls))
    second = proofread_reading(dict(_PAID), complete=_llm([edit], calls))
    assert len(calls) == 1
    assert "좋았습니다" in first["overall"]
    assert second["overall"] == first["overall"]
    assert first["overall_score"] == 86
    assert "2033" in first["overall"] and "86" in first["overall"]
    assert "甲" in first["overall"]


def test_cache_misses_when_prompt_version_changes(monkeypatch):
    _turn_on(monkeypatch, llm=True)
    calls = []
    proofread_reading(dict(_PAID), complete=_llm([], calls))
    monkeypatch.setenv("PROOFREAD_PROMPT_VERSION", "2")
    proofread_reading(dict(_PAID), complete=_llm([], calls))
    assert len(calls) == 2


def test_saju_mashup_is_detected_and_not_rewritten():
    text = "식살한 영업조직에서 일하면 좋았습니다."
    corrected, issues = correct(text)
    assert corrected == text
    assert any(item["type"] == "saju_mashup" and item["applied"] == "false" for item in issues)


def test_llm_cannot_change_score_hanja_or_saju_terms():
    text = "2033년은 86점이고 甲 일주는 용신 방향이 같습니다."
    edited = apply_edits(text, [
        {"original": "86점", "suggestion": "99점", "error_type": "typo", "confidence": 0.99},
        {"original": "甲", "suggestion": "乙", "error_type": "typo", "confidence": 0.99},
        {"original": "용신 방향", "suggestion": "좋은 흐름", "error_type": "spelling", "confidence": 0.99},
    ])
    assert edited == text


def test_api_failure_returns_spellchecked_original(monkeypatch):
    _turn_on(monkeypatch, llm=True)

    def boom(text, model, output_tokens):
        raise RuntimeError("down")

    data = proofread_reading(dict(_PAID), complete=boom)
    assert "됐" in data["overall"]
    assert data["overall_score"] == 86
    assert budget.spent() == 0


def test_timeout_returns_original_without_waiting_out(monkeypatch):
    _turn_on(monkeypatch, llm=True)
    monkeypatch.setenv("PROOFREAD_TIMEOUT_SEC", "0.2")

    def slow(text, model, output_tokens):
        time.sleep(1.5)
        return LlmOutcome([], 10, 10)

    started = time.monotonic()
    data = proofread_reading(dict(_PAID), complete=slow)
    elapsed = time.monotonic() - started
    assert elapsed < 1.0
    assert "됐" in data["overall"]
    assert data["overall_score"] == 86


def test_budget_blocks_the_next_call(monkeypatch):
    _turn_on(monkeypatch, llm=True)
    calls = []
    proofread_reading(dict(_PAID), complete=_llm([], calls, input_tokens=100, output_tokens=20))
    assert len(calls) == 1
    assert budget.spent() == pytest.approx(100 / 1_000_000 * 0.30 + 20 / 1_000_000 * 2.50)
    monkeypatch.setenv("PROOFREAD_MONTHLY_BUDGET_USD", "0")
    proofread_reading({
        "content_type": "결혼운",
        "overall": "다른 문장입니다. 이 문장은 아직 검수되지 않았습니다.",
    }, complete=_llm([], calls))
    assert len(calls) == 1


def test_unknown_model_is_not_called(monkeypatch):
    _turn_on(monkeypatch, llm=True)
    monkeypatch.setenv("PROOFREAD_LLM_MODEL", "unknown-model")
    calls = []
    proofread_reading(dict(_PAID), complete=_llm([], calls))
    assert calls == []


def test_paid_catalog_matches_the_agreed_products():
    paid = (
        "나의 성격", "나의 적성", "궁합", "재회운", "짝사랑운", "결혼운",
        "ideal_partner", "lifelong_fortune", "daewoon_period",
    )
    for name in paid:
        assert classify({"content_type": name}) == "paid"
    assert classify({"content_type": "2026년 총운"}) == "paid"
    assert classify({"reading_type": "오늘의 타로"}) == "paid"
    assert classify({"content_type": "daily_fortune"}) == "free"
    assert classify({"headline": "오늘의 문장"}) == "unknown"
    assert llm_permitted("paid", ProductListPurchase()) is True


def test_gemini_key_is_not_in_the_frontend():
    root = Path(__file__).resolve().parents[2] / "today-score-magic" / "src"
    if not root.is_dir():
        pytest.skip("frontend tree is not next to the backend")
    for path in root.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".env"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "GEMINI_API_KEY" not in text
        assert "PROOFREAD_" not in text
