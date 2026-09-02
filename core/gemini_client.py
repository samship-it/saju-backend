"""Gemini LLM 호출 공용 클라이언트.

도메인 서비스(personality/wealth/comprehensive/compatibility/tarot)에서
자연어 콘텐츠 생성을 위해 사용한다. 사주 엔진(core/*)은 이 모듈을 사용하지 않는다.

`generate_gemini_analysis()`는 원문 문자열을 반환하며, 호출부에서
```json 펜스를 제거하고 json.loads 한다. API 키 미설정 또는 호출 실패 시
예외를 발생시켜 호출부의 폴백 로직이 동작하도록 한다.
"""
import logging

import google.generativeai as genai

import config

logger = logging.getLogger(__name__)


def generate_gemini_analysis(prompt: str, system_instruction: str = "") -> str:
    """프롬프트를 Gemini에 전달하고 응답 텍스트를 반환한다.

    Raises:
        RuntimeError: GEMINI_API_KEY 미설정 시.
        Exception: Gemini 호출/응답 처리 실패 시 (google 라이브러리 예외 전파).
    """
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다. 폴백 데이터를 사용합니다.")

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL_NAME,
        system_instruction=system_instruction or None,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.7,
        },
    )
    response = model.generate_content(prompt)
    return response.text
