import json
from typing import Dict, Any, Tuple
from shared.ai_client import call_gemini_json
from core.saju_base import calculate_saju
from core.daewoon import calculate_daewoon, calculate_seewoon
from core.market import fetch_market_data

def build_full_comprehensive_report(year: int, month: int, day: int, hour: int, minute: int, gender: str, is_lunar: bool = False) -> Tuple[dict, bool]:
    # 1. 명리학 기본 데이터 산출
    saju = calculate_saju(year, month, day, hour, minute, gender, is_lunar)
    daewoon_data = calculate_daewoon(saju)
    seewoon_data = calculate_seewoon(2026)
    
    # 2. 금융 시장 데이터 (재물운 섹션 전용)
    market_data = fetch_market_data()
    
    # 3. AI 프롬프트 설계 (분야별 디테일 운세 분리)
    prompt = f"""
    당신은 사주명리학과 심리 분석, 금융 리스크 관리에 통달한 명리 컨설턴트입니다.
    아래 사주 데이터와 세운(seewoon), 대운(daewoon)을 바탕으로 카테고리별 디테일 운세 리포트를 작성해 주세요.

    [사용자 기본 사주 및 운 데이터]
    - 일간(Day Master): {saju.get('day_master')} / 일지: {saju.get('day_branch')}
    - 오행 구성: {json.dumps(saju.get('five_elements', {}), ensure_ascii=False)}
    - 2026년 세운(seewoon): {seewoon_data.get('seewoon_ganji')} ({seewoon_data.get('seewoon_elements')})
    - 현재 대운(daewoon): {json.dumps(daewoon_data.get('current_daewoon', {}), ensure_ascii=False)}

    [재물운 전용 거시경제 지표]
    - S&P500: {market_data.get('sp500', 'N/A')}, NASDAQ: {market_data.get('nasdaq', 'N/A')}, VIX: {market_data.get('vix', 'N/A')}

    다음 JSON 규격에 맞춰 각 항목을 디테일하게 작성하세요:
    - total_2026_woon: 2026년 총운 (올해의 핵심 키워드 및 흐름)
    - wealth_woon: 금전/재물운 (시장 지표와 사주 원국을 결합한 자산 운용 전략)
    - love_relationship_woon: 애정 및 대인관계운 (연애, 귀인, 인간관계)
    - health_psychology_woon: 건강 및 심리운 (오행 균형 기반 주의점과 멘탈 케어)
    - travel_movement_woon: 여행 및 이동운 (이사, 이직, 해외/지방 이동, 여행 가이드)
    - action_checklist: 올해 실천해야 할 실행 리스트 (3가지)
    """

    fallback_data = {
        'total_2026_woon': f"2026년 丙午년은 {saju.get('day_master')}일간에게 새로운 변화와 도약의 기회가 찾아오는 해입니다.",
        'wealth_woon': f"현재 증시 환경({market_data.get('market_status')})과 사주 흐름을 고려할 때, 안정적인 분할 매수와 리스크 관리가 재물운을 높여줍니다.",
        'love_relationship_woon': "새로운 인연이나 조력자(귀인)의 도움이 예상되는 해입니다. 주변과의 소통을 늘리세요.",
        'health_psychology_woon': "오행 불균형으로 인한 피로감에 유의해야 합니다. 충분한 휴식과 일과 삶의 균형이 필요합니다.",
        'travel_movement_woon': "이동수가 들어오는 시기입니다. 장거리 여행이나 환경 변화가 새로운 영감을 줄 수 있습니다.",
        'action_checklist': ['자산 리밸런싱 시행', '감정 소모 줄이기', '여행/휴식을 통한 에너지 충전']
    }

    result_json, is_fallback = call_gemini_json(prompt, fallback_data)
    
    return {
        'saju_summary': {'day_master': saju.get('day_master'), 'five_elements': saju.get('five_elements')},
        'daewoon_info': daewoon_data,
        'seewoon_info': seewoon_data,
        'market_snapshot': market_data,
        'report': result_json
    }, is_fallback
