import datetime
import json
import traceback
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import KST, API_SECRET_KEY
from core.saju_base import calculate_saju
from domains.daily.content_db import make_key
from domains.daily.ilju_image import ilju_animal_icon, target_name
from domains.daily.partners import partner_of, partners_of, upsert_partner
from domains.daily.service import generate_daily_fortune
from domains.daily.status_variants import fortune_statuses
from domains.love.profiles import birth_of
from shared.public import person_summary

router = APIRouter()


class DailyFortuneRequest(BaseModel):
    user_id: str
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    hour: Optional[int] = None          # None = 출생시간 미상
    minute: Optional[int] = 0
    time_unknown: Optional[bool] = False  # true면 hour가 있어도 시주를 뺀다
    gender: Optional[str] = "female"
    is_lunar: Optional[bool] = False
    target_date: Optional[str] = None    # 미지정 시 오늘(KST)
    love_status: Optional[str] = None    # 'single' | 'dating' | 'married' (미지정/모르는 값=폴백)
    job_status: Optional[str] = None     # 'employee' | 'self_employed' | 'job_seeker' |
                                          # 'student' | 'homemaker' | 'retired' (미지정/모르는 값=폴백)
    target_person_id: Optional[str] = None  # 있으면 등록된 인연 사주, 없으면 요청의 본인 사주
    nickname: Optional[str] = None          # 본인 조회일 때만 응답 닉네임으로 쓴다


class PartnerSyncRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    partner_id: str = Field(..., min_length=1, max_length=128)
    nickname: str = Field(..., min_length=1, max_length=64)
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    time_unknown: bool = False
    gender: str = "female"
    is_lunar: bool = False
    love_status: Optional[str] = None
    job_status: Optional[str] = None


def _resolved_hour(hour: Optional[int], time_unknown: bool = False):
    """시간 모름이거나 시가 없으면 시주를 만들지 않는다."""
    if time_unknown or hour is None:
        return None
    return int(hour)


def _reject_key():
    raise HTTPException(status_code=403, detail="Invalid API Key")


def _partner_missing():
    return JSONResponse(
        status_code=404,
        content={
            "status": "error",
            "code": "PARTNER_NOT_FOUND",
            "message": "등록된 인연을 찾을 수 없습니다.",
        },
    )


def _birth_required():
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "code": "BIRTH_REQUIRED",
            "message": "본인 조회에는 생년월일이 필요합니다.",
        },
    )


@lru_cache(maxsize=512)
def _cached_daily_reading(
    year: int, month: int, day: int, hour_key: int, minute: int,
    gender: str, is_lunar: bool, target_date_str: str,
    love_status: str, job_status: str,
) -> str:
    """같은 사주·날짜·상태면 같은 오늘의 운세. 계산은 기존 3600 DB + 3단 점수 델타 그대로다."""
    t_date = datetime.date.fromisoformat(target_date_str)
    hour = None if hour_key < 0 else hour_key
    saju_data = calculate_saju(
        year, month, day, hour, minute,
        gender=gender or "female", is_lunar=is_lunar, target_date=t_date,
    )
    derived = saju_data.get("derived", {})
    day_ganji = saju_data.get("day_ganji") or ""
    iljin_ganji = (saju_data.get("today_ganji") or {}).get("day") or ""
    fortune_result, is_fallback = generate_daily_fortune(
        saju_data,
        love_status=love_status or None,
        job_status=job_status or None,
    )
    icon = ilju_animal_icon(day_ganji)
    payload = {
        "birth_time_known": saju_data.get("birth_time_known"),
        "saju_info": person_summary(saju_data),
        "active_elements": derived.get("active_elements"),
        "score_components": derived.get("score_components"),
        "combo_key": make_key(day_ganji, iljin_ganji),
        "ilju_profile_image": icon,
        "ilju_animal_icon": icon,
        "cached": not is_fallback,
        "is_fallback": is_fallback,
        "data": fortune_result,
    }
    return json.dumps(payload, ensure_ascii=False)


