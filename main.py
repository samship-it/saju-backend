import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from saju_engine import SajuEngine
from ai_service import get_ai_fortune_interpretation

app = FastAPI(title="Saju Engine API with Gemini AI", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request DTO
class DailyFinanceRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: Optional[int] = 0
    minute: Optional[int] = 0
    gender: str
    analysis_type: Optional[str] = "finance"

@app.get("/")
def read_root():
    return {"status": "online", "message": "Saju Engine API Server is running!"}

@app.post("/api/finance-fortune")
def get_finance_fortune(request: DailyFinanceRequest):
    try:
        # 1. saju_engine.py 규격에 맞게 user_saju Dict 구성
        user_saju = {
            'birth_year': request.year,
            'ten_stars_strength': {'정재': 20, '편재': 30}  # 기본 연산 데이터
        }
        
        # 2. SajuEngine 인스턴스 생성 (user_saju 전달)
        engine = SajuEngine(user_saju)
        
        # 3. Today Data 구성 및 calculate_daily_finance 호출
        today_data = {
            'today_ten_star': '편재'
        }
        engine_result = engine.calculate_daily_finance(today_data)
        
        # 4. Gemini AI 연동하여 해석 생성
        ai_interpretation = get_ai_fortune_interpretation(
            analysis_type=request.analysis_type,
            engine_data=engine_result
        )
        
        return {
            "status": "success",
            "engine_data": engine_result,
            "interpretation": ai_interpretation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
