import csv
import math
import logging
import os
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, Any, List, Tuple
from korean_lunar_calendar import KoreanLunarCalendar

from config import KST

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 60갑자 및 천간/지지 기초 데이터
# ---------------------------------------------------------------------------
GAN = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계"]
JI = ["자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해"]

# 천간 음양 (True: 양, False: 음)
GAN_YANG = [True, False, True, False, True, False, True, False, True, False]

# 월간 계산용 (월두법 테이블)
MONTH_GAN_START = {
    "갑": 2, "기": 2,  # 병인월 시작 (index 2)
    "을": 4, "경": 4,  # 무인월 시작 (index 4)
    "병": 6, "신": 6,  # 경인월 시작 (index 6)
    "정": 8, "임": 8,  # 임인월 시작 (index 8)
    "무": 0, "계": 0   # 갑인월 시작 (index 0)
}

# ---------------------------------------------------------------------------
# 해결책 1: 음력(is_lunar) -> 양력 완전 자동 변환 로직
# ---------------------------------------------------------------------------
def convert_lunar_to_solar(year: int, month: int, day: int, is_leap_month: bool = False) -> datetime:
    """
    korean_lunar_calendar를 사용하여 음력 생년월일을 양력 datetime으로 변환합니다.
    """
    calendar = KoreanLunarCalendar()
    success = calendar.setLunar(year, month, day, is_leap_month)
    
    if not success:
        logger.error(f"음력 변환 실패: {year}-{month}-{day} (윤달: {is_leap_month}). 입력값 기본 유지.")
        return datetime(year, month, day)
        
    return datetime(calendar.solarYear, calendar.solarMonth, calendar.solarDay)

# ---------------------------------------------------------------------------
# 해결책 2: 입춘(2월 4일 경) 절기 기준 연도/세운 보정 로직
# ---------------------------------------------------------------------------
def get_saju_year_and_ganji(birth_dt: datetime) -> Tuple[int, str, str]:
    """
    입춘(2월 4일 00:00 간이 절기) 기준 사주 연도와 연주(60갑자)를 산출합니다.
    1~2월 초 생일자는 입춘 전일 경우 전년도 간지를 적용합니다.
    """
    year = birth_dt.year
    lichun_dt = datetime(year, 2, 4, 0, 0, 0)  # 정밀 절기시 기준 (2월 4일)
    
    # 입춘 전이면 전년도 연도로 보정
    saju_year = year - 1 if birth_dt < lichun_dt else year
    
    # 60갑자 계산 (1900년 = 경자년 기준)
    gan_idx = (saju_year - 4) % 10
    ji_idx = (saju_year - 4) % 12
    
    year_gan = GAN[gan_idx]
    year_ji = JI[ji_idx]
    year_ganji = f"{year_gan}{year_ji}"
    
    return saju_year, year_gan, year_ganji

# ---------------------------------------------------------------------------
# 해결책 3: 절기 시각 일수 기반 정밀 대운수(교운 나이) 산출 로직
# ---------------------------------------------------------------------------
# 월주(月柱)가 바뀌는 경계인 12절(節)만 대운수 계산에 쓴다. 24절기 중 나머지 12개
# (우수/춘분/곡우/소만/하지/대서/처서/추분/상강/소설/동지/대한)는 "중기(中氣)"로,
# 월이 바뀌는 시점이 아니므로 대운수 기준에서 제외한다.
_JEOL_TERMS_KO = frozenset({
    "입춘", "경칩", "청명", "입하", "망종", "소서",
    "입추", "백로", "한로", "입동", "대설", "소한",
})


@lru_cache(maxsize=1)
def _load_jeol_times() -> Tuple[datetime, ...]:
    """sajupy 패키지에 내장된 1900~2100년 실제 24절기 정밀 시각(KASI 기준, 분 단위) 테이블에서
    12절(節)의 절입 시각만 뽑아 정렬된 튜플로 캐시한다.

    sajupy 는 이미 requirements.txt 에 있고 core/saju_base.py 가 원국 계산에 쓰는 검증된
    의존성이므로, 별도로 skyfield/ephem 같은 천문 계산 라이브러리를 새로 추가하지 않고
    이 패키지가 들고 있는 calendar_data.csv(연-월-일 단위 만세력 + 절기 정밀시각)를 재사용한다.
    """
    import sajupy
    csv_path = os.path.join(os.path.dirname(sajupy.__file__), "calendar_data.csv")
    times: List[datetime] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            term_ko = row.get("solar_term_korean")
            term_time = row.get("term_time")
            if term_ko not in _JEOL_TERMS_KO or not term_time:
                continue
            times.append(datetime.strptime(term_time, "%Y%m%d%H%M"))
    times.sort()
    return tuple(times)


