from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from domains.comprehensive.service import generate_comprehensive_report

router = APIRouter()

class SajuComprehensiveRequest(BaseModel):
    year: int = Field(..., example=1990, description="출생연도")
    month: int = Field(..., example=5, description="출생월")
    day: int = Field(..., example=15, description="출생일")
    hour: Optional[int] = Field(0, example=14, description="출생시 (0~23)")
    minute: Optional[int] = Field(0, example=30, description="출생분 (0~59)")
    gender: Optional[str] = Field("female", example="female", description="성별 (male/female)")
    is_lunar: Optional[bool] = Field(False, example=False, description="음력 여부")
    target_year: Optional[int] = Field(2026, example=2026, description="분석할 연도")

@router.post("/report", summary="5대 종합 운세 리포트 분석 (POST)")
async def get_comprehensive_report_post(request: SajuComprehensiveRequest):
    """
    사용자의 사주 정보를 기반으로 연도별 총운 및 5대 영역 종합 운세를 생성합니다.
    """
    try:
        result = generate_comprehensive_report(
            year=request.year,
            month=request.month,
            day=request.day,
            hour=request.hour,
            minute=request.minute,
            gender=request.gender,
            is_lunar=request.is_lunar,
            target_year=request.target_year
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종합 운세 생성 실패: {str(e)}")

@router.get("/report", summary="5대 종합 운세 리포트 분석 (GET)")
async def get_comprehensive_report_get(
    year: int = Query(..., description="출생연도"),
    month: int = Query(..., description="출생월"),
    day: int = Query(..., description="출생일"),
    hour: int = Query(0, description="출생시"),
    minute: int = Query(0, description="출생분"),
    gender: str = Query("female", description="성별"),
    is_lunar: bool = Query(False, description="음력 여부"),
    target_year: int = Query(2026, description="분석할 연도")
):
    """
    쿼리 파라미터를 이용한 종합 운세 조회 엔드포인트입니다.
    """
    try:
        result = generate_comprehensive_report(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            gender=gender,
            is_lunar=is_lunar,
            target_year=target_year
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종합 운세 생성 실패: {str(e)}")