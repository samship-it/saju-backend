"""Gemini 자연어 생성 공용 클라이언트.

- 모델은 config.GEMINI_MODEL_NAME('gemini-3.5-flash')로 고정. 절대 코드에서 바꾸지 않는다.
- 인증은 환경변수 GEMINI_API_KEY.
- 점수 일관성을 위해 temperature=0 으로 호출한다.
- 키 미설정/호출 실패 시 (fallback, is_fallback=True) 반환.
"""
import json
import logging
import re
import time
from typing import Tuple, Optional

import config

logger = logging.getLogger(__name__)

# 429/ResourceExhausted 대응: 분당 제한(RPM)이면 서버가 알려준 retry_delay 만큼
# 한 번만 대기 후 재시도한다. HTTP 핸들러를 오래 붙잡지 않도록 상한을 둔다.
# 일일 한도(PerDay) 초과는 재시도해도 소용없으므로 바로 폴백으로 넘어간다.
_MAX_RETRY_WAIT_SEC = 8


def _is_rate_limited(err: Exception) -> bool:
    name = type(err).__name__
    text = str(err)
    return (
        name in ("ResourceExhausted", "TooManyRequests")
        or "429" in text
        or "Quota exceeded" in text
        or "RATE_LIMIT" in text.upper()
    )


def _retry_delay_sec(err: Exception) -> Optional[int]:
    m = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", str(err))
    if not m:
        m = re.search(r"retry in (\d+)", str(err))
    return int(m.group(1)) if m else None

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
            model_name=config.GEMINI_MODEL_NAME,
            system_instruction=system_instruction or None,
            generation_config=_GENERATION_CONFIG,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ai_client] Gemini 모델 초기화 실패: {e}")
        return fallback_data, True

    for attempt in range(2):
        try:
            response = model.generate_content(prompt)
            return _extract_json(response.text), False
        except Exception as e:  # noqa: BLE001
            if _is_rate_limited(e):
                per_day = "PerDay" in str(e) or "free_tier_requests" in str(e)
                wait = _retry_delay_sec(e)
                if attempt == 0 and not per_day and wait is not None and wait <= _MAX_RETRY_WAIT_SEC:
                    logger.warning(
                        f"[ai_client] 할당량 초과 (model={config.GEMINI_MODEL_NAME}). "
                        f"{wait}s 대기 후 1회 재시도"
                    )
                    time.sleep(wait)
                    continue
                logger.error(
                    f"[ai_client] Gemini 할당량 초과 → 폴백 반환 "
                    f"(model={config.GEMINI_MODEL_NAME}). 무료 등급이면 결제 활성화 필요: {e}"
                )
            else:
                logger.error(f"[ai_client] Gemini 호출 실패: {e}")
            return fallback_data, True

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
