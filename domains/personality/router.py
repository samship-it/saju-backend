from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from domains.daily.chart_subject import resolve_chart_subject
from domains.personality.service import analyze_aptitude, analyze_character

router = APIRouter()


class PersonalitySajuRequest(BaseModel):
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


def _subject(req: PersonalitySajuRequest, x_api_key: Optional[str]):
    return resolve_chart_subject(
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


def _envelope(data: dict, is_fallback: bool, subject: dict):
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


@router.post("/character", summary="나의 성격 (원국 중심, 30P)")
def character_endpoint(req: PersonalitySajuRequest, x_api_key: Optional[str] = Header(None)):
    subject = _subject(req, x_api_key)
    if not isinstance(subject, dict):
        return subject
    try:
        data, is_fallback = analyze_character(
            subject["year"], subject["month"], subject["day"], subject["hour"], subject["minute"],
            subject["gender"], subject["is_lunar"],
        )
        return _envelope(data, is_fallback, subject)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성격 분석 실패: {str(e)}")


@router.post("/aptitude", summary="나의 적성 (원국 중심, 30P)")
def aptitude_endpoint(req: PersonalitySajuRequest, x_api_key: Optional[str] = Header(None)):
    subject = _subject(req, x_api_key)
    if not isinstance(subject, dict):
        return subject
    try:
        data, is_fallback = analyze_aptitude(
            subject["year"], subject["month"], subject["day"], subject["hour"], subject["minute"],
            subject["gender"], subject["is_lunar"],
        )
        return _envelope(data, is_fallback, subject)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"적성 분석 실패: {str(e)}")
