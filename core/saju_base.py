import datetime
from typing import Dict, Any, Optional
import sajupy
from config import KST
from core.sipsin import calculate_sipsin
from core.interactions import check_ji_interactions
from core.life_stage import get_life_stage
from core.domain_derived import analyze_domain_derived

# === [운 명칭 woon 통일 import] ===
from core.daewoon import calculate_daewoon_info, get_seewoon_list, get_wolwoon_list

GAN_FIVE_ELEMENTS = {"甲": "목", "乙": "목", "丙": "화", "丁": "화", "戊": "토", "己": "토", "庚": "금", "辛": "금", "壬": "수", "癸": "수"}
JI_FIVE_ELEMENTS = {"子": "수", "丑": "토", "寅": "목", "卯": "목", "辰": "토", "巳": "화", "午": "화", "未": "토", "申": "금", "酉": "금", "戌": "토", "亥": "수"}

def calculate_saju(
    year: int, month: int, day: int,
    hour: Optional[int] = None, minute: Optional[int] = None,
    gender: str = "male", target_date: Optional[datetime.date] = None
) -> Dict[str, Any]:
    
    safe_hour = 0 if hour is None else hour
    safe_minute = 0 if minute is None else minute

    try:
        if hour is None:
            saju_res = sajupy.calculate_saju(year, month, day, city="Seoul", use_solar_time=True)
            hour_pillar = "미정"
        else:
            saju_res = sajupy.calculate_saju(year, month, day, safe_hour, safe_minute, city="Seoul", use_solar_time=True)
            hour_pillar = saju_res.get("hour_pillar", saju_res.get("time_pillar", "미정"))
    except Exception as e:
        print(f"sajupy 연산 예외 발생: {e}")
        saju_res = {}
        hour_pillar = "미정"

    year_pillar = saju_res.get("year_pillar", "癸亥")
    month_pillar = saju_res.get("month_pillar", "丁巳")
    day_pillar = saju_res.get("day_pillar", "己卯")

    day_master = saju_res.get("day_stem", day_pillar[0] if day_pillar else "己")
    day_branch = saju_res.get("day_branch", day_pillar[1] if len(day_pillar) > 1 else "卯")

    sipsin_map = {}
    pillars = [("year", year_pillar), ("month", month_pillar), ("day", day_pillar)]
    if hour_pillar != "미정":
        pillars.append(("hour", hour_pillar))

    all_jis = []
    for p_name, p_val in pillars:
        if len(p_val) >= 2:
            gan, ji = p_val[0], p_val[1]
            all_jis.append(ji)
            sipsin_map[f"{p_name}_gan"] = calculate_sipsin(day_master, gan, is_gan=True)
            sipsin_map[f"{p_name}_ji"] = calculate_sipsin(day_master, ji, is_gan=False)

    ji_interactions = check_ji_interactions(all_jis)

    t_date = target_date or datetime.datetime.now(KST).date()
    try:
        today_saju_res = sajupy.calculate_saju(t_date.year, t_date.month, t_date.day, city="Seoul", use_solar_time=True)
    except Exception:
        today_saju_res = {}

    age = t_date.year - year - ((t_date.month, t_date.day) < (month, day))

    # === [운 명칭 woon 통일 연산] ===
    daewoon_info = calculate_daewoon_info(year, month, day, gender, year_pillar)
    current_year = t_date.year
    seewoon_10yrs = get_seewoon_list(current_year, 10)
    current_wolwoon = get_wolwoon_list(current_year)

    derived_info = analyze_domain_derived({
        "sipsin": sipsin_map,
        "gender": gender
    })

    return {
        "birth_ganji": {"year": year_pillar, "month": month_pillar, "day": day_pillar, "time": hour_pillar},
        "today_ganji": {"year": today_saju_res.get("year_pillar", ""), "month": today_saju_res.get("month_pillar", ""), "day": today_saju_res.get("day_pillar", "")},
        "day_master": day_master,
        "day_branch": day_branch,
        "gender": gender,
        "sipsin": sipsin_map,
        "ji_interactions": ji_interactions,
        "age": age,
        "life_stage": get_life_stage(age),
        "derived": derived_info,
        # === [운 키값 명칭 woon 통일] ===
        "daewoon": daewoon_info,
        "seewoon_10years": seewoon_10yrs,
        "wolwoon_current_year": current_wolwoon
    }