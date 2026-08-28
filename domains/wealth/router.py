from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from domains.wealth.service import analyze_wealth_and_market_strategy

router = APIRouter()

class SajuWealthRequest(BaseModel):
    year: int = Field(..., example=1990, description="출생연도")
    month: int = Field(..., example=5, description="출생월")
    day: int = Field(..., example=15, description="출생일")
    hour: Optional[int] = Field(0, example=14, description="출생시 (0~23)")
    minute: Optional[int] = Field(0, example=30, description="출생분 (0~59)")
    gender: Optional[str] = Field("female", example="female", description="성별 (male/female)")
    is_lunar: Optional[bool] = Field(False, example=False, description="음력 여부")
    market_context: Optional[str] = Field(
        "US Tech Stocks & Semiconductor ETFs", 
        example="US Tech Stocks & Semiconductor ETFs", 
        description="관심 시장/종목 문맥"
    )

@router.post("/analysis", summary="재테크 및 시장 결합 운세 분석 (POST)")
async def analyze_wealth_post(request: SajuWealthRequest):
    """
    사용자의 사주 재물운과 시장 상황을 결합한 투자 성향 및 리스크 관리 전략을 분석합니다.
    """
    try:
        result = analyze_wealth_and_market_strategy(
            year=request.year,
            month=request.month,
            day=request.day,
            hour=request.hour,
            minute=request.minute,
            gender=request.gender,
            is_lunar=request.is_lunar,
            market_context=request.market_context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재물 및 시장 분석 실패: {str(e)}")

@router.get("/analysis", summary="재테크 및 시장 결합 운세 분석 (GET)")
async def analyze_wealth_get(
    year: int = Query(..., description="출생연도"),
    month: int = Query(..., description="출생월"),
    day: int = Query(..., description="출생일"),
    hour: int = Query(0, description="출생시"),
    minute: int = Query(0, description="출생분"),
    gender: str = Query("female", description="성별"),
    is_lunar: bool = Query(False, description="음력 여부"),
    market_context: str = Query("US Tech Stocks & Semiconductor ETFs", description="관심 시장")
):
    """
    쿼리 파라미터를 이용한 재테크 및 자산운용 전략 분석 엔드포인트입니다.
    """
    try:
        result = analyze_wealth_and_market_strategy(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            gender=gender,
            is_lunar=is_lunar,
            market_context=market_context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재물 및 시장 분석 실패: {str(e)}")