from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from domains.compatibility.service import analyze_compatibility_report
from domains.daily.partner_access import birth_from_row, owned_partner

router = APIRouter()


class PersonSajuInput(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, example=14, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0, example=30)
    gender: Optional[str] = Field("female", example="female")
    is_lunar: Optional[bool] = Field(False)


class CompatibilityRequest(BaseModel):
    person1: PersonSajuInput
    person2: Optional[PersonSajuInput] = None
    relation_type: Optional[str] = Field("romantic", example="romantic")
    user_id: Optional[str] = None
    target_person_id: Optional[str] = None


@router.post("/analyze", summary="궁합 (60P) — 세부/종합 점수 + 8단계 한줄평")
def analyze_compatibility(request: CompatibilityRequest, x_api_key: Optional[str] = Header(None)):
    try:
        row = owned_partner(request.user_id, request.target_person_id, x_api_key)
        birth_version = None
        target_id = None
        if row is None:
            if request.person2 is None:
                return JSONResponse(
                    status_code=422,
                    content={"status": "error", "code": "BIRTH_REQUIRED", "message": "상대 생년월일이 필요합니다."},
                )
            person2 = request.person2.model_dump()
        elif not isinstance(row, dict):
            return row
        else:
            person2 = birth_from_row(row)
            target_id = row["partner_id"]
            birth_version = int(row.get("birth_version") or 1)
        data, is_fallback = analyze_compatibility_report(
            p1_info=request.person1.model_dump(),
            p2_info=person2,
            relation_type=request.relation_type or "romantic",
        )
        return {
            "status": "success",
            "is_fallback": is_fallback,
            **data,
            "target_person_id": target_id,
            "birth_version": birth_version,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"궁합 분석 실패: {str(e)}")
