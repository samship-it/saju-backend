import os
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_dotenv() -> None:
    """의존성 없이 프로젝트 루트의 .env 를 읽어 os.environ 에 채운다.

    이미 설정된 환경변수는 덮어쓰지 않는다 (배포 환경변수 우선).
    """
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as e:  # pragma: no cover
        print(f"[config] .env 로드 실패: {e}")


_load_dotenv()

# 한국 표준시 타임존 설정 (KST)
KST = ZoneInfo("Asia/Seoul")

# Gemini 모델 및 API 키 설정 (모델명은 절대 변경하지 않는다)
GEMINI_MODEL_NAME = "gemini-3.5-flash"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 내부 API 검증용 키
API_SECRET_KEY = os.environ.get("INTERNAL_API_KEY", "default-secret-key")
