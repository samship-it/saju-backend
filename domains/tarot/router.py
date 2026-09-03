from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from domains.tarot.service import generate_tarot_reading, list_cards

router = APIRouter()


class TarotReadingRequest(BaseModel):
    question: str = Field("오늘 하루 전반", example="이직을 고민 중이에요.")
    reading_type: str = Field("오늘의 타로", example="오늘의 타로",
                              description="'오늘의 타로' 또는 '오늘의 재테크 타로'")
    card_id: Optional[int] = Field(None, ge=0, le=21, description="사용자가 고른 카드. 미지정 시 랜덤")
    is_reversed: Optional[bool] = Field(None, description="정/역방향. 미지정 시 랜덤")


@router.get("/cards", summary="타로 카드 목록")
def get_all_tarot_cards():
    return {"status": "success", "cards": list_cards()}


@router.post("/read", summary="타로 1장 뽑기 + 해석")
def read_tarot(request: TarotReadingRequest):
    try:
        result, is_fallback = generate_tarot_reading(
            question=request.question,
            reading_type=request.reading_type,
            card_id=request.card_id,
            is_reversed=request.is_reversed,
        )
        return {"status": "success", "is_fallback": is_fallback, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"타로 리딩 생성 실패: {str(e)}")
