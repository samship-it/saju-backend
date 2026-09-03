"""오늘의 타로 / 오늘의 재테크 타로.

카드 1장을 뽑으면(사용자 선택 또는 랜덤) 정/역방향과 함께 해석을 반환한다.
카드 의미·조언은 domains/tarot/타로카드 설명.docx 원문을 사용하고,
'오늘의 메시지'만 Gemini 가 질문/고민에 맞춰 생성한다. 다시 보기는 포인트(프론트 처리), 횟수 제한 없음.
"""
import random
from typing import Dict, Any, Optional, Tuple

from domains.tarot.deck import BASE_CARDS, CARD_BY_ID, image_url
from domains.tarot.content import get_card_reading
from shared.ai_client import call_gemini_json
from shared.fortune_cache import get_or_create

FINANCE_TYPES = {"오늘의 재테크 타로", "재테크 타로", "finance"}

_SYSTEM = (
    "당신은 2030 세대를 위한 타로 리더입니다. 제공된 카드 원문 해석을 벗어나지 않는 범위에서 "
    "사용자의 질문에 맞춘 '오늘의 메시지'만 생성합니다. 유효한 JSON 만 출력합니다."
)


def _is_finance(reading_type: str) -> bool:
    return (reading_type or "").strip() in FINANCE_TYPES


def list_cards() -> list:
    return [{**c, "image_url": image_url(c["id"])} for c in BASE_CARDS]


def _draw(card_id: Optional[int], is_reversed: Optional[bool]) -> Tuple[int, bool]:
    cid = card_id if (card_id is not None and card_id in CARD_BY_ID) else random.choice(range(22))
    rev = is_reversed if is_reversed is not None else random.choice([True, False])
    return cid, bool(rev)


def _fallback(reading: Dict[str, Any], finance: bool) -> dict:
    one_line = reading.get("summary") or reading.get("advice") or ""
    today = " ".join(x for x in [reading.get("description", ""), reading.get("advice_detail", "")] if x)
    return {"one_line": one_line, "today_message": today}


def generate_tarot_reading(
    question: str,
    reading_type: str = "오늘의 타로",
    card_id: Optional[int] = None,
    is_reversed: Optional[bool] = None,
) -> Tuple[dict, bool]:
    finance = _is_finance(reading_type)
    cid, rev = _draw(card_id, is_reversed)
    card = CARD_BY_ID[cid]
    reading = get_card_reading(cid, rev, finance)

    def _gen() -> Tuple[dict, bool]:
        orientation = "역방향" if rev else "정방향"
        prompt = f"""[운세 유형] {reading_type}
[사용자 질문/고민] {question or '오늘 하루 전반'}

[뽑힌 카드] {card['name_kr']} ({card['name_en']}) — {orientation}
[카드 원문 해석] {reading.get('description', '')}
[카드 원문 조언] {reading.get('advice_detail', '')}
[핵심 조언 한 문장] {reading.get('advice', '')}
{("[재테크 요약] " + reading.get('summary')) if (finance and reading.get('summary')) else ""}

[규칙]
- 카드 원문 해석의 방향(정/역방향 포함)을 벗어나지 말 것.
- 역방향이면 에너지가 지연/과잉/내면화/반대로 나타나는 상태를 반영.
- 사주 용어 사용 금지. 2030 현실 언어.
{"- 반드시 돈/투자/소비 관점으로 해석." if finance else ""}
- today_message 는 질문에 맞춘 오늘의 메시지 5줄 이상.

[출력 JSON — 이 구조만]
{{
  "one_line": "이 카드가 오늘 전하는 한 줄 요약",
  "today_message": "질문에 맞춘 오늘의 메시지 (5줄 이상)"
}}"""
        ai, is_fb = call_gemini_json(prompt, _fallback(reading, finance), system_instruction=_SYSTEM)
        data = _fallback(reading, finance) if is_fb else ai
        result = {
            "reading_type": reading_type,
            "question": question,
            "card": {
                "id": cid,
                "name_kr": card["name_kr"],
                "name_en": card["name_en"],
                "image_url": image_url(cid),
            },
            "orientation": orientation,
            "is_reversed": rev,
            "one_line": str(data.get("one_line") or reading.get("summary") or reading.get("advice") or ""),
            "card_meaning": reading.get("description", ""),
            "advice": reading.get("advice", ""),
            "today_message": str(data.get("today_message", "")),
        }
        if finance:
            result["finance_summary"] = reading.get("summary")
        return result, is_fb

    # 같은 (유형·카드·방향·질문) 이면 동일 결과 유지
    payload = {"type": reading_type, "card_id": cid, "reversed": rev, "q": (question or "").strip()}
    data, is_fallback, _from_cache = get_or_create("tarot", payload, _gen)
    return data, is_fallback
