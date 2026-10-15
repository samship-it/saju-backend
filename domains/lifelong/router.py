from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from domains.daily.chart_subject import resolve_chart_subject
from domains.lifelong.service import analyze_lifelong_fortune

router = APIRouter()


class LifelongFortuneRequest(BaseModel):
    year: Optional[int] = Field(None, example=1990)
    month: Optional[int] = Field(None, example=5)
    day: Optional[int] = Field(None, example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    time_unknown: bool = False
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)
    user_id: Optional[str] = None
    target_person_id: Optional[str] = None
    nickname: Optional[str] = None
    love_status: Optional[str] = None
    job_status: Optional[str] = None
    selected_concern: Optional[str] = Field(
        None, example="money",
        description="사전 질문 답변 — 'money'|'wealth'|'career'|'social'|'family'. "
                     "주면 data.highlight 에 그 영역 집중 분석 카드가 채워진다.",
    )


@router.post("/analysis", summary="평생운세 (원국+대운 흐름 종합, 250P)")
def lifelong_analysis_endpoint(req: LifelongFortuneRequest, x_api_key: Optional[str] = Header(None)):
    subject = resolve_chart_subject(
        target_person_id=req.target_person_id,
        user_id=req.user_id,
        year=req.year,
        month=req.month,
        day=req.day,
        hour=req.hour,
        minute=req.minute,
        time_unknown=req.time_unknown,
        gender=req.gender,
        is_lunar=req.is_lunar,
        nickname=req.nickname,
        love_status=req.love_status,
        job_status=req.job_status,
        x_api_key=x_api_key,
    )
    if not isinstance(subject, dict):
        return subject
    try:
        data, is_fallback = analyze_lifelong_fortune(
            subject["year"], subject["month"], subject["day"], subject["hour"], subject["minute"],
            subject["gender"], subject["is_lunar"],
            selected_concern=req.selected_concern,
        )
        return {
            "status": "success",
            "is_fallback": is_fallback,
            **data,
            "target_person_id": subject["target_person_id"],
            "nickname": subject["nickname"],
            "target_name": subject["target_name"],
            "love_status": subject["love_status"],
            "job_status": subject["job_status"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"평생운세 분석 실패: {str(e)}")


# /stage-detail 엔드포인트는 제거했다 — 대운 카드 '자세히 보기'(전략/방해요소/전환점)를
# domains/daewoon 모듈(/api/v1/daewoon/analysis)로 완전 이관했다(사용자 확인·승인).
