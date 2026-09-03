"""시장 데이터 모듈 (KOSPI / NASDAQ / BTC).

기획: 시장 데이터는 사주 엔진과 완전히 분리. Python이 '주가가 오른다/내린다'를 예측하지 않는다.
외부 금융 API 연동(크론 수집) 전까지는 DB에 저장된 당일 스냅샷을 쓰고, 없으면 중립 스텁을 반환한다.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_NEUTRAL_POINT = (
    "오늘 시장 데이터는 아직 연동되지 않았습니다. 특정 시황을 단정하지 말고, "
    "변동성 관리와 개인 자금 흐름 중심으로 해석하세요."
)


def get_market_snapshot(target_date: str) -> Dict[str, Any]:
    """{'target_date', 'indices': {KOSPI, NASDAQ, BTC}, 'market_point', 'is_live'}."""
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
        "is_live": False,
    }


def get_today_market_summary(target_date: str) -> str:
    """레거시 호환."""
    return get_market_snapshot(target_date)["market_point"]
