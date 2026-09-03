from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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


class MarriageRequest(BaseModel):
    person: PersonInput
    partner: Optional[PersonInput] = None
    target_year: Optional[int] = Field(None, description="미지정 시 올해(자동)")
    target_date: Optional[str] = None


def _dump(p: Optional[PersonInput]):
    return p.model_dump() if p else None


@router.post("/reunion", summary="재회운 (30P)")
def reunion_endpoint(req: LoveRequest):
    try:
        data, is_fallback = analyze_reunion(req.person.model_dump(), _dump(req.partner), req.target_date)
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재회운 분석 실패: {str(e)}")


@router.post("/crush", summary="짝사랑운 (30P)")
def crush_endpoint(req: LoveRequest):
    try:
        data, is_fallback = analyze_crush(req.person.model_dump(), _dump(req.partner), req.target_date)
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"짝사랑운 분석 실패: {str(e)}")


@router.post("/marriage", summary="결혼운 / 결혼시기운 (30P)")
def marriage_endpoint(req: MarriageRequest):
    try:
        data, is_fallback = analyze_marriage(
            req.person.model_dump(), _dump(req.partner), req.target_year, req.target_date,
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"결혼운 분석 실패: {str(e)}")
