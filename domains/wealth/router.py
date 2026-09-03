from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.wealth.service import analyze_daily_finance

router = APIRouter()


class DailyFinanceRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)
    target_date: Optional[str] = Field(None, example="2026-09-03")


@router.post("/analysis", summary="오늘의 재테크 사주 (DAILY)")
def analyze_wealth_post(request: DailyFinanceRequest):
    try:
        result, is_fallback = analyze_daily_finance(
            year=request.year, month=request.month, day=request.day,
            hour=request.hour, minute=request.minute or 0,
            gender=request.gender or "female", is_lunar=bool(request.is_lunar),
            target_date=request.target_date,
        )
        return {"status": "success", "is_fallback": is_fallback, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재테크 사주 분석 실패: {str(e)}")
