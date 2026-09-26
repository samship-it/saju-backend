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
