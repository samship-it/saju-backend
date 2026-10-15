"""시장 지표 시세 수집 (코스피 / 나스닥 / 원·달러 환율) — yfinance(야후 파이낸스 비공식).

기획: 시장 데이터는 사주 엔진과 완전히 분리. 여기서는 시세 숫자만 가져오고 해석하지 않는다.

- 야후 비공식 엔드포인트 과호출 방지: 전체 결과를 메모리에 TTL(기본 60초) 캐싱.
  동시에 여러 요청이 들어와도 락으로 묶어 실제 fetch 는 한 번만 일어난다.
- 부분 실패 허용: 지표 하나가 실패해도 해당 지표만 status="error"(수치 null)로 내려가고
  나머지는 정상 반환한다. 실패 결과도 TTL 동안 캐싱해 장애 시 야후를 두드리지 않는다.
- 캐시는 프로세스 메모리 기준(워커별 독립) — 멀티 워커면 워커 수만큼 호출될 수 있음.
"""
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

# 응답 키 → (표시명, 야후 티커)
INDICATORS: Dict[str, Dict[str, str]] = {
    "KOSPI": {"name": "코스피", "ticker": "^KS11"},
    "NASDAQ": {"name": "나스닥", "ticker": "^IXIC"},
    "USDKRW": {"name": "원/달러 환율", "ticker": "KRW=X"},
}

CACHE_TTL_SECONDS = max(60, int(os.environ.get("MARKET_CACHE_TTL_SECONDS", "60")))
_FETCH_TIMEOUT_SECONDS = 10

_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {"data": None, "expires_at": 0.0}


def _previous_weekday(day: date) -> date:
    cursor = day - timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def _same_price(left: float, right: float) -> bool:
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) / scale < 1e-4


def _history_closes(ticker: str) -> List[Tuple[Optional[date], float]]:
    """일봉 종가. 날짜가 없으면 (None, 가격) — 테스트용 무날짜 시계열도 그대로 받는다.

    야후 일봉은 직전 거래일 종가가 null 인 채로 오는 날이 있다. pandas/yfinance 가
    그 행을 통째로 버려서, 날짜 목록만 보면 그 거래일이 없었던 것처럼 보인다.
    """
    import pandas as pd
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="1mo", interval="1d", timeout=_FETCH_TIMEOUT_SECONDS)
    if hist is None or "Close" not in getattr(hist, "columns", []):
        return []
    dated = isinstance(hist.index, pd.DatetimeIndex)
    out: List[Tuple[Optional[date], float]] = []
    for ts, value in hist["Close"].items():
        if value != value:  # NaN
            continue
        day = ts.date() if dated else None
        out.append((day, float(value)))
    return out


def _spot_quote(ticker: str) -> Optional[Dict[str, Any]]:
    """지금 가격과 직전 거래 종가. 일봉에 구멍이 있어도 chartPreviousClose 는 채워져 있다.

    반환: {'price', 'prev', 'price_date'} — price_date 는 그 거래소 시간대의 날짜.
    """
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + quote(ticker, safe="")
        + "?range=1d&interval=1d&includePrePost=false"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return None
        meta = result[0].get("meta") or {}
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose")
        if prev is None:
            prev = meta.get("previousClose")
        market_time = meta.get("regularMarketTime")
        if price is None or prev is None or not market_time:
            return None
        tz = ZoneInfo(meta.get("exchangeTimezoneName") or "Asia/Seoul")
        return {
            "price": float(price),
            "prev": float(prev),
            "price_date": datetime.fromtimestamp(int(market_time), tz).date(),
        }
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"야후 현재가 조회 실패 ({ticker}): {e}")
        return None


