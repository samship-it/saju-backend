from typing import Dict, List, Any

# 천간 합/충 관계 정의 (사주 엔진 전역과 동일한 한자 간지 기준)
CHEONGAN_HAAP = {
    ("甲", "己"): "갑기합토(甲己合土)", ("己", "甲"): "갑기합토(甲己合土)",
    ("乙", "庚"): "을경합금(乙庚合金)", ("庚", "乙"): "을경합금(乙庚合金)",
    ("丙", "辛"): "병신합수(丙辛合水)", ("辛", "丙"): "병신합수(丙辛合水)",
    ("丁", "壬"): "정임합목(丁壬合木)", ("壬", "丁"): "정임합목(丁壬合木)",
    ("戊", "癸"): "무계합화(戊癸合火)", ("癸", "戊"): "무계합화(戊癸合火)"
}

CHEONGAN_CHUNG = {
    ("甲", "庚"): "갑경충(甲庚沖)", ("庚", "甲"): "갑경충(甲庚沖)",
    ("乙", "辛"): "을신충(乙辛沖)", ("辛", "乙"): "을신충(乙辛沖)",
    ("丙", "壬"): "병임충(丙壬沖)", ("壬", "丙"): "병임충(丙壬沖)",
    ("丁", "癸"): "정계충(丁癸沖)", ("癸", "丁"): "정계충(丁癸沖)"
}

# 지지 육합 / 지지 충 정의
JIJI_YUKHAP = {
    ("子", "丑"): "자축합토(子丑合土)", ("丑", "子"): "자축합토(子丑合土)",
    ("寅", "亥"): "인해합목(寅亥合木)", ("亥", "寅"): "인해합목(寅亥合木)",
    ("卯", "戌"): "묘술합화(卯戌合火)", ("戌", "卯"): "묘술합화(卯戌合火)",
    ("辰", "酉"): "진유합금(辰酉合金)", ("酉", "辰"): "진유합금(辰酉合金)",
    ("巳", "申"): "사신합수(巳申合水)", ("申", "巳"): "사신합수(巳申合水)",
    ("午", "未"): "오미합화(午未合火)", ("未", "午"): "오미합화(午未合火)"
}

JIJI_CHUNG = {
    ("子", "午"): "자오충(子午沖)", ("午", "子"): "자오충(子午沖)",
    ("丑", "未"): "축미충(丑未沖)", ("未", "丑"): "축미충(丑未沖)",
    ("寅", "申"): "인신충(寅申沖)", ("申", "寅"): "인신충(寅申沖)",
    ("卯", "酉"): "묘유충(卯酉沖)", ("酉", "卯"): "묘유충(卯酉沖)",
    ("辰", "戌"): "진술충(辰戌沖)", ("戌", "辰"): "진술충(辰戌沖)",
    ("巳", "亥"): "사해충(巳亥沖)", ("亥", "巳"): "사해충(巳亥沖)"
}

def calculate_compatibility_interactions(person1_saju: Dict[str, Any], person2_saju: Dict[str, Any]) -> Dict[str, Any]:
    """
    두 사람 사주 간의 일간 궁합, 천간합/충, 지지합/충 상호작용 계산
    """
    p1_day_master = person1_saju.get("day_master", "")
    p2_day_master = person2_saju.get("day_master", "")
    
    # 일간(Day Master) 간 상호작용
    day_master_relation = "중립"
    if (p1_day_master, p2_day_master) in CHEONGAN_HAAP:
        day_master_relation = f"일간 천간합: {CHEONGAN_HAAP[(p1_day_master, p2_day_master)]} (깊은 끌림)"
    elif (p1_day_master, p2_day_master) in CHEONGAN_CHUNG:
        day_master_relation = f"일간 천간충: {CHEONGAN_CHUNG[(p1_day_master, p2_day_master)]} (역동적 자극과 보완)"

    # 사주 각 자리에 대한 지지 합/충 계산 (일지 중심)
    p1_day_jiji = person1_saju.get("day_ganji", "")[-1] if person1_saju.get("day_ganji") else ""
    p2_day_jiji = person2_saju.get("day_ganji", "")[-1] if person2_saju.get("day_ganji") else ""

    jiji_relation = "보통"
    if (p1_day_jiji, p2_day_jiji) in JIJI_YUKHAP:
        jiji_relation = f"일지 육합: {JIJI_YUKHAP[(p1_day_jiji, p2_day_jiji)]} (속궁합 및 정서적 안정)"
    elif (p1_day_jiji, p2_day_jiji) in JIJI_CHUNG:
        jiji_relation = f"일지 충: {JIJI_CHUNG[(p1_day_jiji, p2_day_jiji)]} (가치관의 차이 및 변화)"

    return {
        "person1_day_master": p1_day_master,
        "person2_day_master": p2_day_master,
        "day_master_relation": day_master_relation,
        "day_jiji_relation": jiji_relation,
        "compatibility_score_base": 85 if "합" in day_master_relation or "합" in jiji_relation else 75
    }