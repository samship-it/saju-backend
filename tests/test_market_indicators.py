"""시장 지표 엔드포인트 — 실제 야후 호출 없이 캐시/부분실패 동작만 검증."""
import pytest
from fastapi.testclient import TestClient

import main
from domains.market import indicators

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _reset_cache():
    indicators.clear_cache()
    yield
    indicators.clear_cache()


def _fake_quote(calls):
    def fake(ticker):
        calls.append(ticker)
        if ticker == "^IXIC":
            raise RuntimeError("yahoo down")
        return {"price": 100.0, "change": 1.5, "change_percent": 1.52}
    return fake


def test_partial_failure_returns_200_with_error_status(monkeypatch):
    calls = []
    monkeypatch.setattr(indicators, "_fetch_quote", _fake_quote(calls))

    r = client.get("/api/v1/market-indicators")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    ind = body["indicators"]
    assert set(ind) == {"KOSPI", "NASDAQ", "USDKRW"}

    assert ind["KOSPI"]["status"] == "ok"
    assert ind["KOSPI"]["price"] == 100.0
    assert ind["USDKRW"]["ticker"] == "KRW=X"

    assert ind["NASDAQ"]["status"] == "error"
    assert ind["NASDAQ"]["price"] is None
    assert ind["NASDAQ"]["change"] is None
    assert ind["NASDAQ"]["change_percent"] is None


def test_cache_prevents_refetch_within_ttl(monkeypatch):
    calls = []
    monkeypatch.setattr(indicators, "_fetch_quote", _fake_quote(calls))

    first = indicators.get_market_indicators(now=1000.0)
    second = indicators.get_market_indicators(now=1000.0 + 59)
    assert first["cached"] is False
    assert second["cached"] is True
    assert len(calls) == 3  # 두 번째 요청은 야후 호출 없음

    third = indicators.get_market_indicators(now=1000.0 + indicators.CACHE_TTL_SECONDS)
    assert third["cached"] is False
    assert len(calls) == 6


def test_fetch_quote_computes_change_from_last_two_closes(monkeypatch):
    import pandas as pd
    import yfinance as yf

    class FakeTicker:
        def __init__(self, t):
            pass

        def history(self, **kw):
            return pd.DataFrame({"Close": [2500.0, 2600.0, float("nan"), 2574.0]})

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    q = indicators._fetch_quote("^KS11")
    assert q == {"price": 2574.0, "change": -26.0, "change_percent": -1.0}
