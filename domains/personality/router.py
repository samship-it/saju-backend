from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from domains.personality.service import analyze_personality_and_talent

router = APIRouter()

class SajuPersonalityRequest(BaseModel):
    year: int = Field(..., example=1990, description="출생연도")
    month: int = Field(..., example=5, description="출생월")
    day: int = Field(..., example=15, description="출생일")
    hour: Optional[int] = Field(0, example=14, description="출생시 (0~23)")
    minute: Optional[int] = Field(0, example=30, description="출생분 (0~59)")
    gender: Optional[str] = Field("female", example="female", description="성별 (male/female)")
    is_lunar: Optional[bool] = Field(False, example=False, description="음력 여부")

@router.post("/analyze", summary="성격 및 적성 분석 (POST)")
async def analyze_personality_post(request: SajuPersonalityRequest):
    """
    사용자의 사주 정보를 기반으로 성격, 기질, 장단점, 적성 및 추천 직업을 분석합니다.
    """
    try:
        result = analyze_personality_and_talent(
            year=request.year,
            month=request.month,
            day=request.day,
            hour=request.hour,
            minute=request.minute,
            gender=request.gender,
            is_lunar=request.is_lunar
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성격 및 적성 분석 실패: {str(e)}")

@router.get("/analyze", summary="성격 및 적성 분석 (GET)")
async def analyze_personality_get(
    year: int = Query(..., description="출생연도"),
    month: int = Query(..., description="출생월"),
    day: int = Query(..., description="출생일"),
    hour: int = Query(0, description="출생시"),
    minute: int = Query(0, description="출생분"),
    gender: str = Query("female", description="성별"),
    is_lunar: bool = Query(False, description="음력 여부")
):
    """
    쿼리 파라미터를 이용한 성격 및 적성 분석 엔드포인트입니다.
    """
    try:
        result = analyze_personality_and_talent(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            gender=gender,
            is_lunar=is_lunar
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성격 및 적성 분석 실패: {str(e)}")