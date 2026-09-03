"""운세 결과 캐시 전체 삭제.

로컬:   python scripts/clear_cache.py
운영:   DATABASE_URL=postgresql://... python scripts/clear_cache.py

market_summary(시장 데이터)는 캐시가 아니므로 --all 을 줘야 함께 삭제된다.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db_session, DailyFortuneCache, FortuneCache, MarketSummary, init_db  # noqa: E402


def main() -> None:
    init_db()
    wipe_market = "--all" in sys.argv

    before = {
        "daily_fortune_cache": db_session.query(DailyFortuneCache).count(),
        "fortune_cache": db_session.query(FortuneCache).count(),
        "market_summary": db_session.query(MarketSummary).count(),
    }
    print(f"삭제 전: {before}")

    d1 = db_session.query(DailyFortuneCache).delete()
    d2 = db_session.query(FortuneCache).delete()
    d3 = db_session.query(MarketSummary).delete() if wipe_market else 0
    db_session.commit()

    print(f"삭제됨: daily_fortune_cache={d1}, fortune_cache={d2}, market_summary={d3}")
    print("완료. 다음 요청부터 새로 계산됩니다.")


if __name__ == "__main__":
    main()
