import datetime
import hashlib
import traceback
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

from config import KST, API_SECRET_KEY
from database import db_session, DailyFortuneCache
from core.saju_base import calculate_saju
from domains.daily.service import generate_daily_fortune
from domains.market.cron_market import get_today_market_summary

router = APIRouter(prefix="/api/v1/fortune/daily", tags=["Daily Fortune"])

class DailyFortuneRequest(BaseModel):
    user_id: str
    year: int
    month: int
    day: int
    hour: Optional[int] = None
    minute: Optional[int] = 0
    gender: Optional[str] = "female"
    target_date: Optional[str] = None

@router.post("")
def get_daily_fortune_endpoint(req: DailyFortuneRequest, x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    try:
        if req.target_date:
            t_date = datetime.datetime.strptime(req.target_date, "%Y-%m-%d").date()
            target_date_str = req.target_date
        else:
            t_date = datetime.datetime.now(KST).date()
            target_date_str = t_date.strftime("%Y-%m-%d")

        birth_str = f"{req.year}-{req.month}-{req.day}-{req.hour or 'none'}-{req.minute or 0}-{req.gender}"
        birth_hash = hashlib.md5(birth_str.encode()).hexdigest()[:8]
        cache_key = f"{req.user_id}_{target_date_str}_{birth_hash}"

        cached = db_session.query(DailyFortuneCache).filter_by(cache_key=cache_key).first()
        if cached:
            return {"status": "success", "cached": True, "is_fallback": False, "data": cached.fortune_json}

        saju_data = calculate_saju(req.year, req.month, req.day, req.hour, req.minute, req.gender or "female", t_date)
        market_summary = get_today_market_summary(target_date_str)
        fortune_result, is_fallback = generate_daily_fortune(saju_data, market_summary)

        if not is_fallback:
            db_session.add(DailyFortuneCache(cache_key=cache_key, fortune_json=fortune_result))
            db_session.commit()

        return {"status": "success", "cached": False, "is_fallback": is_fallback, "saju_info": saju_data, "data": fortune_result}

    except Exception as e:
        error_msg = traceback.format_exc()
        print("====== 상세 에러 발생 ======")
        print(error_msg)
        raise HTTPException(status_code=500, detail=f"내부 로직 에러: {str(e)}")