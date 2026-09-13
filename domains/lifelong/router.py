from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.lifelong.service import analyze_lifelong_fortune

router = APIRouter()


class LifelongFortuneRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)


@router.post("/analysis", summary="평생운세 (원국+대운 흐름 종합, 250P)")
def lifelong_analysis_endpoint(req: LifelongFortuneRequest):
    try:
        data, is_fallback = analyze_lifelong_fortune(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar),
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"평생운세 분석 실패: {str(e)}")
