from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import API_SECRET_KEY
from domains.daily.ilju_image import target_name
from domains.daily.partners import partner_of
from domains.daily.status_variants import fortune_statuses
from domains.love.profiles import birth_of
from domains.yearly.service import CATEGORIES, generate_travel_hobby, generate_yearly

router = APIRouter()


class YearlyRequest(BaseModel):
    year: Optional[int] = Field(None, example=1990)
    month: Optional[int] = Field(None, example=5)
    day: Optional[int] = Field(None, example=15)
    hour: Optional[int] = Field(None, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0)
    time_unknown: bool = False
    gender: Optional[str] = Field("female")
    is_lunar: Optional[bool] = Field(False)
    target_year: Optional[int] = Field(None, description="미지정 시 올해(자동, 하드코딩 없음)")
    user_id: Optional[str] = None
    target_person_id: Optional[str] = None
    nickname: Optional[str] = None
    love_status: Optional[str] = None
    job_status: Optional[str] = None


def _reject_key():
    raise HTTPException(status_code=403, detail="Invalid API Key")


def _error(status_code: int, code: str, message: str):
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "code": code, "message": message},
    )


def _resolved_hour(hour: Optional[int], time_unknown: bool = False):
    if time_unknown or hour is None:
        return None
    return int(hour)


def _subject(req: YearlyRequest, x_api_key: Optional[str]):
    """인연 id가 있으면 등록 사주만 본다. 없으면 요청 본문의 생년월일을 그대로 쓴다."""
    partner_id = (req.target_person_id or "").strip()
    if partner_id:
        if x_api_key != API_SECRET_KEY:
            _reject_key()
        owner = (req.user_id or "").strip()
        if not owner:
            return _error(422, "USER_REQUIRED", "사용자 정보가 필요합니다.")
        row = partner_of(owner, partner_id)
        if row is None:
            return _error(404, "PARTNER_NOT_FOUND", "등록된 인연을 찾을 수 없습니다.")
        return {
            "target_person_id": partner_id,
            "nickname": row["nickname"],
            "year": row["year"],
            "month": row["month"],
            "day": row["day"],
            "hour": row["hour"],
            "minute": row["minute"] or 0,
            "gender": row["gender"] or "female",
            "is_lunar": bool(row["is_lunar"]),
            "stored_love": row.get("love_status"),
            "stored_job": row.get("job_status"),
            "is_target": True,
        }
    if req.year is None or req.month is None or req.day is None:
        return _error(422, "BIRTH_REQUIRED", "생년월일이 필요합니다.")
    nickname = (req.nickname or "").strip()
    return {
        "target_person_id": None,
        "nickname": nickname or None,
        "year": req.year,
        "month": req.month,
        "day": req.day,
        "hour": _resolved_hour(req.hour, req.time_unknown),
        "minute": req.minute or 0,
        "gender": req.gender or "female",
        "is_lunar": bool(req.is_lunar),
        "stored_love": None,
        "stored_job": None,
        "is_target": False,
    }


def _statuses(req: YearlyRequest, subject: dict):
    if subject["is_target"]:
        stored_love, stored_job = subject["stored_love"], subject["stored_job"]
    else:
        profile = birth_of(req.user_id) if (req.user_id or "").strip() else None
        profile = profile or {}
        stored_love, stored_job = profile.get("love_status"), profile.get("job_status")
    return fortune_statuses(
        subject["is_target"], stored_love, stored_job, req.love_status, req.job_status,
    )


def _envelope(data: dict, is_fallback: bool, subject: dict, love_status, job_status):
    return {
        "status": "success",
        "is_fallback": is_fallback,
        **data,
        "target_person_id": subject["target_person_id"],
        "nickname": subject["nickname"],
        "target_name": target_name(subject["nickname"]),
        "love_status": love_status,
        "job_status": job_status,
    }


def _prepare(req: YearlyRequest, x_api_key: Optional[str]):
    subject = _subject(req, x_api_key)
    if not isinstance(subject, dict):
        return subject
    love_status, job_status = _statuses(req, subject)
    return subject, love_status, job_status


@router.get("/categories", summary="연간 운세 9개 카테고리")
def categories():
    return {"status": "success", "categories": CATEGORIES}


@router.post("/travel-hobby", summary="여행·취미 통합 운세")
def travel_hobby_endpoint(req: YearlyRequest, x_api_key: Optional[str] = Header(None)):
    prepared = _prepare(req, x_api_key)
    if not isinstance(prepared, tuple):
        return prepared
    subject, love_status, job_status = prepared
    try:
        data, is_fallback = generate_travel_hobby(
            subject["year"], subject["month"], subject["day"], subject["hour"], subject["minute"],
            subject["gender"], subject["is_lunar"], req.target_year,
        )
        return _envelope(data, is_fallback, subject, love_status, job_status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"여행·취미 운세 생성 실패: {str(e)}")


@router.post("/{category}", summary="연간 운세 (카테고리별)")
def yearly_endpoint(
    req: YearlyRequest,
    category: str = Path(..., description="overall/wealth/love/business/career_change/study/health/travel/hobby"),
    x_api_key: Optional[str] = Header(None),
):
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail=f"알 수 없는 카테고리: {category}")
    prepared = _prepare(req, x_api_key)
    if not isinstance(prepared, tuple):
        return prepared
    subject, love_status, job_status = prepared
    try:
        data, is_fallback = generate_yearly(
            category, subject["year"], subject["month"], subject["day"], subject["hour"], subject["minute"],
            subject["gender"], subject["is_lunar"], req.target_year,
        )
        return _envelope(data, is_fallback, subject, love_status, job_status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"연간 운세 생성 실패: {str(e)}")