def calculate_exact_daewoon_num(birth_dt: datetime, is_forward: bool) -> int:
    """
    생년월시와 실제 절입(節入) 시각 사이의 정확한 일수를 계산하여 정밀 대운수를 산출합니다.
    - 순행: 생일부터 '다음에 오는 절입일시'까지의 일수 / 3
    - 역행: 생일부터 '직전에 지난 절입일시'까지의 일수 / 3
    (전통 명리학 계산법: 3일 = 1년, 나머지는 반올림)
    """
    times = _load_jeol_times()

    if not times or birth_dt < times[0] or birth_dt > times[-1]:
        # sajupy calendar_data.csv 수록 범위(1900~2100) 밖의 극단적 입력에 대한 안전망.
        # 실제 서비스 대상 생년월일에서는 발생하지 않아야 정상이므로 경고를 남긴다.
        logger.warning(
            "calculate_exact_daewoon_num: %s 는 절기 테이블 범위(1900~2100) 밖입니다. "
            "근사값(15일 간격)으로 대체합니다.", birth_dt,
        )
        days = 15.0
    elif is_forward:
        idx = bisect_left(times, birth_dt)  # 생일 이후(같은 시각 포함) 첫 절입
        target = times[idx]
        days = (target - birth_dt).total_seconds() / 86400.0
    else:
        idx = bisect_right(times, birth_dt) - 1  # 생일 이전(같은 시각 포함) 마지막 절입
        target = times[idx]
        days = (birth_dt - target).total_seconds() / 86400.0

    # 사주 명리학 계산법: 3일 = 1년, 나머지는 반올림(사사오입)
    daewoon_num = math.floor(days / 3.0 + 0.5)
    return max(1, daewoon_num)

# ---------------------------------------------------------------------------
# 부가 로직: 10년 단위 대운 흐름 및 60갑자 세운 목록 생성
# ---------------------------------------------------------------------------
def generate_daewoon_list(year_gan: str, month_ganji: str, is_forward: bool, start_age: int, count: int = 8) -> List[Dict[str, Any]]:
    """대운수부터 10년 단위 대운 간지 흐름 목록을 생성합니다."""
    # 월주 간지 분리 (기본값)
    m_gan = month_ganji[0] if len(month_ganji) > 0 else "갑"
    m_ji = month_ganji[1] if len(month_ganji) > 1 else "인"
    
    gan_idx = GAN.index(m_gan) if m_gan in GAN else 0
    ji_idx = JI.index(m_ji) if m_ji in JI else 2
    
    daewoon_list = []
    step = 1 if is_forward else -1
    
    for i in range(1, count + 1):
        gan_idx = (gan_idx + step) % 10
        ji_idx = (ji_idx + step) % 12
        age = start_age + (i - 1) * 10
        
        daewoon_ganji = f"{GAN[gan_idx]}{JI[ji_idx]}"
        daewoon_list.append({
            "step": i,
            "start_age": age,
            "ganji": daewoon_ganji,
            "label": f"{age}세 대운 ({daewoon_ganji})"
        })
    return daewoon_list

def generate_sewoon_list(start_year: int, count: int = 10) -> List[Dict[str, Any]]:
    """60갑자 순환 기준 세운(연운) 리스트 생성"""
    sewoon_list = []
    for i in range(count):
        cy = start_year + i
        g_idx = (cy - 4) % 10
        j_idx = (cy - 4) % 12
        ganji = f"{GAN[g_idx]}{JI[j_idx]}"
        sewoon_list.append({
            "year": cy,
            "ganji": ganji,
            "label": f"{cy}년 ({ganji}년)"
        })
    return sewoon_list

