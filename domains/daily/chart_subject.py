"""평생운세·성격·적성이 등록 인연 사주를 읽는 규칙.

인연 id가 있으면 그 사용자에게 저장된 사주만 쓰고, 요청 본문의 생년월일은 보지 않는다.
인연의 연애·직업 상태가 없으면 싱글·직장인으로 둔다.
"""
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from config import API_SECRET_KEY
from domains.daily.ilju_image import target_name
from domains.daily.partners import partner_of
from domains.daily.status_variants import fortune_statuses
from domains.love.profiles import birth_of


def _error(status_code: int, code: str, message: str):
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "code": code, "message": message},
    )


def resolve_chart_subject(
    *,
    target_person_id: Optional[str],
    user_id: Optional[str],
    year: Optional[int],
    month: Optional[int],
    day: Optional[int],
    hour: Optional[int],
    minute: Optional[int],
    time_unknown: bool,
    gender: Optional[str],
    is_lunar: Optional[bool],
    nickname: Optional[str],
    love_status: Optional[str],
    job_status: Optional[str],
    x_api_key: Optional[str],
) -> Any:
    partner_id = (target_person_id or "").strip()
    if partner_id:
        if x_api_key != API_SECRET_KEY:
            raise HTTPException(status_code=403, detail="Invalid API Key")
        owner = (user_id or "").strip()
        if not owner:
            return _error(422, "USER_REQUIRED", "사용자 정보가 필요합니다.")
        row = partner_of(owner, partner_id)
        if row is None:
            return _error(404, "PARTNER_NOT_FOUND", "등록된 인연을 찾을 수 없습니다.")
        subject = {
            "target_person_id": partner_id,
            "nickname": row["nickname"],
            "year": row["year"],
            "month": row["month"],
            "day": row["day"],
            "hour": None if row["hour"] is None else int(row["hour"]),
            "minute": row["minute"] or 0,
            "gender": row["gender"] or "female",
            "is_lunar": bool(row["is_lunar"]),
            "is_target": True,
        }
        stored_love, stored_job = row.get("love_status"), row.get("job_status")
    else:
        if year is None or month is None or day is None:
            return _error(422, "BIRTH_REQUIRED", "생년월일이 필요합니다.")
        called = (nickname or "").strip()
        subject = {
            "target_person_id": None,
            "nickname": called or None,
            "year": year,
            "month": month,
            "day": day,
            "hour": None if time_unknown or hour is None else int(hour),
            "minute": minute or 0,
            "gender": gender or "female",
            "is_lunar": bool(is_lunar),
            "is_target": False,
        }
        profile = birth_of(user_id) if (user_id or "").strip() else None
        profile = profile or {}
        stored_love, stored_job = profile.get("love_status"), profile.get("job_status")
    love, job = fortune_statuses(
        subject["is_target"], stored_love, stored_job, love_status, job_status,
    )
    subject["love_status"] = love
    subject["job_status"] = job
    subject["target_name"] = target_name(subject["nickname"])
    return subject
