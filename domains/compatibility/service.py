import json
import logging
from typing import Dict, Any
from core.saju_base import calculate_saju
from core.gemini_client import generate_gemini_analysis
from domains.compatibility.engine import calculate_compatibility_interactions

logger = logging.getLogger(__name__)

def analyze_compatibility_report(
    p1_info: Dict[str, Any],
    p2_info: Dict[str, Any],
    relation_type: str = "romantic"  # romantic(연인/부부), business(동업/비즈니스), friend(친구)
) -> Dict[str, Any]:
    """
    두 사주 원국 연산 및 상호작용(합/충)을 바탕으로 궁합 리포트 생성
    """
    # 1. 두 사람의 사주 기본 명식 연산
    saju1 = calculate_saju(
        p1_info['year'], p1_info['month'], p1_info['day'],
        p1_info.get('hour', 0), p1_info.get('minute', 0),
        p1_info.get('gender', 'female'), p1_info.get('is_lunar', False)
    )
    
    saju2 = calculate_saju(
        p2_info['year'], p2_info['month'], p2_info['day'],
        p2_info.get('hour', 0), p2_info.get('minute', 0),
        p2_info.get('gender', 'male'), p2_info.get('is_lunar', False)
    )

    # 2. 사주간 합/충 명리 연산 엔진 수행
    interaction_data = calculate_compatibility_interactions(saju1, saju2)

    # 3. LLM 해석용 프롬프트 구성
    system_instruction = """
    당신은 정통 명리학과 관계 심리학을 결합한 궁합 컨설턴트입니다.
    두 사람의 사주 명식과 천간/지지 합·충 결과를 바탕으로 두 사람의 궁합 지수, 시너지, 시련 극복 조언을 제시합니다.
    반드시 유효한 JSON 형식으로만 응답해야 하며, Markdown 문법(```json 등)은 절대 사용하지 마세요.
    """

    prompt = f"""
    [관계 유형]: {relation_type}
    [본인 사주]: {saju1.get('year_ganji')}년 {saju1.get('month_ganji')}월 {saju1.get('day_ganji')}일 {saju1.get('time_ganji')}시 (일간: {saju1.get('day_master')})
    [상대방 사주]: {saju2.get('year_ganji')}년 {saju2.get('month_ganji')}월 {saju2.get('day_ganji')}일 {saju2.get('time_ganji')}시 (일간: {saju2.get('day_master')})
    [명리 연산 결과]:
    - 일간 관계: {interaction_data['day_master_relation']}
    - 일지 관계: {interaction_data['day_jiji_relation']}

    위 데이터를 바탕으로 두 사람의 궁합 분석 보고서를 다음 JSON 스키마 구조로 작성해주세요:
    {{
        "overall_compatibility_score": 88,
        "headline": "한 줄 궁합 총평 메시지",
        "harmony_analysis": {{
            "emotional_connection": "정서적/소통 궁합 분석",
            "values_and_lifestyle": "가치관 및 라이프스타일 조화도",
            "synergy_points": ["서로에게 도움이 되는 시너지 포인트 1", "시너지 포인트 2"]
        }},
        "conflict_management": {{
            "potential_friction": "부딪힐 수 있는 갈등 요소",
            "solution_advice": "갈등을 지혜롭게 풀어가는 구체적 조언"
        }},
        "relationship_roadmap": "함께 맞춰가면 좋은 향후 관계 발전 가이드"
    }}
    """

    try:
        raw_response = generate_gemini_analysis(prompt, system_instruction)
        cleaned_json = raw_response.strip().replace("```json", "").replace("```", "").strip()
        analysis_result = json.loads(cleaned_json)
    except Exception as e:
        logger.error(f"Compatibility service JSON parsing error: {e}")
        analysis_result = {
            "overall_compatibility_score": interaction_data['compatibility_score_base'],
            "headline": "서로의 다른 점이 서로를 더욱 빛나게 만드는 궁합입니다.",
            "harmony_analysis": {
                "emotional_connection": "상호보완적 기운이 강하여 깊은 유대감을 형성할 수 있습니다.",
                "values_and_lifestyle": "대화를 통해 이견을 조율할수록 시너지가 증대됩니다.",
                "synergy_points": ["서로의 부족한 기운을 채워주는 보완 관계", "목표 지향적 협업 능력"]
            },
            "conflict_management": {
                "potential_friction": "일처리 방식이나 표현 스타일의 차이로 인한 오해",
                "solution_advice": "상대방의 입장을 한 번 더 경청하는 여유가 필요합니다."
            },
            "relationship_roadmap": "서로의 장점을 존중하고 단점을 싸안아줄 때 최고의 파트너십을 이룹니다."
        }

    return {
        "status": "success",
        "person1_saju": {"day_master": saju1.get('day_master'), "ganji": saju1.get('day_ganji')},
        "person2_saju": {"day_master": saju2.get('day_master'), "ganji": saju2.get('day_ganji')},
        "engine_interactions": interaction_data,
        "compatibility_report": analysis_result
    }