from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.compatibility.service import analyze_compatibility_report

router = APIRouter()


class PersonSajuInput(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)


class CompatibilityRequest(BaseModel):
    person1: PersonSajuInput
    person2: PersonSajuInput
    relation_type: Optional[str] = Field("romantic", example="romantic")


@router.post("/analyze", summary="궁합 (60P) — 세부/종합 점수 + 8단계 한줄평")
def analyze_compatibility(request: CompatibilityRequest):
    try:
        data, is_fallback = analyze_compatibility_report(
            p1_info=request.person1.model_dump(),
            p2_info=request.person2.model_dump(),
            relation_type=request.relation_type or "romantic",
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"궁합 분석 실패: {str(e)}")
