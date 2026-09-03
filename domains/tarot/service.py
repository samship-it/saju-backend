"""오늘의 타로 / 오늘의 재테크 타로.

카드 1장을 뽑으면(사용자 선택 + 정/역방향) 해당 방향의 해석을 반환한다.
카드 의미·조언은 domains/tarot/타로카드 설명.docx 원문(정방향/역방향/재테크 정·역 4종)을 사용하고,
'오늘의 메시지'만 Gemini 가 질문/고민에 맞춰 생성한다. 다시 보기는 포인트(프론트), 횟수 무제한.
"""
import random
from typing import Dict, Any, Optional, Tuple

from domains.tarot.deck import BASE_CARDS, CARD_BY_ID, image_url
from domains.tarot.content import get_card_reading, load_card_content
from shared.ai_client import call_gemini_json
from shared.fortune_cache import get_or_create

FINANCE_TYPES = {"오늘의 재테크 타로", "재테크 타로", "finance"}

_SYSTEM = (
    "당신은 2030 세대를 위한 노련한 타로 리더입니다. 제공된 카드 원문(정방향/역방향)의 방향과 의미를 "
    "절대 벗어나지 않는 범위에서, 사용자의 질문에 밀착한 '오늘의 메시지'를 충실하게 생성합니다. "
    "사주 용어는 쓰지 않고 현실 언어로 풀어씁니다. 유효한 JSON 만 출력합니다."
)

_ORIENTATION_NOTE = {
    False: "정방향 — 카드의 에너지가 자연스럽게, 제 방향으로 흐르는 상태",
    True: "역방향 — 카드의 에너지가 지연되거나·과해지거나·내면화되거나·반대로 나타나는 상태",
}


def _is_finance(reading_type: str) -> bool:
    return (reading_type or "").strip() in FINANCE_TYPES


def list_cards() -> list:
    return [{**c, "image_url": image_url(c["id"])} for c in BASE_CARDS]


def _draw(card_id: Optional[int], is_reversed: Optional[bool]) -> Tuple[int, bool]:
    cid = card_id if (card_id is not None and card_id in CARD_BY_ID) else random.choice(range(22))
    rev = is_reversed if is_reversed is not None else random.choice([True, False])
    return cid, bool(rev)


def _fallback_today(reading: Dict[str, Any], rev: bool, finance: bool) -> str:
    """AI 미사용 시: 원문 설명 + 조언 본문을 문단으로 이어 붙여 충분한 분량을 확보."""
    parts = []
    desc = reading.get("description", "").strip()
    detail = reading.get("advice_detail", "").strip()
    if desc:
        parts.append(desc)
    if detail and detail != desc:
        parts.append(detail)
    if not parts:
        parts.append(
            ("역방향" if rev else "정방향") + " 카드의 흐름을 차분히 읽어보세요. "
            + ("돈·투자·소비 판단에서 " if finance else "")
            + "서두르기보다 방향을 먼저 점검하는 편이 유리한 날입니다."
        )
    return "\n\n".join(parts)


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
    content_loaded = bool(load_card_content())

    def _gen() -> Tuple[dict, bool]:
        orientation = "역방향" if rev else "정방향"
        fb = {
            "one_line": reading.get("summary") or reading.get("advice") or "",
            "today_message": _fallback_today(reading, rev, finance),
        }
        prompt = f"""[운세 유형] {reading_type}
[사용자 질문/고민] {question or '오늘 하루 전반'}

[뽑힌 카드] {card['name_kr']} ({card['name_en']})
[방향] {_ORIENTATION_NOTE[rev]}
[이 방향의 카드 의미(원문)] {reading.get('description', '')}
[이 방향의 조언(원문)] {reading.get('advice_detail', '')}
[핵심 조언 한 문장] {reading.get('advice', '')}
{("[재테크 요약] " + reading.get('summary')) if (finance and reading.get('summary')) else ""}

[작성 규칙]
- 위 '{orientation}' 원문의 방향·뉘앙스를 절대 벗어나지 말 것. (정방향 카드에 역방향 해석 금지, 그 반대도 금지)
- 역방향이면 지연/과잉/내면화/반대로 나타나는 상태를 분명히 반영.
- 카드 의미를 '오늘, 이 질문'에 어떻게 적용할지 구체적 상황·행동으로 풀어쓸 것.
- 사주 용어 금지. 2030 현실 언어.
{"- 반드시 돈/투자/소비/현금흐름 관점으로 해석." if finance else ""}
- today_message 는 최소 7줄, 도입(카드가 말하는 오늘의 분위기) → 전개(구체 상황) → 마무리(오늘 할 일)의 흐름.

[출력 JSON — 이 구조만]
{{
  "one_line": "이 카드가 오늘 전하는 한 줄 요약 (질문 맥락 반영)",
  "today_message": "질문에 밀착한 오늘의 메시지 (7줄 이상)"
}}"""
        ai, is_fb = call_gemini_json(prompt, fb, system_instruction=_SYSTEM)
        data = fb if is_fb else ai

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
            "orientation_meaning": _ORIENTATION_NOTE[rev],
            "one_line": str(data.get("one_line") or reading.get("summary") or reading.get("advice") or ""),
            "card_meaning": reading.get("description", ""),
            "advice": reading.get("advice", ""),
            "advice_detail": reading.get("advice_detail", ""),
            "today_message": str(data.get("today_message") or fb["today_message"]),
            "content_loaded": content_loaded,
        }
        if finance:
            result["finance_summary"] = reading.get("summary")
        return result, is_fb

    # 같은 (유형·카드·방향·질문)이면 동일 결과 유지
    payload = {"type": reading_type, "card_id": cid, "reversed": rev, "q": (question or "").strip()}
    data, is_fallback, _from_cache = get_or_create("tarot", payload, _gen)
    return data, is_fallback
