"""검수 스위치. 값은 호출 때마다 환경변수에서 읽는다.

기본은 모두 꺼져 있다. Render 환경변수를 켜기 전에는 고객 문장을 바꾸지 않는다.
API 키는 config.GEMINI_API_KEY 만 사용한다. 이 모듈은 키를 저장하거나 로그에 남기지 않는다.
"""
import os

import config  # noqa: F401  # .env 로드. 이미 있는 배포 환경변수는 덮어쓰지 않는다.

_ON = ("1", "true", "yes", "on")


def _flag(name: str, default: str = "") -> bool:
    return os.environ.get(name, default).strip().lower() in _ON


def enabled() -> bool:
    return _flag("PROOFREAD_ENABLED")


def llm_enabled() -> bool:
    return _flag("PROOFREAD_LLM_ENABLED")


def model() -> str:
    chosen = os.environ.get("PROOFREAD_LLM_MODEL", "").strip()
    if chosen:
        return chosen
    return os.environ.get("GEMINI_MODEL_NAME", "").strip() or config.GEMINI_MODEL_NAME


def monthly_budget_usd() -> float:
    try:
        return max(0.0, float(os.environ.get("PROOFREAD_MONTHLY_BUDGET_USD", "20")))
    except ValueError:
        return 20.0


def timeout_sec() -> float:
    try:
        return max(0.1, float(os.environ.get("PROOFREAD_TIMEOUT_SEC", "5")))
    except ValueError:
        return 5.0


def max_output_tokens() -> int:
    try:
        return max(32, int(os.environ.get("PROOFREAD_MAX_OUTPUT_TOKENS", "512")))
    except ValueError:
        return 512


def max_input_chars() -> int:
    try:
        return max(200, int(os.environ.get("PROOFREAD_MAX_INPUT_CHARS", "4000")))
    except ValueError:
        return 4000


def prompt_version() -> str:
    return os.environ.get("PROOFREAD_PROMPT_VERSION", "1").strip() or "1"


def policy_version() -> str:
    return os.environ.get("PROOFREAD_POLICY_VERSION", "1").strip() or "1"


def store_mode() -> str:
    return os.environ.get("PROOFREAD_STORE", "sqlite").strip().lower() or "sqlite"
