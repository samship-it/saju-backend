from typing import Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from domains.yearly.service import generate_yearly, CATEGORIES

router = APIRouter()


class YearlyRequest(BaseModel):
    year: int = Field(..., example=1990)
    month: int = Field(..., example=5)
    day: int = Field(..., example=15)
    hour: Optional[int] = Field(None, description="None = 출생시간 미상")
    minute: Optional[int] = Field(0)
    gender: Optional[str] = Field("female")
    is_lunar: Optional[bool] = Field(False)
    target_year: Optional[int] = Field(None, description="미지정 시 올해(자동, 하드코딩 없음)")


@router.get("/categories", summary="연간 운세 9개 카테고리")
def categories():
    return {"status": "success", "categories": CATEGORIES}


@router.post("/{category}", summary="연간 운세 (카테고리별)")
def yearly_endpoint(
    req: YearlyRequest,
    category: str = Path(..., description="overall/wealth/love/business/career_change/study/health/travel/hobby"),
):
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail=f"알 수 없는 카테고리: {category}")
    try:
        data, is_fallback = generate_yearly(
            category, req.year, req.month, req.day, req.hour, req.minute or 0,
            req.gender or "female", bool(req.is_lunar), req.target_year,
        )
        return {"status": "success", "is_fallback": is_fallback, **data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"연간 운세 생성 실패: {str(e)}")
