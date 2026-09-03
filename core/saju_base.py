import datetime
from typing import Dict, Any, Optional, List

import sajupy

from config import KST
from core.constants import GAN_ELEM, JI_ELEM
from core.sipsin import calculate_sipsin
from core.interactions import check_ji_interactions, analyze_branch_relations
from core.life_stage import get_life_stage
from core.twelve_unseong import twelve_unseong_map
from core.sinsal import analyze_sinsal
from core.strength import analyze_strength, analyze_gyeokguk, spouse_star
from core.domain_derived import analyze_domain_derived
from core.daewoon import calculate_daewoon_info, get_seewoon_list, get_wolwoon_list

GAN_FIVE_ELEMENTS = GAN_ELEM
JI_FIVE_ELEMENTS = JI_ELEM

# 서울(종로) 경도. sajupy 에 city="Seoul" 을 넘기면 매 호출마다 지오코딩 네트워크 요청이 발생하고
# (429 레이트리밋 시 표준시로 조용히 폴백 → 결과 비일관) 느리므로, 경도를 직접 고정한다.
_SEOUL_LON = 126.9783


def _sajupy_calc(y, m, d, hh, mm):
    return sajupy.calculate_saju(y, m, d, hh, mm, longitude=_SEOUL_LON, use_solar_time=True)


def _count_five_elements(pillars) -> Dict[str, int]:
    counts = {"목": 0, "화": 0, "토": 0, "금": 0, "수": 0}
    for p_val in pillars:
        if not p_val or len(p_val) < 2:
            continue
        gan_elem = GAN_ELEM.get(p_val[0])
        ji_elem = JI_ELEM.get(p_val[1])
        if gan_elem:
            counts[gan_elem] += 1
        if ji_elem:
            counts[ji_elem] += 1
    return counts


def sipsin_of_ganji(day_master: str, ganji: str) -> Dict[str, str]:
    """임의 간지(2자)의 일간 대비 천간/지지 십신."""
    if not ganji or len(ganji) < 2:
        return {}
    return {
        "gan": calculate_sipsin(day_master, ganji[0], is_gan=True),
        "ji": calculate_sipsin(day_master, ganji[1], is_gan=False),
    }


def _pillar_from_sajupy(res: Dict[str, Any], key_pillar: str, key_stem: str, key_branch: str, fallback: str) -> str:
    p = res.get(key_pillar)
    if p and len(p) >= 2:
        return p
    s, b = res.get(key_stem), res.get(key_branch)
    if s and b:
        return f"{s}{b}"
    return fallback


