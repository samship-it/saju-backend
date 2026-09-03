"""테스트는 실제 Gemini 호출 없이 결정적으로 동작해야 한다.

계약(구조) 테스트는 폴백 응답도 동일 스키마임을 검증하는 것이 목적이므로,
테스트 세션 동안 GEMINI_API_KEY 를 비워 실 API 호출/비용/레이트리밋을 피한다.
"""
import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def _disable_live_ai():
    import config
    saved_env = os.environ.pop("GEMINI_API_KEY", None)
    saved_cfg = config.GEMINI_API_KEY
    config.GEMINI_API_KEY = ""
    try:
        yield
    finally:
        config.GEMINI_API_KEY = saved_cfg
        if saved_env is not None:
            os.environ["GEMINI_API_KEY"] = saved_env
