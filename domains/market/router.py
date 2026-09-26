from fastapi import APIRouter

from domains.market.indicators import get_market_indicators

router = APIRouter()


@router.get("/market-indicators", summary="시장 지표 (코스피/나스닥/원달러) — 60초 캐시")
def market_indicators():
    # 개별 지표 실패는 서비스에서 status="error" 로 흡수하므로 여기서는 500 이 나지 않는다.
    return {"status": "success", **get_market_indicators()}