def calculate_saju(
    year: int, month: int, day: int,
    hour: Optional[int] = None, minute: Optional[int] = None,
    gender: str = "male", is_lunar: bool = False,
    target_date: Optional[datetime.date] = None,
    partner_exists: bool = False,
) -> Dict[str, Any]:

    safe_hour = 0 if hour is None else hour
    safe_minute = 0 if minute is None else minute
    birth_time_known = hour is not None

    if isinstance(target_date, str) and target_date:
        target_date = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()

    if is_lunar:
        try:
            conv = sajupy.lunar_to_solar(year, month, day)
            year, month, day = conv["solar_year"], conv["solar_month"], conv["solar_day"]
        except Exception as e:
            print(f"음력->양력 변환 예외: {e}")

    try:
        if not birth_time_known:
            saju_res = _sajupy_calc(year, month, day, 12, 0)
            hour_pillar = "미정"
        else:
            saju_res = _sajupy_calc(year, month, day, safe_hour, safe_minute)
            hour_pillar = _pillar_from_sajupy(saju_res, "hour_pillar", "hour_stem", "hour_branch", "미정")
    except Exception as e:
        print(f"sajupy 연산 예외: {e}")
        saju_res = {}
        hour_pillar = "미정"

    year_pillar = _pillar_from_sajupy(saju_res, "year_pillar", "year_stem", "year_branch", "癸亥")
    month_pillar = _pillar_from_sajupy(saju_res, "month_pillar", "month_stem", "month_branch", "丁巳")
    day_pillar = _pillar_from_sajupy(saju_res, "day_pillar", "day_stem", "day_branch", "己卯")

    day_master = saju_res.get("day_stem", day_pillar[0])
    day_branch = saju_res.get("day_branch", day_pillar[1] if len(day_pillar) > 1 else "卯")

    pillars = {"year": year_pillar, "month": month_pillar, "day": day_pillar}
    if hour_pillar != "미정":
        pillars["hour"] = hour_pillar

    branches = {pos: gz[1] for pos, gz in pillars.items() if len(gz) > 1}

    # 십신 맵
    sipsin_map: Dict[str, str] = {}
    for pos, gz in pillars.items():
        if len(gz) >= 2:
            sipsin_map[f"{pos}_gan"] = calculate_sipsin(day_master, gz[0], is_gan=True)
            sipsin_map[f"{pos}_ji"] = calculate_sipsin(day_master, gz[1], is_gan=False)

    ji_interactions = check_ji_interactions(list(branches.values()))
    branch_relations = analyze_branch_relations(branches)
    five_elements = _count_five_elements(list(pillars.values()))

    unseong = twelve_unseong_map(day_master, branches)
    sinsal = analyze_sinsal(day_master, branches, pillars)
    strength = analyze_strength(day_master, pillars, birth_time_known)
    gyeokguk = analyze_gyeokguk(day_master, pillars)
    spouse = spouse_star(day_master, gender, pillars, sipsin_map)

    # 날짜 컨텍스트
    t_date = target_date or datetime.datetime.now(KST).date()
    try:
        today_res = _sajupy_calc(t_date.year, t_date.month, t_date.day, 12, 0)
    except Exception:
        today_res = {}
    today_day_pillar = _pillar_from_sajupy(today_res, "day_pillar", "day_stem", "day_branch", "")
    today_year_pillar = _pillar_from_sajupy(today_res, "year_pillar", "year_stem", "year_branch", "")
    today_month_pillar = _pillar_from_sajupy(today_res, "month_pillar", "month_stem", "month_branch", "")

    age = t_date.year - year - ((t_date.month, t_date.day) < (month, day))

    daewoon_info = calculate_daewoon_info(year, month, day, gender, year_pillar, month_pillar)
    current_daewoon = _current_daewoon(daewoon_info, age)
    seewoon_10yrs = get_seewoon_list(t_date.year, 10)
    wolwoon_current = get_wolwoon_list(t_date.year)

    # 운 오버레이 십신 (일운/세운/월운 vs 일간)
    ilwoon_sipsin = sipsin_of_ganji(day_master, today_day_pillar)
    current_seewoon_ganji = seewoon_10yrs[0]["ganji"] if seewoon_10yrs else ""
    sewoon_sipsin = sipsin_of_ganji(day_master, current_seewoon_ganji)
    overlay = [v for v in ilwoon_sipsin.values()] + [v for v in sewoon_sipsin.values()]
    if current_daewoon:
        overlay += list(sipsin_of_ganji(day_master, current_daewoon.get("ganji", "")).values())

    saju: Dict[str, Any] = {
        "year_ganji": year_pillar,
        "month_ganji": month_pillar,
        "day_ganji": day_pillar,
        "time_ganji": hour_pillar if hour_pillar != "미정" else "",
        "birth_ganji": {"year": year_pillar, "month": month_pillar, "day": day_pillar, "time": hour_pillar},
        "day_master": day_master,
        "day_branch": day_branch,
        "day_master_elem": GAN_ELEM.get(day_master, ""),
        "gender": gender,
        "is_lunar": is_lunar,
        "birth_time_known": birth_time_known,
        "five_elements": five_elements,
        "sipsin": sipsin_map,
        "jijanggan": {pos: [h for h, _ in _JJG(ji)] for pos, ji in branches.items()},
        "twelve_unseong": unseong,
        "sinsal": sinsal,
        "strength": strength,
        "gyeokguk": gyeokguk,
        "spouse_star": spouse,
        "ji_interactions": ji_interactions,
        "branch_relations": branch_relations,
        # 운
        "daewoon": daewoon_info,
        "current_daewoon": current_daewoon,
        "seewoon_10years": seewoon_10yrs,
        "wolwoon_current_year": wolwoon_current,
        "today_ganji": {"year": today_year_pillar, "month": today_month_pillar, "day": today_day_pillar},
        "ilwoon_sipsin": ilwoon_sipsin,
        "sewoon_sipsin": sewoon_sipsin,
        "overlay_sipsin": overlay,
        # 공통 규칙 필드
        "target_date": t_date.strftime("%Y-%m-%d"),
        "target_month": t_date.month,
        "target_year": t_date.year,
        "age": age,
        "life_stage": get_life_stage(age),
        "partner_exists": partner_exists,
    }

    saju["derived"] = analyze_domain_derived(saju, overlay_sipsin=overlay)
    return saju


def _JJG(ji: str):
    from core.constants import JIJANGGAN
    return JIJANGGAN.get(ji, [])


def _current_daewoon(daewoon_info: Dict[str, Any], age: int) -> Dict[str, Any]:
    flow = daewoon_info.get("flow", []) if daewoon_info else []
    cur = {}
    for item in flow:
        if item.get("start_age", 999) <= age:
            cur = item
        else:
            break
    return cur
