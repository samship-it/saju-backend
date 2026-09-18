from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.lifelong.service import analyze_lifelong_fortune

router = APIRouter()


class LifelongFortuneRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)
    selected_concern: Optional[str] = Field(
        None, example="money",
        description="사전 질문(LifelongIntakeSheet) 답변 — 'money'|'wealth'|'career'|'social'|'family'. "
                     "주면 data.highlight 에 그 영역 집중 분석 카드가 채워진다.",
    )


@router.post("/analysis", summary="평생운세 (원국+대운 흐름 종합, 250P)")
def lifelong_analysis_endpoint(req: LifelongFortuneRequest):
    try:
        data, is_fallback = analyze_lifelong_fortune(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar),
            selected_concern=req.selected_concern,
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"평생운세 분석 실패: {str(e)}")


# /stage-detail 엔드포인트는 제거했다 — 대운 카드 '자세히 보기'(전략/방해요소/전환점)를
# domains/daewoon 모듈(/api/v1/daewoon/analysis)로 완전 이관했다(사용자 확인·승인).
