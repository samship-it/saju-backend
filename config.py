import os
from zoneinfo import ZoneInfo

# 한국 표준시 타임존 설정 (KST)
KST = ZoneInfo("Asia/Seoul")

# Gemini 모델 및 API 키 설정
GEMINI_MODEL_NAME = "gemini-3.5-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 내부 API 검증용 키
API_SECRET_KEY = os.environ.get("INTERNAL_API_KEY", "default-secret-key")