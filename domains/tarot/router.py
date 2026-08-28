# domains/tarot/router.py 예시

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from domains.tarot.service import generate_tarot_reading, BASE_CARDS

router = APIRouter()

class TarotReadingRequest(BaseModel):
    question: str = Field(..., example="오늘의 운세를 알려주세요.", description="타로 질문")
    reading_type: Optional[str] = Field("오늘의 운세", example="오늘의 재테크 운세", description="운세 유형 (오늘의 운세 / 오늘의 재테크 운세 등)")
    selected_card_ids: Optional[List[int]] = Field(None, example=[0, 10, 21])
    custom_orientations: Optional[List[bool]] = Field(None, example=[False, True, False])

@router.get("/cards")
async def get_all_tarot_cards():
    return {"status": "success", "cards": BASE_CARDS}

@router.post("/read")
async def read_tarot(request: TarotReadingRequest):
    try:
        result = generate_tarot_reading(
            question=request.question,
            reading_type=request.reading_type,
            selected_card_ids=request.selected_card_ids,
            custom_orientations=request.custom_orientations
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"타로 리딩 생성 실패: {str(e)}")