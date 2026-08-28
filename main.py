from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 도메인별 라우터 불러오기
from domains.daily.router import router as daily_router
from domains.comprehensive.router import router as comprehensive_router
from domains.personality.router import router as personality_router
from domains.wealth.router import router as wealth_router
from domains.compatibility.router import router as compatibility_router
from domains.tarot.router import router as tarot_router

app = FastAPI(
    title='Saju Fortune & Financial Analysis Engine',
    description='사주명리학 엔진 + LLM 해석 + 금융 시장 데이터 결합 API',
    version='1.0.0'
)

# CORS 설정 (Lovable 프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# 전역 예외 처리기
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'status': 'error',
            'code': 'INTERNAL_SERVER_ERROR',
            'message': '서버 처리 중 예외가 발생했습니다.',
            'detail': str(exc)
        }
    )

# 도메인 라우터 연결
app.include_router(daily_router, prefix='/api/v1/daily', tags=['Daily Fortune'])
app.include_router(comprehensive_router, prefix='/api/v1/comprehensive', tags=['Comprehensive Report'])
app.include_router(personality_router, prefix='/api/v1/personality', tags=['Personality & Talent'])
app.include_router(wealth_router, prefix='/api/v1/wealth', tags=['Wealth & Market'])
app.include_router(compatibility_router, prefix='/api/v1/compatibility', tags=['Compatibility'])
app.include_router(tarot_router, prefix='/api/v1/tarot', tags=['Tarot Reading'])

@app.get('/')
def read_root():
    return {'status': 'healthy', 'message': 'Saju Fortune Engine is fully operational.'}

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from domains.tarot.router import router as tarot_router

app = FastAPI()

# 타로 이미지 폴더가 있는 실제 경로
TAROT_IMAGE_DIR = r"C:\운세\타로이미지"

# 이미지 폴더를 /static/tarot_images 경로로 접근 가능하게 설정
if os.path.exists(TAROT_IMAGE_DIR):
    app.mount("/static/tarot_images", StaticFiles(directory=TAROT_IMAGE_DIR), name="tarot_images")

app.include_router(tarot_router, prefix="/api/v1/tarot", tags=["Tarot"])    