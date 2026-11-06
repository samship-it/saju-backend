"""인연 ID가 있는 운세는 그 주인의 저장 행만 계산에 쓴다."""
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from config import API_SECRET_KEY
from domains.daily.partners import partner_of


def owned_partner(user_id: Optional[str], partner_id: Optional[str], api_key: Optional[str]):
    """ID가 비어 있으면 None. 없거나 다른 주인이면 오류 응답. 있으면 저장 행."""
    target = (partner_id or "").strip()
    if not target:
        return None
    if api_key != API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    owner = (user_id or "").strip()
    if not owner:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "code": "USER_REQUIRED", "message": "사용자 정보가 필요합니다."},
        )
    row = partner_of(owner, target)
    if row is None:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "code": "PARTNER_NOT_FOUND",
                "message": "등록된 인연을 찾을 수 없습니다.",
            },
        )
    return row


def birth_from_row(row: dict) -> dict:
    return {
        "year": int(row["year"]),
        "month": int(row["month"]),
        "day": int(row["day"]),
        "hour": None if row["hour"] is None else int(row["hour"]),
        "minute": int(row["minute"] or 0),
        "gender": row["gender"] or "female",
        "is_lunar": bool(row["is_lunar"]),
    }
