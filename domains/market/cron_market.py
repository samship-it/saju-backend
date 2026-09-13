"""시장 데이터 모듈 (KOSPI / NASDAQ / BTC).

기획: 시장 데이터는 사주 엔진과 완전히 분리. Python이 '주가가 오른다/내린다'를 예측하지 않는다.
외부 금융 API 연동(크론 수집) 전까지는 DB에 저장된 당일 스냅샷을 쓰고, 없으면 중립 스텁을 반환한다.

`is_live` = 지금 이 순간 한국거래소(KRX) 정규장이 열려 있는지(KST 기준, 평일 09:00~15:30).
서버가 어느 타임존에서 돌든 결과가 같도록 항상 Asia/Seoul 로 변환해서 판정한다.
⚠️ 공휴일 캘린더는 아직 반영하지 않음(평일·시간대만 판정) — 알려진 한계.
"""
import logging
from datetime import datetime, time as dtime
from typing import Dict, Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
_MARKET_OPEN = dtime(9, 0)
_MARKET_CLOSE = dtime(15, 30)

_NEUTRAL_POINT = (
    "오늘 시장 데이터는 아직 연동되지 않았습니다. 특정 시황을 단정하지 말고, "
    "변동성 관리와 개인 자금 흐름 중심으로 해석하세요."
)
_CLOSED_MARKET_POINT = "현재 휴장입니다. 차분한 자금 점검이 필요한 시점입니다."


def is_market_open_now() -> bool:
    """지금(KST) 이 순간 KRX 정규장 시간대인지. 주말·장외 시간은 False(공휴일 미반영)."""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 5=토, 6=일
        return False
    return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


def get_market_snapshot(target_date: str) -> Dict[str, Any]:
    """{'target_date', 'indices': {KOSPI, NASDAQ, BTC}, 'market_point', 'is_live'}.

    is_live=False(휴장)면 market_point 는 항상 고정 문구다(AI가 덮어쓰지 않음 — service.py 참고).
    """
    is_live = is_market_open_now()
    if not is_live:
        return {
            "target_date": target_date,
            "indices": {"KOSPI": None, "NASDAQ": None, "BTC": None},
            "market_point": _CLOSED_MARKET_POINT,
            "is_live": False,
        }

    try:
        from core.database import db_session, MarketSummary

        row = db_session.query(MarketSummary).filter_by(target_date=target_date).first()
        if row and row.summary_text:
            return {
                "target_date": target_date,
                "indices": {"KOSPI": None, "NASDAQ": None, "BTC": None},
                "market_point": row.summary_text,
                "is_live": True,
            }
    except Exception as e:
        logger.debug(f"market snapshot 조회 실패: {e}")

    return {
        "target_date": target_date,
        "indices": {"KOSPI": None, "NASDAQ": None, "BTC": None},
        "market_point": _NEUTRAL_POINT,
        "is_live": True,
    }


def get_today_market_summary(target_date: str) -> str:
    """레거시 호환."""
    return get_market_snapshot(target_date)["market_point"]
