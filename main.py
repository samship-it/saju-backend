# main.py

import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from saju_engine import SajuEngine
from ai_service import get_ai_fortune_interpretation

app = FastAPI(
    title="Saju Engine API with Gemini AI",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request DTO 정의
class DailyFinanceRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: Optional[int] = 0
    minute: Optional[int] = 0
    gender: str  # "male" or "female"
    analysis_type: Optional[str] = "finance"

@app.get("/")
def read_root():
    return {"status": "online", "message": "Saju Engine API Server is running!"}

@app.post("/api/finance-fortune")
def get_finance_fortune(request: DailyFinanceRequest):
    try:
        # 1. 사주 엔진 연산 실행
        engine = SajuEngine()
        # saju_engine의 메서드명에 맞게 호출
        engine_result = engine.calculate(
            year=request.year,
            month=request.month,
            day=request.day,
            hour=request.hour,
            gender=request.gender
        )
        
        # 2. 연산 결과를 Gemini에 전달해 2030 맞춤형 해석 생성
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
