from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from ai_service import get_ai_fortune_interpretation

app = FastAPI(title="Saju Fortune API")

# Lovable 및 모든 프론트엔드에서 API를 호출할 수 있도록 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 프론트엔드에서 보내올 요청 데이터 규격
class FortuneRequest(BaseModel):
    year: int
    month: int
    day: int
    hour: Optional[int] = None
    gender: str  # "male" or "female"

@app.get("/")
def read_root():
    return {"status": "online", "message": "Saju Fortune API with Gemini 3.5 is running"}

@app.post("/api/v1/fortune")
def generate_fortune(request: FortuneRequest):
    try:
        # 1. 사주 엔진 결과 연산 (가상 데이터/엔진 연동 영역)
        engine_data = {
            "wealth": {
                "wealth_star_strength": 50,
                "wealth_star_activation": "HIGH"
            },
            "investment": {
                "speculation_tendency": 80,
                "risk_taking_tendency": 75,
                "financial_caution": "WARNING"
            },
            "consumption": {
                "impulse_buying_tendency": 70
            },
            "money_action": {
                "recommended": "기존 자산의 비중을 점검하고 분할 매수로 접근하세요.",
                "avoid": "급등하는 종목이나 자산을 홧김에 추격 매수하는 행동",
                "keywords": ["#기회탐색", "#추격매수주의", "#분할매수"]
            }
        }

        # 2. 검증된 Gemini 3.5 API 호출로 AI 해석 생성
        ai_interpretation = get_ai_fortune_interpretation("wealth", engine_data)

        # 3. Lovable에서 사용하기 편하도록 최종 구조화된 데이터 반환
        return {
            "status": "success",
            "user_info": {
                "birth_date": f"{request.year}-{request.month:02d}-{request.day:02d}",
                "gender": request.gender
            },
            "engine_data": engine_data,
            "interpretation": ai_interpretation
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