# ---------------------------------------------------------------------------
# 메인 통합 서비스 함수 (라우터/엔드포인트에서 이 함수를 호출)
# ---------------------------------------------------------------------------
def calculate_saju_daewoon_sewoon(
    year: int,
    month: int,
    day: int,
    hour: int = 12,
    is_lunar: bool = False,
    is_leap_month: bool = False,
    gender: str = "female",  # "male" 또는 "female"
    month_ganji: str = "병인"  # 기본 월주
) -> Dict[str, Any]:
    """
    [통합 실행] 음력 변환 -> 입춘 세운 보정 -> 대운수/대운 흐름 -> 세운 목록 산출
    """
    # 1. [해결1] 음력 입력 시 양력 자동 변환
    if is_lunar:
        logger.info(f"[만세력] 음력 변환 실행: {year}-{month}-{day}")
        solar_dt = convert_lunar_to_solar(year, month, day, is_leap_month)
        solar_dt = solar_dt.replace(hour=hour)
    else:
        solar_dt = datetime(year, month, day, hour)

    # 2. [해결2] 입춘 기준 사주 연도 및 연간 산출
    saju_year, year_gan, year_ganji = get_saju_year_and_ganji(solar_dt)

    # 3. 양남음녀 / 음남양녀 순행/역행 판별
    is_male = (gender.lower() == "male")
    year_gan_idx = GAN.index(year_gan)
    is_yang_gan = GAN_YANG[year_gan_idx]
    
    # 양남음녀 = 순행, 음남양녀 = 역행
    if (is_male and is_yang_gan) or (not is_male and not is_yang_gan):
        is_forward = True
        direction_str = "순행"
    else:
        is_forward = False
        direction_str = "역행"

    # 4. [해결3] 정밀 대운수(교운 나이) 계산
    daewoon_num = calculate_exact_daewoon_num(solar_dt, is_forward)

    # 5. 대운 간지 흐름 & 세운 10년치 데이터 생성
    daewoon_flow = generate_daewoon_list(year_gan, month_ganji, is_forward, daewoon_num)
    current_year = datetime.now(KST).year  # 서버가 UTC로 돌아도 KST 기준 연도로 고정
    sewoon_flow = generate_sewoon_list(start_year=current_year, count=10)

    return {
        "status": "success",
        "birth_info": {
            "is_lunar": is_lunar,
            "converted_solar_date": solar_dt.strftime("%Y-%m-%d %H:%M"),
            "saju_year": saju_year,
            "year_ganji": year_ganji
        },
        "daewoon_info": {
            "daewoon_num": daewoon_num,
            "direction": direction_str,
            "flow": daewoon_flow
        },
        "sewoon_info": {
            "current_year": current_year,
            "list": sewoon_flow
        }
    }


