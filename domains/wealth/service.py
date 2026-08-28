import json
import logging
from typing import Dict, Any
from core.saju_base import calculate_saju
from core.gemini_client import generate_gemini_analysis

logger = logging.getLogger(__name__)

def analyze_wealth_and_market_strategy(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    gender: str = 'female',
    is_lunar: bool = False,
    market_context: str = "US Tech Stocks & Semiconductor ETFs (TQQQ, SOXL, USD)"
) -> Dict[str, Any]:
    """
    사주 재물운(정재/편재) 분석 및 증시/투자 시장 결합 맞춤 전략 생성
    """
    # 1. 사주 기본 명식 연산
    saju_data = calculate_saju(year, month, day, hour, minute, gender, is_lunar)
    
    # 2. LLM 해석용 프롬프트 구성
    system_instruction = """
    당신은 사주명리학과 글로벌 자산운용 메커니즘을 융합한 핀테크 금융 운세 자문가입니다.
    사용자의 재성(정재/편재) 및 식상 생재 흐름을 분석하여 리스크 관리, 매매 성향, 증시 시장 대응 전략을 제안합니다.
    반드시 유효한 JSON 형식으로만 응답해야 하며, Markdown 문법(```json 등)은 절대 사용하지 마세요.
    """

    prompt = f"""
    [사용자 사주 정보]
    - 성별: {saju_data.get('gender')}
    - 사주 원국: {saju_data.get('year_ganji')}년 {saju_data.get('month_ganji')}월 {saju_data.get('day_ganji')}일 {saju_data.get('time_ganji')}시
    - 일간(Day Master): {saju_data.get('day_master')}
    - 관심 시장/자산: {market_context}

    위 사주 명식 및 관심 시장을 바탕으로 자산 운용 및 매매 전략을 다음 JSON 스키마 구조로 분석해주세요:
    {{
        "wealth_profile": {{
            "wealth_type": "편재형(공격형/변동성 선호) 또는 정재형(안정축적형)",
            "wealth_score": 88,
            "overall_wealth_flow": "타고난 재물 그릇 및 현 시점의 재물 흐름 요약"
        }},
        "investment_style": {{
            "risk_appetite": "고위험 고수익(Aggressive) / 중립(Moderate) / 보수적(Conservative)",
            "recommended_asset_classes": ["미국 기술주/레버리지 ETF", "배당주", "가상자산", "채권/현금"],
            "trading_behavior_advice": "뇌동매매 방지 및 심리 컨트롤 가이드"
        }},
        "market_strategy": {{
            "market_focus": "{market_context}",
            "buy_timing_insight": "분할 매수 및 변동성 대응에 유리한 시점 조건",
            "risk_management_rule": "손절매/포트폴리오 리밸런싱 핵심 규칙"
        }},
        "lucky_financial_tips": {{
            "lucky_days_type": "일간 기준 재물 기운이 강해지는 요일/날짜 패턴",
            "actionable_mindset": "이번 분기 재테크 핵심 마인드셋"
        }}
    }}
    """

    try:
        raw_response = generate_gemini_analysis(prompt, system_instruction)
        cleaned_json = raw_response.strip().replace("```json", "").replace("```", "").strip()
        analysis_result = json.loads(cleaned_json)
    except Exception as e:
        logger.error(f"Wealth service JSON parsing error: {e}")
        # LLM 응답 실패 시 기본 폴백 데이터
        analysis_result = {
            "wealth_profile": {
                "wealth_type": "식상생재형 (분석 및 기술 기반 투자)",
                "wealth_score": 85,
                "overall_wealth_flow": "자신만의 철학과 데이터에 기반한 투자가 결실을 맺는 사주 흐름입니다."
            },
            "investment_style": {
                "risk_appetite": "Aggressive (분석 기반 고위험 고수익 선호)",
                "recommended_asset_classes": ["미국 빅테크", "반도체 레버리지 ETF", "성장주"],
                "trading_behavior_advice": "시장 변동성 확대 시 감정적 매매를 지양하고 분할 접근 방식을 유지하세요."
            },
            "market_strategy": {
                "market_focus": market_context,
                "buy_timing_insight": "지수 음봉 및 과매도 구간(RSI 저점) 활용 분할 매수",
                "risk_management_rule": "원칙 없는 추격 매수 금지 및 일정 비율 현금 비중 유지"
            },
            "lucky_financial_tips": {
                "lucky_days_type": "재성 및 식상 기운이 강화되는 날짜",
                "actionable_mindset": "철저한 리밸런싱 규칙 수립 및 멘탈 관리"
            }
        }

    return {
        "status": "success",
        "saju_info": {
            "day_master": saju_data.get('day_master'),
            "year_ganji": saju_data.get('year_ganji')
        },
        "wealth_report": analysis_result
    }
    