from typing import Dict, List, Any

# 천간 합/충 관계 정의
CHEONGAN_HAAP = {
    ("갑", "기"): "갑기합토(甲己合土)", ("기", "갑"): "갑기합토(甲己合土)",
    ("을", "경"): "을경합금(乙庚合金)", ("경", "을"): "을경합금(乙庚合金)",
    ("병", "신"): "병신합수(丙辛合水)", ("신", "병"): "병신합수(丙辛合水)",
    ("정", "임"): "정임합목(丁壬合木)", ("임", "정"): "정임합목(丁壬合木)",
    ("무", "계"): "무계합화(戊癸合火)", ("계", "무"): "무계합화(戊癸合火)"
}

CHEONGAN_CHUNG = {
    ("갑", "경"): "갑경충(甲庚沖)", ("경", "갑"): "갑경충(甲庚沖)",
    ("을", "신"): "을신충(乙辛沖)", ("신", "을"): "을신충(乙辛沖)",
    ("병", "임"): "병임충(丙壬沖)", ("임", "병"): "병임충(丙壬沖)",
    ("정", "계"): "정계충(丁癸沖)", ("계", "정"): "정계충(丁癸沖)"
}

# 지지 육합 / 지지 충 정의
JIJI_YUKHAP = {
    ("자", "축"): "자축합토(子丑合土)", ("축", "자"): "자축합토(子丑合土)",
    ("인", "해"): "인해합목(寅亥合木)", ("해", "인"): "인해합목(寅亥合木)",
    ("묘", "술"): "묘술합화(卯戌合火)", ("술", "묘"): "묘술합화(卯戌合火)",
    ("진", "유"): "진유합금(辰酉合金)", ("유", "진"): "진유합금(辰酉合金)",
    ("사", "신"): "사신합수(巳申合水)", ("신", "사"): "사신합수(巳申合水)",
    ("오", "미"): "오미합화(午未合火)", ("미", "오"): "오미합화(午未合火)"
}

JIJI_CHUNG = {
    ("자", "오"): "자오충(子午沖)", ("오", "자"): "자오충(子午沖)",
    ("축", "미"): "축미충(丑未沖)", ("미", "축"): "축미충(丑未沖)",
    ("인", "신"): "인신충(寅申沖)", ("신", "인"): "인신충(寅申沖)",
    ("묘", "유"): "묘유충(卯酉沖)", ("유", "묘"): "묘유충(卯酉沖)",
    ("진", "술"): "진술충(辰戌沖)", ("술", "진"): "진술충(辰戌沖)",
    ("사", "해"): "사해충(巳亥沖)", ("해", "사"): "사해충(巳亥沖)"
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