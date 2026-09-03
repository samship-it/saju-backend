"""레거시 진입점 — shared.ai_client 로 위임한다.

도메인 서비스가 core.gemini_client.generate_gemini_analysis 를 import 하던 것을 유지.
"""
from shared.ai_client import generate_gemini_analysis, call_gemini_json

__all__ = ["generate_gemini_analysis", "call_gemini_json"]