def merge_official_close(
    sessions: List[Tuple[date, float]],
    *,
    price: Optional[float],
    previous_close: Optional[float],
    price_date: Optional[date],
) -> List[Tuple[date, float]]:
    """일봉이 건너뛴 직전 거래일을 공식 전일 종가로 한 칸 메운다.

    휴장일이라 봉 자체가 없는 경우는 메우지 않는다(전일 종가가 이미 가진 마지막 봉과 같다).
    당일 가격은 공식 현재가로 덮어써서 장중 시세가 하루 전 종가에 머물지 않게 한다.
    """
    ordered: Dict[date, float] = {day: close for day, close in sessions}
    if price_date is not None and previous_close is not None:
        missing = _previous_weekday(price_date)
        if missing not in ordered:
            earlier = [day for day in ordered if day < missing]
            if earlier and _previous_weekday(missing) == max(earlier):
                if not _same_price(ordered[max(earlier)], previous_close):
                    ordered[missing] = float(previous_close)
        if price is not None:
            ordered[price_date] = float(price)
    return sorted(ordered.items())


def _quote_from_closes(price: float, prev_close: float) -> Dict[str, float]:
    change = price - prev_close
    change_percent = (change / prev_close * 100) if prev_close else 0.0
    return {
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
    }


def _fetch_quote(ticker: str) -> Dict[str, Any]:
    """현재가와 직전 거래 종가 대비 등락.

    거래소 날짜가 있는 시계열이면 야후 현재가(regularMarketPrice / chartPreviousClose)를 쓴다.
    일봉 Close 가 null 이라 하루가 통째로 빠져도 전일 종가를 건너뛰지 않는다.
    """
    closes = _history_closes(ticker)
    if len(closes) < 2:
        raise ValueError(f"시세 데이터 부족 ({len(closes)}개)")

    if closes[0][0] is not None:
        spot = _spot_quote(ticker)
        if spot and spot.get("price") is not None and spot.get("prev"):
            quote = _quote_from_closes(float(spot["price"]), float(spot["prev"]))
            quote["session_date"] = spot["price_date"].isoformat()
            return quote

    return _quote_from_closes(closes[-1][1], closes[-2][1])


def _build_indicator(key: str) -> Dict[str, Any]:
    meta = INDICATORS[key]
    base = {"name": meta["name"], "ticker": meta["ticker"]}
    try:
        return {**base, **_fetch_quote(meta["ticker"]), "status": "ok"}
    except Exception as e:
        logger.warning(f"시장 지표 조회 실패 {key}({meta['ticker']}): {e}")
        return {
            **base,
            "price": None,
            "change": None,
            "change_percent": None,
            "status": "error",
            "error": "시세를 불러오지 못했습니다.",
        }


def _fetch_all() -> Dict[str, Any]:
    keys = list(INDICATORS)
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        results = list(pool.map(_build_indicator, keys))
    return {
        "fetched_at": datetime.now(KST).isoformat(timespec="seconds"),
        "indicators": dict(zip(keys, results)),
    }


def get_market_indicators(now: Optional[float] = None) -> Dict[str, Any]:
    """{'fetched_at', 'cached', 'indicators': {KOSPI, NASDAQ, USDKRW}}. 절대 예외를 던지지 않는다."""
    now = time.monotonic() if now is None else now
    with _cache_lock:
        if _cache["data"] is not None and now < _cache["expires_at"]:
            return {**_cache["data"], "cached": True}

        data = _fetch_all()
        _cache["data"] = data
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return {**data, "cached": False}


def clear_cache() -> None:
    with _cache_lock:
        _cache["data"] = None
        _cache["expires_at"] = 0.0


# ───────────────────────── 재테크 운세용: 하루 고정 시장 방향 ─────────────────────────
# "같은 날 아침과 저녁의 운세가 달라지면 안 된다" — 장중 실시간 등락이 아니라
# target_date(KST) 이전의 '마지막 완결 거래일' 종가 대비 등락률을 쓴다.
# 과거 종가로만 계산하므로 재시작·워커가 달라도 같은 날엔 항상 같은 값이 나온다.
# 직전 거래일까지 메워진 성공 결과만 그날 고정한다.
# 야후 일봉이 비어 아직 전전 거래일에 머무르면 짧게만 캐싱하고 다시 받는다.
DIRECTION_TICKER = INDICATORS["KOSPI"]["ticker"]
_DIRECTION_ERROR_TTL_SECONDS = 300
_DIRECTION_CACHE_MAX_DAYS = 14

