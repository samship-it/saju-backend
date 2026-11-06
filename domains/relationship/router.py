from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from domains.daily.partner_access import birth_from_row, owned_partner
from domains.relationship.service import (
    analyze_reunion, analyze_crush, analyze_marriage,
)

router = APIRouter()


class PersonInput(BaseModel):
    year: int = Field(..., example=1993)
    month: int = Field(..., example=7)
    day: int = Field(..., example=21)
    hour: Optional[int] = Field(None, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0)
    gender: Optional[str] = Field("female")
    is_lunar: Optional[bool] = Field(False)


class LoveRequest(BaseModel):
    person: PersonInput
    partner: Optional[PersonInput] = Field(None, description="상대방(+1명). 없으면 본인 원국만")
    target_date: Optional[str] = Field(None, example="2026-09-03")
    user_id: Optional[str] = None
    target_person_id: Optional[str] = None


class MarriageRequest(BaseModel):
    person: PersonInput
    partner: Optional[PersonInput] = None
    target_year: Optional[int] = Field(None, description="미지정 시 올해(자동)")
    target_date: Optional[str] = None
    user_id: Optional[str] = None
    target_person_id: Optional[str] = None


def _dump(p: Optional[PersonInput]):
    return p.model_dump() if p else None


def _partner_birth(req, api_key: Optional[str]):
    """인연 ID가 있으면 저장된 출생만 쓴다. 없으면 요청 본문을 그대로 둔다."""
    row = owned_partner(getattr(req, "user_id", None), getattr(req, "target_person_id", None), api_key)
    if row is None:
        return _dump(req.partner), None, None
    if not isinstance(row, dict):
        return row, None, None
    return birth_from_row(row), row["partner_id"], int(row.get("birth_version") or 1)


def _with_target(payload: dict, partner_id, birth_version):
    payload["target_person_id"] = partner_id
    payload["birth_version"] = birth_version
    return payload


@router.post("/reunion", summary="재회운 (30P)")
def reunion_endpoint(req: LoveRequest, x_api_key: Optional[str] = Header(None)):
    try:
        partner_info, partner_id, birth_version = _partner_birth(req, x_api_key)
        if not isinstance(partner_info, dict) and partner_info is not None:
            return partner_info
        data, is_fallback = analyze_reunion(req.person.model_dump(), partner_info, req.target_date)
        return _with_target(
            {"status": "success", "is_fallback": is_fallback, **data},
            partner_id, birth_version,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재회운 분석 실패: {str(e)}")


@router.post("/crush", summary="짝사랑운 (30P)")
def crush_endpoint(req: LoveRequest, x_api_key: Optional[str] = Header(None)):
    try:
        partner_info, partner_id, birth_version = _partner_birth(req, x_api_key)
        if not isinstance(partner_info, dict) and partner_info is not None:
            return partner_info
        data, is_fallback = analyze_crush(req.person.model_dump(), partner_info, req.target_date)
        return _with_target(
            {"status": "success", "is_fallback": is_fallback, **data},
            partner_id, birth_version,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"짝사랑운 분석 실패: {str(e)}")


@router.post("/marriage", summary="결혼운 / 결혼시기운 (30P)")
def marriage_endpoint(req: MarriageRequest, x_api_key: Optional[str] = Header(None)):
    try:
        partner_info, partner_id, birth_version = _partner_birth(req, x_api_key)
        if not isinstance(partner_info, dict) and partner_info is not None:
            return partner_info
        data, is_fallback = analyze_marriage(
            req.person.model_dump(), partner_info, req.target_year, req.target_date,
        )
        return _with_target(
            {"status": "success", "is_fallback": is_fallback, **data},
            partner_id, birth_version,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"결혼운 분석 실패: {str(e)}")