def _subject(req: DailyFortuneRequest):
    """계산에 쓸 사주와 응답에 실을 닉네임. 인연 id 가 있으면 등록 목록만 본다."""
    partner_id = (req.target_person_id or "").strip()
    if partner_id:
        row = partner_of(req.user_id, partner_id)
        if row is None:
            return None
        return {
            "target_person_id": partner_id,
            "nickname": row["nickname"],
            "year": row["year"],
            "month": row["month"],
            "day": row["day"],
        "hour": _resolved_hour(row["hour"]),
            "minute": row["minute"],
            "gender": row["gender"],
            "is_lunar": row["is_lunar"],
            "love_status": row.get("love_status"),
            "job_status": row.get("job_status"),
        }
    if req.year is None or req.month is None or req.day is None:
        return False
    nickname = (req.nickname or "").strip()
    return {
        "target_person_id": None,
        "nickname": nickname or None,
        "year": req.year,
        "month": req.month,
        "day": req.day,
        "hour": _resolved_hour(req.hour, bool(req.time_unknown)),
        "minute": req.minute or 0,
        "gender": req.gender or "female",
        "is_lunar": bool(req.is_lunar),
    }


@lru_cache(maxsize=512)
def _birth_ilju_icon(year: int, month: int, day: int, hour_key: int, minute: int, gender: str, is_lunar: bool) -> str:
    saju = calculate_saju(
        year, month, day, None if hour_key < 0 else hour_key, minute,
        gender=gender or "female", is_lunar=is_lunar,
    )
    return ilju_animal_icon(saju.get("day_ganji") or "")


def _partner_card(row: dict) -> dict:
    """인연 목록 한 칸. 사주는 일주 아이콘을 정하는 데만 쓴다."""
    return {
        "id": row["partner_id"],
        "nickname": row["nickname"],
        "ilju_animal_icon": _birth_ilju_icon(
            int(row["year"]), int(row["month"]), int(row["day"]),
            -1 if row["hour"] is None else int(row["hour"]),
            int(row["minute"] or 0),
            row["gender"] or "female",
            bool(row["is_lunar"]),
        ),
    }


@router.get("/partners", summary="등록된 인연 목록")
def list_partners(user_id: str, x_api_key: str = Header(...)):
    """이 사용자의 인연. id, nickname, 60갑자 동물 캐릭터 키."""
    if x_api_key != API_SECRET_KEY:
        _reject_key()
    owner = (user_id or "").strip()
    if not owner:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "code": "USER_REQUIRED", "message": "사용자 정보가 필요합니다."},
        )
    return {"status": "success", "data": [_partner_card(row) for row in partners_of(owner)]}


@router.put("/partners", summary="인연 사주 등록")
def sync_partner(req: PartnerSyncRequest, x_api_key: str = Header(...)):
    """오늘의 운세가 조회할 인연의 생년월일시·성별·닉네임을 저장한다."""
    if x_api_key != API_SECRET_KEY:
        _reject_key()
    saved = upsert_partner(
        req.user_id.strip(), req.partner_id.strip(),
        nickname=req.nickname.strip(),
        year=req.year, month=req.month, day=req.day,
        hour=_resolved_hour(req.hour, req.time_unknown), minute=req.minute,
        gender=req.gender, is_lunar=req.is_lunar,
        love_status=req.love_status, job_status=req.job_status,
    )
    return {"status": "success", "data": saved}


@router.post("/fortune", summary="오늘의 운세 (DAILY_FORTUNE)")
def get_daily_fortune_endpoint(req: DailyFortuneRequest, x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        _reject_key()

    try:
        if req.target_date:
            t_date = datetime.datetime.strptime(req.target_date, "%Y-%m-%d").date()
        else:
            t_date = datetime.datetime.now(KST).date()
        target_date_str = t_date.strftime("%Y-%m-%d")

        subject = _subject(req)
        if subject is None:
            return _partner_missing()
        if subject is False:
            return _birth_required()

        if subject["target_person_id"]:
            stored_love, stored_job = subject.get("love_status"), subject.get("job_status")
        else:
            profile = birth_of(req.user_id) or {}
            stored_love, stored_job = profile.get("love_status"), profile.get("job_status")
        love_status, job_status = fortune_statuses(
            bool(subject["target_person_id"]),
            stored_love, stored_job, req.love_status, req.job_status,
        )

        raw = _cached_daily_reading(
            int(subject["year"]), int(subject["month"]), int(subject["day"]),
            -1 if subject["hour"] is None else int(subject["hour"]),
            int(subject["minute"] or 0),
            subject["gender"] or "female",
            bool(subject["is_lunar"]),
            target_date_str,
            love_status or "",
            job_status or "",
        )
        reading = json.loads(raw)
        return {
            "status": "success",
            "target_date": target_date_str,
            "target_person_id": subject["target_person_id"],
            "nickname": subject["nickname"],
            "target_name": target_name(subject["nickname"]),
            **reading,
        }

    except HTTPException:
        raise
    except Exception as e:
        print("====== daily 에러 ======")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"내부 로직 에러: {str(e)}")
