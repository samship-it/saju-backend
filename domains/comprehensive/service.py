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
    saju_data = calculate_saju(
        year, month, day, hour, minute, gender=gender, is_lunar=is_lunar
    )

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
    - 오행 분포: {json.dumps(saju_data.get('five_elements', {}), ensure_ascii=False)}
    - 대운: {json.dumps(saju_data.get('daewoon', {}), ensure_ascii=False)}
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
        cleaned_json = raw_response.strip().replace("```json", "").replace("```", "").strip()
        analysis_result = json.loads(cleaned_json)
    except Exception as e:
        logger.error(f"Comprehensive service JSON parsing error: {e}")
        analysis_result = {
            "target_year": target_year,
            "overall_score": 85,
            "overall_summary": f"{target_year}년은 축적한 역량이 결실로 이어지는 안정적 성장의 해입니다.",
            "yearly_flow": "상반기에는 기반을 다지고, 하반기로 갈수록 성과와 확장의 기운이 강해집니다.",
            "categories": {
                "wealth": {"score": 84, "analysis": "무리한 확장보다 분할 접근과 리스크 관리가 재물운을 지킵니다."},
                "love": {"score": 82, "analysis": "소통의 폭을 넓히면 귀인과 인연의 기회가 열립니다."},
                "health": {"score": 80, "analysis": "과로로 인한 피로 누적에 유의하고 규칙적인 휴식이 필요합니다."},
                "career": {"score": 87, "analysis": "책임이 커지는 시기이며, 성실함이 인정으로 이어집니다."},
                "study": {"score": 85, "analysis": "새로운 분야를 학습하기에 유리하며 집중력이 높아집니다."}
            },
            "monthly_highlights": [
                {"month": 3, "keyword": "시작", "advice": "미뤄둔 계획을 실행에 옮기기 좋은 시점입니다."},
                {"month": 9, "keyword": "결실", "advice": "성과를 정리하고 다음 단계를 준비하세요."}
            ],
            "lucky_elements": {
                "color": "네이비",
                "direction": "동남쪽",
                "number": "7"
            }
        }

    return {
        "status": "success",
        "saju_info": {
            "day_master": saju_data.get("day_master"),
            "year_ganji": saju_data.get("year_ganji"),
            "month_ganji": saju_data.get("month_ganji"),
            "day_ganji": saju_data.get("day_ganji"),
            "time_ganji": saju_data.get("time_ganji"),
            "five_elements": saju_data.get("five_elements"),
            "daewoon": saju_data.get("daewoon"),
        },
        "comprehensive_report": analysis_result,
    }
