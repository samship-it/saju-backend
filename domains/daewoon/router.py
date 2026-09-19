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
    target: Optional[str] = Field(
        "me", example="me", description="'me' | 'partner' — 어떤 birth 데이터인지 표시용(계산에는 안 씀).",
    )
    target_age: Optional[int] = Field(
        None, example=32, ge=0, le=130,
        description="확인하고 싶은 나이. 미지정 시 현재 실제 나이 기준 대운으로 계산.",
    )
    love_status: Optional[str] = Field(
        None, example="dating",
        description="'single'|'dating'|'married' — 현재 대운을 볼 때만 relationship.guide_by_status 에 반영.",
    )


@router.post("/analysis", summary="10년 대운 (평생운세와 별개의 독립 모듈, 유료)")
def daewoon_period_endpoint(req: DaewoonPeriodRequest):
    try:
        data, is_fallback = analyze_daewoon_period(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar),
            target_age=req.target_age, target=req.target or "me", love_status=req.love_status,
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"10년 대운 분석 실패: {str(e)}")
