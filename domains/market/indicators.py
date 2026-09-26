"""시장 지표 시세 수집 (코스피 / 나스닥 / 원·달러 환율) — yfinance(야후 파이낸스 비공식).

기획: 시장 데이터는 사주 엔진과 완전히 분리. 여기서는 시세 숫자만 가져오고 해석하지 않는다.

- 야후 비공식 엔드포인트 과호출 방지: 전체 결과를 메모리에 TTL(기본 60초) 캐싱.
  동시에 여러 요청이 들어와도 락으로 묶어 실제 fetch 는 한 번만 일어난다.
- 부분 실패 허용: 지표 하나가 실패해도 해당 지표만 status="error"(수치 null)로 내려가고
  나머지는 정상 반환한다. 실패 결과도 TTL 동안 캐싱해 장애 시 야후를 두드리지 않는다.
- 캐시는 프로세스 메모리 기준(워커별 독립) — 멀티 워커면 워커 수만큼 호출될 수 있음.
"""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional
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


def _fetch_quote(ticker: str) -> Dict[str, float]:
    """최근 종가 2개로 현재가/전일 대비 변동을 계산. 장중이면 마지막 봉이 당일 현재가다."""
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="5d", interval="1d", timeout=_FETCH_TIMEOUT_SECONDS)
    closes = hist["Close"].dropna() if hist is not None and "Close" in hist else []
    if len(closes) < 2:
        raise ValueError(f"시세 데이터 부족 ({len(closes)}개)")

    price = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])
    change = price - prev_close
    change_percent = (change / prev_close * 100) if prev_close else 0.0
    return {
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
    }


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
# 성공 결과는 날짜별로 캐싱(하루 1회 조회), 실패는 짧게만 캐싱해 재시도한다.
DIRECTION_TICKER = INDICATORS["KOSPI"]["ticker"]
_DIRECTION_ERROR_TTL_SECONDS = 300
_DIRECTION_CACHE_MAX_DAYS = 14

_direction_lock = threading.Lock()
_direction_cache: Dict[str, Dict[str, Any]] = {}  # target_date → {"data", "expires_at"(실패만)}


def _fetch_prev_session_change(target_date: str) -> Dict[str, Any]:
    import yfinance as yf

    hist = yf.Ticker(DIRECTION_TICKER).history(period="1mo", interval="1d", timeout=_FETCH_TIMEOUT_SECONDS)
    closes = hist["Close"].dropna() if hist is not None and "Close" in hist else []
    # target_date 당일 봉(장중 미완결일 수 있음)은 제외 — 직전 완결 거래일까지만 사용
    closes = [(ts.date(), float(v)) for ts, v in closes.items() if ts.date().isoformat() < target_date]
    if len(closes) < 2:
        raise ValueError(f"{target_date} 이전 종가 데이터 부족 ({len(closes)}개)")
    (_, prev_close), (session_date, close) = closes[-2], closes[-1]
    change_percent = (close - prev_close) / prev_close * 100 if prev_close else 0.0
    return {"session_date": session_date.isoformat(), "change_percent": round(change_percent, 2)}


def get_daily_market_direction(target_date: str, now: Optional[float] = None) -> Dict[str, Any]:
    """{'status': 'ok'|'error', 'change_percent', 'session_date'} — 방향 분류는 소비 측(wealth.engine)이 한다."""
    now = time.monotonic() if now is None else now
    with _direction_lock:
        hit = _direction_cache.get(target_date)
        if hit and (hit["expires_at"] is None or now < hit["expires_at"]):
            return hit["data"]

        try:
            data = {"status": "ok", **_fetch_prev_session_change(target_date)}
            expires_at = None
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