# ===========================================================================
# 한자 간지 기반 운(woon) 헬퍼 — core/saju_base.calculate_saju() 에서 사용
# (위쪽 로직은 한글 간지, 아래는 사주 엔진 전체에서 쓰는 한자 간지 기준)
# ===========================================================================
GAN_H = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
JI_H = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
GAN_YANG_H = {
    "甲": True, "乙": False, "丙": True, "丁": False, "戊": True,
    "己": False, "庚": True, "辛": False, "壬": True, "癸": False,
}
# 월두법: 연간 -> 인월(寅月) 천간 index
_MONTH_HEAD_H = {"甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6, "丁": 8, "壬": 8, "戊": 0, "癸": 0}

_MALE_TOKENS = {"male", "m", "남", "남자", "남성"}


def _ganji_by_year(year: int) -> str:
    return GAN_H[(year - 4) % 10] + JI_H[(year - 4) % 12]


def daewoon_ganji_sequence(month_pillar: str, is_forward: bool, count: int = 8) -> List[str]:
    """월주(한자) + 순역방향만으로 결정되는 1~count 번째 대운 간지 순서.

    일주/생년월일과 무관 — 대운 간지 시퀀스 자체는 월주에서 순행/역행으로 한 칸씩
    옮겨가며 정해지고(월두법), 실제 개인마다 다른 건 "몇 살부터 1번째가 시작하는가"
    (대운수)뿐이다. 그래서 (월주, 순역방향)만 있으면 1~8번째 대운 간지를 전부 낼 수 있다.
    """
    m_gan = GAN_H.index(month_pillar[0]) if month_pillar and month_pillar[0] in GAN_H else 0
    m_ji = JI_H.index(month_pillar[1]) if len(month_pillar) > 1 and month_pillar[1] in JI_H else 2
    step = 1 if is_forward else -1
    gi, ji = m_gan, m_ji
    out = []
    for _ in range(count):
        gi = (gi + step) % 10
        ji = (ji + step) % 12
        out.append(GAN_H[gi] + JI_H[ji])
    return out


# 지지 2자 관계 판정(일지 vs 대운/세운/일진 지지 등 범용) — daily 프롬프트가 쓰던 것과 동일 로직을
# core 로 승격해 단일 소스로 관리(scripts/generate_content_db.py 는 이걸 그대로 가져다 쓴다).
def branch_relation(branch_a: str, branch_b: str) -> str:
    from core.constants import YUKHAP, CHUNG, PA, HAE, SANGHYEONG, SELF_HYEONG

    if not branch_a or not branch_b:
        return "무관"
    pair = frozenset((branch_a, branch_b))
    if branch_a == branch_b:
        return "복음(같은 지지)" + (" · 자형" if branch_a in SELF_HYEONG else "")
    for table, label in ((YUKHAP, "육합(협력·인연)"), (CHUNG, "충(충돌·이동)"),
                         (PA, "파(어긋남)"), (HAE, "해(방해·구설)"), (SANGHYEONG, "형(마찰·조정)")):
        if pair in table:
            return label
    return "무관"


def daewoon_step_facts(
    day_master: str, day_branch: str, month_pillar: str, is_forward: bool, count: int = 8,
) -> List[Dict[str, Any]]:
    """1~count 번째 대운 각각의 간지·십신·십신군·(일지 대비) 충형관계를 계산한다.

    Python 이 계산하는 '사실' — AI 프롬프트/정적 DB 콤보 키 생성 양쪽에서 쓴다.
    """
    from core.sipsin import calculate_sipsin, sipsin_group

    out = []
    for i, ganji in enumerate(daewoon_ganji_sequence(month_pillar, is_forward, count), start=1):
        gan, ji = ganji[0], ganji[1] if len(ganji) > 1 else ""
        sipsin = calculate_sipsin(day_master, gan, is_gan=True)
        out.append({
            "step": i,
            "ganji": ganji,
            "sipsin": sipsin,
            "sipsin_group": sipsin_group(sipsin),
            "branch_relation": branch_relation(day_branch, ji),
        })
    return out


def calculate_daewoon_info(
    year: int, month: int, day: int, gender: str,
    year_pillar: str, month_pillar: str = "甲寅",
) -> Dict[str, Any]:
    """생년월일 + 연주/월주(한자)로 대운수·순역·10년 단위 대운 흐름을 산출한다."""
    birth_dt = datetime(year, month, day, 12)
    year_stem = year_pillar[0] if year_pillar else "甲"
    is_yang = GAN_YANG_H.get(year_stem, True)
    is_male = gender.strip().lower() in _MALE_TOKENS

    # 양남음녀 순행 / 음남양녀 역행
    is_forward = (is_male and is_yang) or (not is_male and not is_yang)
    daewoon_num = calculate_exact_daewoon_num(birth_dt, is_forward)

    flow = []
    for i, ganji in enumerate(daewoon_ganji_sequence(month_pillar, is_forward, 8), start=1):
        start_age = daewoon_num + (i - 1) * 10
        flow.append({
            "step": i,
            "start_age": start_age,
            "ganji": ganji,
            "label": f"{start_age}세 대운 ({ganji})",
        })

    return {
        "daewoon_num": daewoon_num,
        "direction": "순행" if is_forward else "역행",
        "flow": flow,
    }


def get_seewoon_list(start_year: int, count: int = 10) -> List[Dict[str, Any]]:
    """start_year 부터 count 년치 세운(연운) 간지 목록(한자)."""
    return [
        {
            "year": start_year + i,
            "ganji": _ganji_by_year(start_year + i),
            "label": f"{start_year + i}년 ({_ganji_by_year(start_year + i)})",
        }
        for i in range(count)
    ]


def get_wolwoon_list(year: int) -> List[Dict[str, Any]]:
    """해당 연도 12개월 월운 간지 목록(한자). 절기 기준 인월(寅月)=1로 본다."""
    year_stem = GAN_H[(year - 4) % 10]
    start_gan = _MONTH_HEAD_H[year_stem]
    out = []
    for m in range(12):
        gi = (start_gan + m) % 10
        ji = (2 + m) % 12  # 寅(2) 부터 시작
        ganji = GAN_H[gi] + JI_H[ji]
        out.append({
            "month_index": m + 1,           # 인월=1 ... 축월=12
            "solar_month_approx": ((m + 1) % 12) + 1,  # 인월≈2월
            "ganji": ganji,
            "label": f"{ganji}월",
        })
    return out