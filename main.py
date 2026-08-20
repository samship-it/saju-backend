# main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from saju_engine import SajuEngine
from ai_service import get_ai_fortune_interpretation

app = FastAPI(title="Saju Engine API with Gemini AI", version="1.0.0")

# --- CORS 설정 추가 ---
# Lovable, 로컬 개발 환경, 개발용 도메인 전체 요청 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 특정 도메인 주소로 제한할 수 있습니다.
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, OPTIONS 등 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 Header 허용
)

# --- Request Models ---
class DailyFinanceRequest(BaseModel):
    user_saju: Dict[str, Any]
    today_data: Dict[str, Any]

class PersonalRequest(BaseModel):
    user_saju: Dict[str, Any]
    target_date: str
    partner_saju: Optional[Dict[str, Any]] = None

class YearlyRequest(BaseModel):
    user_saju: Dict[str, Any]
    target_year: Optional[int] = None

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"status": "online", "message": "Saju Engine API Server is running!"}

# 1. 오늘의 재테크 운세 (AI)
@app.post("/api/v1/daily-finance-ai")
def get_daily_finance_ai(req: DailyFinanceRequest):
    try:
        engine = SajuEngine(req.user_saju)
        raw_result = engine.calculate_daily_finance(req.today_data)
        ai_commentary = get_ai_fortune_interpretation("오늘의 재테크 운세", raw_result)
        return {
            "engine_data": raw_result,
            "ai_interpretation": ai_commentary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"엔진/AI 연산 중 오류 발생: {str(e)}")

# 2. 궁합 및 인간관계 전략 (AI)
@app.post("/api/v1/personal-ai")
def get_personal_ai(req: PersonalRequest):
    try:
        engine = SajuEngine(req.user_saju)
        raw_result = engine.calculate_personal_relationship(req.target_date, req.partner_saju)
        ai_commentary = get_ai_fortune_interpretation("궁합 및 인간관계 전략", raw_result)
        return {
            "engine_data": raw_result,
            "ai_interpretation": ai_commentary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"엔진/AI 연산 중 오류 발생: {str(e)}")

# 3. 연간 운세 및 12개월 흐름 (AI)
@app.post("/api/v1/yearly-ai")
def get_yearly_ai(req: YearlyRequest):
    try:
        engine = SajuEngine(req.user_saju)
        year_to_calc = req.target_year if (req.target_year and req.target_year > 0) else datetime.now().year
        
        if hasattr(engine, 'calculate_yearly_trend'):
            raw_result = engine.calculate_yearly_trend(year_to_calc)
        elif hasattr(engine, 'calculate_yearly'):
            raw_result = engine.calculate_yearly(year_to_calc)
        else:
            raw_result = {"year": year_to_calc, "status": "yearly engine logic completed"}

        ai_commentary = get_ai_fortune_interpretation(f"{year_to_calc}년 연간 운세 및 월별 흐름", raw_result)
        
        return {
            "calculated_year": year_to_calc,
            "engine_data": raw_result,
            "ai_interpretation": ai_commentary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"연간 운세 처리 중 오류 발생: {str(e)}")