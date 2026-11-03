"""Gemini 검수 호출. 재시도하지 않는다. 실패하면 None 이다.

키는 환경변수의 GEMINI_API_KEY 만 읽는다. 로그에 키를 쓰지 않는다.
"""
import logging
from typing import Optional

import config
from shared.proofread.settings import max_output_tokens

logger = logging.getLogger("proofread")

SYSTEM = (
    "너는 한국어 교정자다. 사주 작가나 해석가가 아니다. "
    "맞춤법, 띄어쓰기, 조사, 문장부호, 명백한 오탈자, 단어가 잘못 붙은 곳만 고친다. "
    "의미, 점수, 연도, 숫자, 간지, 일주, 문체, 새로운 해석은 바꾸지 않는다. "
    "확신이 없으면 edits 를 빈 배열로 둔다. JSON 만 반환한다. "
    '{"edits":[{"original":"틀린 부분","suggestion":"고친 부분",'
    '"error_type":"spelling","confidence":0.95}]} '
    "error_type 은 spelling, spacing, particle, punctuation, typo 중 하나만 쓴다."
)


class LlmOutcome:
    def __init__(self, edits, input_tokens: int, output_tokens: int):
        self.edits = edits if isinstance(edits, list) else []
        self.input_tokens = int(input_tokens or 0)
        self.output_tokens = int(output_tokens or 0)


def complete(text: str, model: str, output_tokens: Optional[int] = None) -> Optional[LlmOutcome]:
    api_key = config.GEMINI_API_KEY
    if not api_key:
        logger.warning("[proofread] GEMINI_API_KEY 없음. 원문을 유지합니다.")
        return None
    try:
        import google.generativeai as genai
    except Exception:  # noqa: BLE001
        logger.warning("[proofread] Gemini SDK 없음. 원문을 유지합니다.")
        return None
    try:
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "max_output_tokens": int(output_tokens or max_output_tokens()),
            },
        )
        response = client.generate_content(text)
        payload = _json(getattr(response, "text", "") or "")
        usage = getattr(response, "usage_metadata", None)
        return LlmOutcome(
            (payload or {}).get("edits") if isinstance(payload, dict) else [],
            _usage_count(usage, "prompt_token_count"),
            _usage_count(usage, "candidates_token_count"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[proofread] Gemini 호출 실패. 원문을 유지합니다: %s", type(exc).__name__)
        return None


def _json(raw: str):
    import json
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    return json.loads(cleaned)


def _usage_count(usage, name: str) -> int:
    if usage is None:
        return 0
    value = getattr(usage, name, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(name, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
