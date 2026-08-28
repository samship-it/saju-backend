import json
from typing import Dict, Any, Tuple
from shared.ai_client import call_gemini_json

def generate_daily_fortune(saju_data: Dict[str, Any], market_summary: str) -> Tuple[dict, bool]:
    day_master = saju_data.get("day_master", "己")
    age = saju_data.get("age", 40)
    gender = saju_data.get("gender", "female")
    sipsin_map = saju_data.get("sipsin", {})
    today_ganji = saju_data.get("today_ganji", {})
    
    prompt = f"""
    당신은 사주명리학과 금융 시장 흐름을 조화롭게 해석하는 전문 운세 컨설턴트입니다.
    아래 사용자의 사주 분석 정보와 오늘 시장 요약을 바탕으로 정확히 규격화된 데일리 운세를 생성하세요.

    [사용자 프로필 및 운세 정보]
    - 일간(Day Master): {day_master}
    - 나이/성별: 만 {age}세 / {gender}
    - 십신 정보: {json.dumps(sipsin_map, ensure_ascii=False)}
    - 오늘의 일진(간지): {json.dumps(today_ganji, ensure_ascii=False)}

    [오늘의 시장 요약]
    {market_summary}

    [답변 출력 규칙]
    반드시 다음 JSON 구조로만 응답하세요. 다른 설명이나 마크다운 표기는 절대로 포함하지 마세요.

    JSON 구조:
    {{
      "overall_score": 88,
      "summary": "오늘 하루 종합 요약 (2문장)",
      "overall_fortune": "일간, 오늘 간지, 오행 균형을 반영한 종합 운세 상세 설명",
      "finance_fortune": "재성/식상생재 및 시장 흐름을 고려한 금전/투자 조언",
      "love_fortune": "배우자성 및 일지 합충을 반영한 애정/소통 운세",
      "work_fortune": "관성/인성/식상 기반 직장/학업/비즈니스 가이드",
      "keywords": ["상관운", "재성발복", "신중함"],
      "action_tip": "오늘 강하게 작용하는 오행/십신을 반영한 실천적인 추천 행동",
      "lucky_items": {{
        "color": "추천 행운의 색상 (예: 네이비)",
        "direction": "추천 행운의 방위 (예: 동남쪽)",
        "number": 7
      }}
    }}
    """

    fallback_data = {
        "overall_score": 85,
        "summary": f"오늘 일간({day_master})의 기운이 안정적인 조화를 이루는 날입니다.",
        "overall_fortune": "일간과 오늘 간지의 흐름이 원만하여 차분하게 내실을 다지기에 적합한 하루입니다.",
        "finance_fortune": "재성 흐름을 점검하며 무리한 지출을 줄이고 안정적인 자산 관리에 집중하세요.",
        "love_fortune": "일지 가중치와 조화를 통해 상대방의 의견을 경청하면 유대감이 깊어집니다.",
        "work_fortune": "관성과 인성의 균형으로 계획한 업무를 차분하게 성취할 수 있는 날입니다.",
        "keywords": ["자산성찰", "평정심", "소통"],
        "action_tip": "중요한 의사결정 전 5분간 우선순위를 재점검해 보세요.",
        "lucky_items": {
            "color": "네이비",
            "direction": "동남쪽",
            "number": 8
        }
    }

    result_json, is_fallback = call_gemini_json(prompt, fallback_data)
    return result_json, is_fallback