"""Gemini 자연어 생성 공용 클라이언트.

- 모델은 config.GEMINI_MODEL_NAME('gemini-3.5-flash')로 고정. 절대 코드에서 바꾸지 않는다.
- 인증은 환경변수 GEMINI_API_KEY.
- 점수 일관성을 위해 temperature=0 으로 호출한다.
- 키 미설정/호출 실패 시 (fallback, is_fallback=True) 반환.
"""
import json
import logging
from typing import Tuple, Optional

import config

logger = logging.getLogger(__name__)

try:  # google-generativeai 미설치 환경에서도 import 되도록
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    "temperature": 0.0,
    "top_p": 1.0,
}


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def call_gemini_json(
    prompt: str,
    fallback_data: dict,
    system_instruction: Optional[str] = None,
) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환."""
    api_key = config.GEMINI_API_KEY
    if not api_key or genai is None:
        logger.info("[ai_client] GEMINI_API_KEY 미설정 또는 SDK 없음 → 폴백 반환")
        return fallback_data, True

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL_NAME,  # 'gemini-3.5-flash' 고정
            system_instruction=system_instruction or None,
            generation_config=_GENERATION_CONFIG,
        )
        response = model.generate_content(prompt)
        return _extract_json(response.text), False
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ai_client] Gemini 호출 실패: {e}")
        return fallback_data, True


def generate_gemini_analysis(prompt: str, system_instruction: str = "") -> str:
    """레거시 호환: 원문 문자열 반환. 키 미설정/실패 시 예외."""
    api_key = config.GEMINI_API_KEY
    if not api_key or genai is None:
        raise RuntimeError("GEMINI_API_KEY 미설정")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL_NAME,
        system_instruction=system_instruction or None,
        generation_config=_GENERATION_CONFIG,
    )
    return model.generate_content(prompt).text
