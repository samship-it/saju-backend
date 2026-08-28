from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from domains.compatibility.service import analyze_compatibility_report

router = APIRouter()

class PersonSajuInput(BaseModel):
    year: int = Field(..., example=1990, description="출생연도")
    month: int = Field(..., example=5, description="출생월")
    day: int = Field(..., example=15, description="출생일")
    hour: Optional[int] = Field(0, example=14, description="출생시")
    minute: Optional[int] = Field(0, example=30, description="출생분")
    gender: Optional[str] = Field("female", example="female", description="성별 (male/female)")
    is_lunar: Optional[bool] = Field(False, example=False, description="음력 여부")

class CompatibilityRequest(BaseModel):
    person1: PersonSajuInput
    person2: PersonSajuInput
    relation_type: Optional[str] = Field("romantic", example="romantic", description="관계 유형 (romantic/business/friend)")

@router.post("/analyze", summary="두 사람의 사주 궁합 분석 (POST)")
async def analyze_compatibility(request: CompatibilityRequest):
    """
    두 사람의 사주 원국과 천간/지지 합·충 연산 결과를 기반으로 궁합 지수 및 리포트를 분석합니다.
    """
    try:
        result = analyze_compatibility_report(
            p1_info=request.person1.model_dump(),
            p2_info=request.person2.model_dump(),
            relation_type=request.relation_type
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"궁합 분석 실패: {str(e)}")