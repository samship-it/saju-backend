"""만세력 명식(원국) 조회 — AI 호출 없음, 빠름.

프론트엔드 명식 카드(SajuChartCard)용. 만세력은 한번 산출되면 고정이므로
같은 입력이면 항상 같은 결과.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.saju_base import calculate_saju
from shared.public import person_summary

router = APIRouter()


class SajuChartRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0)
    gender: Optional[str] = Field("female")
    is_lunar: Optional[bool] = Field(False)


@router.post("/chart", summary="만세력 명식(원국) 조회")
def saju_chart(req: SajuChartRequest):
    try:
        saju = calculate_saju(
            req.year, req.month, req.day, req.hour, req.minute or 0,
            gender=req.gender or "female", is_lunar=bool(req.is_lunar),
        )
        return {
            "status": "success",
            "birth_time_known": saju.get("birth_time_known"),
            "saju_info": person_summary(saju),
            "daewoon": saju.get("daewoon"),
            "current_daewoon": saju.get("current_daewoon"),
            "sipsin": saju.get("sipsin"),
            "twelve_unseong": saju.get("twelve_unseong"),
            "branch_relations": saju.get("branch_relations", {}).get("counts"),
            "active_elements": (saju.get("derived") or {}).get("active_elements"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"명식 조회 실패: {str(e)}")
