from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.personality.service import analyze_character, analyze_aptitude

router = APIRouter()


class PersonalitySajuRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)


@router.post("/character", summary="나의 성격 (원국 중심, 30P)")
def character_endpoint(req: PersonalitySajuRequest):
    try:
        data, is_fallback = analyze_character(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar),
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성격 분석 실패: {str(e)}")


@router.post("/aptitude", summary="나의 적성 (원국 중심, 30P)")
def aptitude_endpoint(req: PersonalitySajuRequest):
    try:
        data, is_fallback = analyze_aptitude(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar),
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"적성 분석 실패: {str(e)}")
