import json
import logging
import google.generativeai as genai
from typing import Tuple
import config

logging.basicConfig(
    filename="app_errors.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def call_gemini_json(prompt: str, fallback_data: dict) -> Tuple[dict, bool]:
    """
    Gemini 3.5 Flash 호출 함수 (API 키 미설정 시 즉시 폴백)
    """
    # API 키가 없으면 대기 없이 즉시 폴백 반환
    if not config.GEMINI_API_KEY:
        print("[AI Client] GEMINI_API_KEY가 설정되지 않아 기본 데이터를 즉시 반환합니다.")
        return fallback_data, True

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL_NAME,
            generation_config={"response_mime_type": "application/json", "temperature": 0.7}
        )
        response = model.generate_content(prompt)
        return json.loads(response.text), False
    except Exception as e:
        print(f"[AI Client] Gemini API 호출 예외 발생: {e}")
        logging.error(f"Gemini API 호출 에러: {e}")
        return fallback_data, True