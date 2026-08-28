from datetime import datetime
from typing import Dict, Any
from core.saju_base import calculate_saju
from core.sipsin import get_sipsin

def get_today_ganji(date_obj: datetime = None) -> Dict[str, str]:
    """
    오늘 날짜 기준의 간지(천간/지지)를 산출합니다.
    (실제 만세력 연산 로직을 기반으로 오늘 일진 반환)
    """
    if date_obj is None:
        date_obj = datetime.now()
        
    # 오늘 날짜 기반 사주 연산 호출
    today_saju = calculate_saju(
        year=date_obj.year,
        month=date_obj.month,
        day=date_obj.day,
        hour=date_obj.hour,
        minute=date_obj.minute,
        gender='female',
        is_lunar=False
    )
    
    return {
        'day_gan': today_saju.get('day_master', '甲'),
        'day_ji': today_saju.get('day_branch', '子'),
        'ganji': f"{today_saju.get('day_master')}{today_saju.get('day_branch')}"
    }

def calculate_daily_fortune_element(user_saju: Dict[str, Any], date_obj: datetime = None) -> Dict[str, Any]:
    """
    사용자 사주 원국과 오늘 일진간의 십성 및 오행 기운을 연산합니다.
    """
    today_ganji = get_today_ganji(date_obj)
    day_master = user_saju.get('day_master', '甲')
    
    # 일간 기준 오늘 일간 천간/지지의 십성 산출
    sipsin_gan = get_sipsin(day_master, today_ganji['day_gan'])
    sipsin_ji = get_sipsin(day_master, today_ganji['day_ji'])
    
    # 십성 기반 오늘의 기본 운세 점수 가공 (예시 알골리즘)
    luck_score_map = {
        '정재': 95, '편재': 90, '식신': 88, '정관': 85,
        '정인': 82, '비견': 78, '상관': 75, '편인': 70,
        '편관': 65, '겁재': 60
    }
    
    score = luck_score_map.get(sipsin_gan, 80)
    
    return {
        'today_date': datetime.now().strftime('%Y-%m-%d') if date_obj is None else date_obj.strftime('%Y-%m-%d'),
        'today_ganji': today_ganji['ganji'],
        'today_sipsin_gan': sipsin_gan,
        'today_sipsin_ji': sipsin_ji,
        'luck_score': score,
        'favorable_element': user_saju.get('day_master')
    }
