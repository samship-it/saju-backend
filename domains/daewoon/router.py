from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.daewoon.service import analyze_daewoon_period

router = APIRouter()


class DaewoonPeriodRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)
    step: Optional[int] = Field(
        None, example=4, ge=1, le=8,
        description="대운 순번(1~8). 미지정 시 현재 나이 기준 대운으로 계산.",
    )


@router.post("/analysis", summary="10년 대운 (평생운세 '자세히 보기' 완전 이관, 유료)")
def daewoon_period_endpoint(req: DaewoonPeriodRequest):
    try:
        data, is_fallback = analyze_daewoon_period(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar), step=req.step,
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"10년 대운 분석 실패: {str(e)}")
