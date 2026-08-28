import json
import logging
from typing import Dict, Any
from core.saju_base import calculate_saju
from core.gemini_client import generate_gemini_analysis

logger = logging.getLogger(__name__)

def generate_comprehensive_report(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    gender: str = 'female',
    is_lunar: bool = False,
    target_year: int = 2026
) -> Dict[str, Any]:
    """
    사주 원국 연산 및 Gemini LLM 기반 5대 종합 운세 리포트 생성
    """
    # 1. 사주 기본 명식 연산
    saju_data = calculate_saju(year, month, day, hour, minute, gender, is_lunar)
    
    # 2. LLM 해석용 프롬프트 구성
    system_instruction = """
    당신은 30년 경력의 동양 명리학 자문가입니다.
    사용자의 사주 명식과 지정된 연도(target_year)의 운성을 바탕으로 5대 종합 운세를 정밀 분석합니다.
    반드시 유효한 JSON 형식으로만 응답해야 하며, Markdown 문법(```json 등)은 절대 사용하지 마세요.
    """

    prompt = f"""
    [사용자 사주 정보]
    - 성별: {saju_data.get('gender')}
    - 사주 원국: {saju_data.get('year_ganji')}년 {saju_data.get('month_ganji')}월 {saju_data.get('day_ganji')}일 {saju_data.get('time_ganji')}시
    - 일간(Day Master): {saju_data.get('day_master')}
    - 분석 대상 연도: {target_year}년

    위 사주 명식을 기반으로 {target_year}년 종합 운세 리포트를 다음 JSON 스키마 구조로 작성해주세요:
    {{
        "target_year": {target_year},
        "overall_score": 88,
        "overall_summary": "한 줄 총운 요약 메시지",
        "yearly_flow": "연도별 운세의 핵심 흐름 분석 내용",
        "categories": {{
            "wealth": {{"score": 90, "analysis": "재물운 상세 분석"}},
            "love": {{"score": 85, "analysis": "애정/인연운 상세 분석"}},
            "health": {{"score": 80, "analysis": "건강/바이오리듬 상세 분석"}},
            "career": {{"score": 92, "analysis": "직장/사업/성취운 상세 분석"}},
            "study": {{"score": 87, "analysis": "학업/자기계발운 상세 분석"}}
        }},
        "monthly_highlights": [
            {{"month": 1, "keyword": "키워드", "advice": "월별 조언"}},
            {{"month": 2, "keyword": "키워드", "advice": "월별 조언"}}
        ],
        "lucky_elements": {{
            "color": "행운의 색상",
            "direction": "행운의 방위",
            "number": "행운의 숫자"
        }}
    }}
    """

    try:
        raw_response = generate_gemini_analysis(prompt, system_instruction)
        cleaned_json = raw_response.strip().replace("