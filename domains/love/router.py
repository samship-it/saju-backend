"""연애 섹션 배너 — 내 사주가 끌어당기는 운명의 인연.

출생값은 요청 본문에 없다. X-User-Id 로 저장된 프로필을 읽고 복콩을 차감한다.
"""
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from domains.love.profiles import upsert_profile
from domains.love.service import (
    CONTENT_TYPE, InsufficientBokkong, ProfileMissing, analyze_ideal_partner,
)

router = APIRouter()


class ProfileSyncRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: Optional[int] = Field(None, ge=0, le=23, description="None = 출생시간 미상")
    minute: int = Field(0, ge=0, le=59)
    gender: str = Field("female")
    is_lunar: bool = Field(False)
    bokkong: Optional[int] = Field(None, ge=0, description="없으면 기존 잔액 유지, 신규는 30")
    love_status: Optional[str] = Field(None, description="single | dating | married")
    job_status: Optional[str] = Field(
        None, description="employee | self_employed | job_seeker | student | homemaker | retired",
    )


def _user_required():
    return JSONResponse(
        status_code=403,
        content={"status": "error", "code": "USER_REQUIRED", "message": "로그인한 사용자 정보가 필요합니다."},
    )


def _profile_missing():
    return JSONResponse(
        status_code=403,
        content={"status": "error", "code": "PROFILE_NOT_FOUND", "message": "저장된 사주 프로필이 없습니다."},
    )


@router.put("/profile", summary="로그인 사용자 사주 프로필 동기화")
def sync_profile(body: ProfileSyncRequest, x_user_id: Optional[str] = Header(default=None)):
    """인연 가이드가 조회할 프로필을 저장한다. 운세 입력 폼이 아니다."""
    user_id = (x_user_id or "").strip()
    if not user_id:
        return _user_required()
    saved = upsert_profile(
        user_id,
        year=body.year, month=body.month, day=body.day,
        hour=body.hour, minute=body.minute,
        gender=body.gender, is_lunar=body.is_lunar,
        bokkong=body.bokkong,
        love_status=body.love_status, job_status=body.job_status,
    )
    return {"status": "success", "data": saved}


@router.post("/ideal-partner", summary="내 사주가 끌어당기는 운명의 인연 가이드")
def ideal_partner(x_user_id: Optional[str] = Header(default=None)):
    user_id = (x_user_id or "").strip()
    if not user_id:
        return _user_required()
    try:
        data, is_fallback = analyze_ideal_partner(user_id)
    except ProfileMissing:
        return _profile_missing()
    except InsufficientBokkong as exc:
        return JSONResponse(
            status_code=402,
            content={
                "status": "error",
                "code": "INSUFFICIENT_BOKKONG",
                "message": "복콩이 부족합니다.",
                "remaining_bokkong": exc.remaining,
            },
        )
    return {
        "status": "success",
        "is_fallback": is_fallback,
        "content_type": CONTENT_TYPE,
        "data": data,
    }
