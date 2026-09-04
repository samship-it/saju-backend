import datetime
import traceback
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import KST, API_SECRET_KEY
from core.saju_base import calculate_saju
from domains.daily.content_db import make_key
from domains.daily.service import generate_daily_fortune
from shared.public import person_summary

router = APIRouter()


class DailyFortuneRequest(BaseModel):
    user_id: str
    year: int
    month: int
    day: int
    hour: Optional[int] = None          # None = 출생시간 미상
    minute: Optional[int] = 0
    gender: Optional[str] = "female"
    is_lunar: Optional[bool] = False
    target_date: Optional[str] = None    # 미지정 시 오늘(KST)


@router.post("/fortune", summary="오늘의 운세 (DAILY_FORTUNE)")
def get_daily_fortune_endpoint(req: DailyFortuneRequest, x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    try:
        if req.target_date:
            t_date = datetime.datetime.strptime(req.target_date, "%Y-%m-%d").date()
        else:
            t_date = datetime.datetime.now(KST).date()
        target_date_str = t_date.strftime("%Y-%m-%d")

        saju_data = calculate_saju(
            req.year, req.month, req.day, req.hour, req.minute,
            gender=req.gender or "female", is_lunar=bool(req.is_lunar), target_date=t_date,
        )
        derived = saju_data.get("derived", {})

        day_ganji = saju_data.get("day_ganji") or ""
        iljin_ganji = (saju_data.get("today_ganji") or {}).get("day") or ""

        base_response = {
            "status": "success",
            "target_date": target_date_str,
            "birth_time_known": saju_data.get("birth_time_known"),
            "saju_info": person_summary(saju_data),
            "active_elements": derived.get("active_elements"),
            "score_components": derived.get("score_components"),
            "combo_key": make_key(day_ganji, iljin_ganji),  # 내 일주_오늘 일진
        }

        # 사전 생성 정적 DB(daily_db.json)에서 (내 일주 × 오늘 일진) 키로 즉시 조회.
        fortune_result, is_fallback = generate_daily_fortune(saju_data)

        return {**base_response, "cached": not is_fallback, "is_fallback": is_fallback, "data": fortune_result}

    except HTTPException:
        raise
    except Exception as e:
        print("====== daily 에러 ======")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"내부 로직 에러: {str(e)}")
