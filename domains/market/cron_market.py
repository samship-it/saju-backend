"""오늘의 시장 요약 제공 모듈.

외부 금융 데이터 연동(크론 수집)이 붙기 전까지 사용하는 스텁이다.
`core.database.MarketSummary` 테이블에 당일 요약이 저장돼 있으면 그것을 쓰고,
없으면 중립적 기본 문구를 반환한다. 외부 API를 직접 호출하지 않는다.
"""
import logging

logger = logging.getLogger(__name__)

_NEUTRAL_SUMMARY = (
    "오늘의 시장 데이터는 아직 연동되지 않았습니다. "
    "특정 시황을 가정하지 말고, 사주 원국 흐름을 중심으로 재물/투자운을 해석하세요."
)


def get_today_market_summary(target_date: str) -> str:
    """target_date(YYYY-MM-DD) 기준 시장 요약 텍스트를 반환한다."""
    try:
        from core.database import db_session, MarketSummary

        row = (
            db_session.query(MarketSummary)
            .filter_by(target_date=target_date)
            .first()
        )
        if row and row.summary_text:
            return row.summary_text
    except Exception as e:  # 테이블 미생성 등은 조용히 폴백
        logger.debug(f"market summary 조회 실패, 기본 문구 사용: {e}")

    return _NEUTRAL_SUMMARY
