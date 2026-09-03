import os

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from domains.saju.router import router as saju_router
from domains.daily.router import router as daily_router
from domains.wealth.router import router as wealth_router
from domains.tarot.router import router as tarot_router
from domains.personality.router import router as personality_router
from domains.compatibility.router import router as compatibility_router
from domains.relationship.router import router as relationship_router
from domains.yearly.router import router as yearly_router

app = FastAPI(
    title="Saju Fortune Engine",
    description="만세력 사주 엔진 + Gemini(gemini-3.5-flash) 자연어 콘텐츠 레이어",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "서버 처리 중 예외가 발생했습니다.",
            "detail": str(exc),
        },
    )


# 만세력 명식 (AI 없음)
app.include_router(saju_router, prefix="/api/v1/saju", tags=["만세력 명식"])
# TODAY
app.include_router(daily_router, prefix="/api/v1/daily", tags=["오늘의 운세"])
app.include_router(wealth_router, prefix="/api/v1/wealth", tags=["오늘의 재테크 사주"])
app.include_router(tarot_router, prefix="/api/v1/tarot", tags=["타로"])
# PERSONAL
app.include_router(personality_router, prefix="/api/v1/personality", tags=["나의 성격/적성"])
# RELATIONSHIP
app.include_router(compatibility_router, prefix="/api/v1/compatibility", tags=["궁합"])
app.include_router(relationship_router, prefix="/api/v1/relationship", tags=["재회/짝사랑/결혼운"])
# YEARLY
app.include_router(yearly_router, prefix="/api/v1/yearly", tags=["연간 운세 9종"])

# 타로 이미지 정적 서빙
TAROT_IMAGE_DIR = os.environ.get(
    "TAROT_IMAGE_DIR",
    os.path.join(os.path.dirname(__file__), "domains", "tarot", "타로이미지"),
)
if os.path.isdir(TAROT_IMAGE_DIR):
    app.mount("/static/tarot_images", StaticFiles(directory=TAROT_IMAGE_DIR), name="tarot_images")


@app.get("/")
def read_root():
    return {"status": "healthy", "message": "Saju Fortune Engine is operational."}
