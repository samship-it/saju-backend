"""시장 지표 엔드포인트 — 실제 야후 호출 없이 캐시/부분실패 동작만 검증."""
import pytest
from fastapi.testclient import TestClient

import main
from domains.market import indicators
from domains.market.indicators import _fetch_prev_session_change as _real_prev_session

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


def test_null_daily_bar_uses_official_previous_close():
    """일봉에 10월 14일 종가가 없으면 그 날짜가 사라진다. 공식 전일 종가로 그 하루만 메운다."""
    from datetime import date

    merged = indicators.merge_official_close(
        [(date(2026, 10, 13), 6035.35), (date(2026, 10, 15), 5660.0)],
        price=5660.0,
        previous_close=6008.81,
        price_date=date(2026, 10, 15),
    )
    assert merged[-3:] == [
        (date(2026, 10, 13), 6035.35),
        (date(2026, 10, 14), 6008.81),
        (date(2026, 10, 15), 5660.0),
    ]


def test_holiday_without_a_bar_is_not_invented():
    from datetime import date

    merged = indicators.merge_official_close(
        [(date(2026, 10, 8), 6625.93), (date(2026, 10, 12), 6384.24)],
        price=6384.24,
        previous_close=6625.93,
        price_date=date(2026, 10, 12),
    )
    assert [day for day, _ in merged] == [date(2026, 10, 8), date(2026, 10, 12)]


def test_quote_uses_spot_previous_close_when_history_has_dates(monkeypatch):
    import pandas as pd
    import yfinance as yf
    from datetime import date

    idx = pd.to_datetime(["2026-10-13", "2026-10-15"]).tz_localize("Asia/Seoul")

    class FakeTicker:
        def __init__(self, t):
            pass

        def history(self, **kw):
            return pd.DataFrame({"Close": [6035.35, 5660.0]}, index=idx)

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    monkeypatch.setattr(
        indicators, "_spot_quote",
        lambda ticker: {"price": 5660.0, "prev": 6008.81, "price_date": date(2026, 10, 15)},
    )
    quote = indicators._fetch_quote("^KS11")
    assert quote["price"] == 5660.0
    assert quote["session_date"] == "2026-10-15"
    assert quote["change"] == round(5660.0 - 6008.81, 2)
    assert quote["change_percent"] == round((5660.0 - 6008.81) / 6008.81 * 100, 2)


def test_prev_session_fills_missing_close(monkeypatch):
    import pandas as pd
    import yfinance as yf
    from datetime import date

    idx = pd.to_datetime(["2026-10-13", "2026-10-15"]).tz_localize("Asia/Seoul")

    class FakeTicker:
        def __init__(self, t):
            pass

        def history(self, **kw):
            return pd.DataFrame({"Close": [6035.35, 5660.0]}, index=idx)

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    monkeypatch.setattr(
        indicators, "_spot_quote",
        lambda ticker: {"price": 5660.0, "prev": 6008.81, "price_date": date(2026, 10, 15)},
    )
    filled = _real_prev_session("2026-10-15")
    assert filled["session_date"] == "2026-10-14"
    assert filled["change_percent"] == round((6008.81 - 6035.35) / 6035.35 * 100, 2)


def test_unfilled_gap_retries_instead_of_sticking(monkeypatch):
    """일봉 구멍을 메우기 전에는 10월 13일 값을 하루 종일 고정하지 않는다."""
    calls = {"n": 0}

    def fake(target_date, ticker=None):
        calls["n"] += 1
        # 조회 1회 = 나스닥 + 환율. 첫 쌍이 구멍이면 짧게만 유지하고, TTL 뒤 다시 받는다.
        if calls["n"] <= 2:
            return {"session_date": "2026-10-13", "change_percent": -5.46, "gap_unfilled": True}
        return {"session_date": "2026-10-14", "change_percent": -0.44}

    monkeypatch.setattr(indicators, "_fetch_prev_session_change", fake)
    first = indicators.get_daily_market_direction("2026-10-15", now=0)
    held = indicators.get_daily_market_direction("2026-10-15", now=10)
    assert first["session_date"] == "2026-10-13"
    assert held["session_date"] == "2026-10-13"
    assert calls["n"] == 2
    refreshed = indicators.get_daily_market_direction("2026-10-15", now=301)
    assert refreshed["session_date"] == "2026-10-14"
    assert calls["n"] == 4


def test_history_hole_without_spot_is_not_cached_as_final(monkeypatch):
    import pandas as pd
    import yfinance as yf

    idx = pd.to_datetime(["2026-10-12", "2026-10-13", "2026-10-15"]).tz_localize("Asia/Seoul")

    class FakeTicker:
        def __init__(self, t):
            pass

        def history(self, **kw):
            return pd.DataFrame({"Close": [6384.24, 6035.35, 5660.0]}, index=idx)

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    monkeypatch.setattr(indicators, "_spot_quote", lambda ticker: None)
    gap = _real_prev_session("2026-10-15")
    assert gap["session_date"] == "2026-10-13"
    assert gap["gap_unfilled"] is True