_direction_lock = threading.Lock()
_direction_cache: Dict[str, Dict[str, Any]] = {}  # target_date → {"data", "expires_at"(실패만)}


def _single_weekday_hole(days: List[date], anchor: date) -> bool:
    """anchor 직전 평일 하루만 비어 있으면 True. 휴장으로 여러 날이 빈 경우는 False."""
    missing = _previous_weekday(anchor)
    if missing in days:
        return False
    return _previous_weekday(missing) in days


def _fetch_prev_session_change(target_date: str) -> Dict[str, Any]:
    closes = [(day, price) for day, price in _history_closes(DIRECTION_TICKER) if day is not None]
    spot = _spot_quote(DIRECTION_TICKER)
    anchor = spot.get("price_date") if spot else (closes[-1][0] if closes else None)
    previous_close = spot.get("prev") if spot else None
    if spot:
        closes = merge_official_close(
            closes,
            price=spot.get("price"),
            previous_close=previous_close,
            price_date=spot.get("price_date"),
        )
    # 일봉이 하루만 비었는데 공식 종가로 메우지 못하면, 그 결과를 하루 종일 고정하지 않는다.
    gap_unfilled = False
    if anchor is not None and _single_weekday_hole([day for day, _ in closes], anchor):
        missing = _previous_weekday(anchor)
        earlier = [price for day, price in closes if day < missing]
        gap_unfilled = previous_close is None or not earlier or not _same_price(earlier[-1], previous_close)
    # target_date(KST) 당일 봉은 장중일 수 있어 제외 — 직전 완결 거래일까지만 사용
    closes = [(day, price) for day, price in closes if day.isoformat() < target_date]
    if len(closes) < 2:
        raise ValueError(f"{target_date} 이전 종가 데이터 부족 ({len(closes)}개)")
    (_, prev_close), (session_date, close) = closes[-2], closes[-1]
    change_percent = (close - prev_close) / prev_close * 100 if prev_close else 0.0
    result = {"session_date": session_date.isoformat(), "change_percent": round(change_percent, 2)}
    if gap_unfilled:
        result["gap_unfilled"] = True
    return result


def get_daily_market_direction(target_date: str, now: Optional[float] = None) -> Dict[str, Any]:
    """{'status': 'ok'|'error', 'change_percent', 'session_date'} — 방향 분류는 소비 측(wealth.engine)이 한다."""
    now = time.monotonic() if now is None else now
    with _direction_lock:
        hit = _direction_cache.get(target_date)
        if hit and (hit["expires_at"] is None or now < hit["expires_at"]):
            return hit["data"]

        try:
            fetched = _fetch_prev_session_change(target_date)
            # 빈 거래일을 메운 값만 그날 고정한다. 아직 구멍이 있으면 짧게 다시 받는다.
            gap_unfilled = bool(fetched.pop("gap_unfilled", False))
            data = {"status": "ok", **fetched}
            expires_at = now + _DIRECTION_ERROR_TTL_SECONDS if gap_unfilled else None
        except Exception as e:
            logger.warning(f"재테크 시장 방향 조회 실패 ({DIRECTION_TICKER}, {target_date}): {e}")
            data = {"status": "error", "change_percent": None, "session_date": None}
            expires_at = now + _DIRECTION_ERROR_TTL_SECONDS

        _direction_cache[target_date] = {"data": data, "expires_at": expires_at}
        if len(_direction_cache) > _DIRECTION_CACHE_MAX_DAYS:
            for old in sorted(_direction_cache)[: len(_direction_cache) - _DIRECTION_CACHE_MAX_DAYS]:
                _direction_cache.pop(old, None)
        return data


def clear_direction_cache() -> None:
    with _direction_lock:
        _direction_cache.clear()
