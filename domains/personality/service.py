import json
import logging
from typing import Dict, Any
from core.saju_base import calculate_saju
from core.gemini_client import generate_gemini_analysis

logger = logging.getLogger(__name__)

def analyze_personality_and_talent(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    gender: str = 'female',
    is_lunar: bool = False
) -> Dict[str, Any]:
    """
    사주 원국 기반 타고난 성격, 기질, 적성 및 직업적 재능 정밀 분석
    """
    # 1. 사주 기본 명식 및 오행 분석
    saju_data = calculate_saju(year, month, day, hour, minute, gender, is_lunar)
    
    # 2. LLM 해석용 프롬프트 구성
    system_instruction = """
    당신은 사주명리학과 현대 심리학/적성 검사를 결합하여 개인의 성격과 잠재 능력을 분석하는 명리 심리 컨설턴트입니다.
    사용자의 일간, 오행의 치우침, 십성 구성을 기반으로 정교한 기질 분석을 제공합니다.
    반드시 유효한 JSON 형식으로만 응답해야 하며, Markdown 문법(```json 등)은 절대 사용하지 마세요.
    """

    prompt = f"""
    [사용자 사주 정보]
    - 성별: {saju_data.get('gender')}
    - 사주 원국: {saju_data.get('year_ganji')}년 {saju_data.get('month_ganji')}월 {saju_data.get('day_ganji')}일 {saju_data.get('time_ganji')}시
    - 일간(Day Master): {saju_data.get('day_master')}
    - 오행 분포: {json.dumps(saju_data.get('five_elements', {}), ensure_ascii=False)}

    위 사주 명식을 기반으로 타고난 성격 및 적성을 다음 JSON 스키마 구조로 분석해주세요:
    {{
        "core_traits": {{
            "day_master_nature": "일간 중심의 핵심 성격 및 본질 설명",
            "element_balance_analysis": "오행 균형 및 발달된 기운 분석",
            "mbti_style_summary": "명리학으로 본 성격 유형 한 줄 요약"
        }},
        "strengths": [
            "타고난 강점 및 유용한 역량 1",
            "타고난 강점 및 유용한 역량 2",
            "타고난 강점 및 유용한 역량 3"
        ],
        "weaknesses_to_mind": [
            "주의해야 할 성격적 단점이나 blind spot 1",
            "주의해야 할 성격적 단점이나 blind spot 2"
        ],
        "aptitude_and_career": {{
            "work_style": "일할 때의 스타일 및 조직 내 역할",
            "recommended_fields": ["추천 직업 분야 1", "추천 직업 분야 2", "추천 직업 분야 3"],
            "financial_mindset": "돈과 자산을 대