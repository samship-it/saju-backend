"""평생운세 섹션1 — '사주적 풍경' 카드.

AI 호출도, 정적 DB도 없다. day_master_elem(일간, "나 자신")·elem_power(오행 파워
분포, "나를 둘러싼 배경")·yongsin(용신, "필요한 기운")은 core/saju_base.py가 이미
매 요청마다 실시간으로 계산해 두는 값이라, 오행 5개 × 역할별 고정 문구 블록만
미리 써 두고 그 값으로 조합한다(daily HEADLINE_TABLE과 동일한 패턴). 일주(60갑자)
단위 DB가 아니다 — day_master_elem·elem_power·yongsin은 4주(년/월/일/시) 전체로
정해지는 값이라 일주만으로는 결정되지 않기 때문이다.

reason(풍경 근거)은 월지의 계절(조후) + 시지를 그대로 서술하는 결정론적 조합이다
(12지지→4계절 매핑은 명리학에서 이견 없는 고정 사실이라 별도 검증 불필요). 정교한
조후용신 이론(한난조습 세부 판단)까지는 안 들어가고 "계절 기운을 받았다" 수준으로
단순화했다 — core/saju_base.py의 억부법 단순화와 같은 층위의 근사치다.
"""
from typing import Any, Dict, List, Optional

from core.constants import JI_ELEM

# 주체(SUBJECT) — 일간(day_master_elem, "나 자신") 오행이 상징하는 형상.
SUBJECT_IMAGE: Dict[str, str] = {
    "목": "곧게 뻗은 푸른 소나무",
    "화": "환하게 타오르는 붉은 불꽃",
    "토": "말없이 자리를 지키는 넓은 산",
    "금": "서늘하게 빛나는 칼날",
    "수": "깊고 고요히 흐르는 강물",
}

# 배경(ENV) — elem_power(오행별 실제 파워)에서 가장 강한 오행이 상징하는 풍경.
ENV_IMAGE: Dict[str, str] = {
    "목": "울창하게 우거진 숲",
    "화": "한여름 정오의 뜨거운 태양",
    "토": "끝없이 펼쳐진 대지",
    "금": "서늘하게 부는 가을바람",
    "수": "깊고 어두운 밤바다",
}

# 개운법(TIP) — strength.yongsin(용신, 부족해서 필요한 오행) 1순위가 상징하는 조언.
# 섹션2(core_nature)에서 [강점/성향 -> 단점/주의점 -> 개운법] 흐름의 마지막 요소로
# 쓰인다(build_tip() 참고, service.py 가 core_nature 에 붙여 반환). 평생운세 전용 —
# daily의 "오늘 하루 행동 팁"과 달리, 삶의 관조적 태도·장기적 환경 조성·심상 관리
# 위주로 쓴다(단발성 행동 지시 금지, 구체적 daily 행동 예시 금지).
TIP: Dict[str, str] = {
    "목": (
        "🌱 평생에 걸쳐 배움과 성장을 놓지 않는 태도가 이 사람을 지탱하는 힘이 됩니다. "
        "일상 속에 초록빛 식물이나 나무가 우거진 공간을 가까이 두면, 정체된 순간마다 "
        "다시 뻗어나갈 방향을 찾는 데 도움이 됩니다."
    ),
    "화": (
        "🔥 마음을 안으로만 가두지 않고 표현하며 살아가는 태도가 중요합니다. "
        "따뜻하고 밝은 사람들, 그리고 볕이 잘 드는 환경을 곁에 오래 두면 삶 전반의 "
        "활력이 꾸준히 유지됩니다."
    ),
    "토": (
        "⛰️ 흔들릴 때마다 무리하게 방향을 틀기보다, 변하지 않는 원칙과 루틴을 삶의 "
        "중심에 두는 태도가 필요합니다. 안정적인 거처와 관계를 오래 지키는 것이 "
        "장기적으로 가장 큰 자산이 됩니다."
    ),
    "금": (
        "⚔️ 맺고 끊음이 분명한 삶의 태도가 이 사람에게는 특히 중요합니다. 불필요한 "
        "관계와 미련을 정리하는 습관을 평생에 걸쳐 들이면, 중요한 순간마다 흔들리지 "
        "않는 결단력으로 이어집니다."
    ),
    "수": (
        "🌊 채우기보다 비워내는 여백의 시간을 삶 속에 꾸준히 마련하는 태도가 필요합니다. "
        "혼자 조용히 머무를 수 있는 공간과 시간을 오래도록 곁에 두면, 지혜와 통찰이 "
        "서서히 깊어집니다."
    ),
}

_DEFAULT_TIP = "지금의 균형을 오래도록 잘 유지해 나가는 것만으로도 충분합니다."

# 월지(月支) 12개 → 계절 이름. 명리학 고정 사실(이견 없음).
_SEASON_BRANCHES = {
    "봄": "寅卯辰", "여름": "巳午未", "가을": "申酉戌", "겨울": "亥子丑",
}
SEASON_OF_BRANCH: Dict[str, str] = {b: season for season, branches in _SEASON_BRANCHES.items() for b in branches}

# 계절별 조후(氣) 서술 — 한난조습을 단순화한 수식어.
SEASON_DESC: Dict[str, str] = {
    "봄": "따뜻하게 생동하는 봄",
    "여름": "뜨겁고 메마른 여름",
    "가을": "서늘하고 청명한 가을",
    "겨울": "차갑게 응축된 겨울",
}

_BRANCH_KO = {
    "子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사",
    "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해",
}


def build_reason(saju: Dict[str, Any], env_elem: str, yongsin: List[str]) -> Optional[str]:
    """풍경이 왜 이렇게 나왔는지(월지 조후 + 시지 영향 + 최강 오행 + 용신)를 2~3문장으로.

    일간·월지·시지는 calculate_saju()가 이미 계산해 둔 실제 값을 그대로 서술만 한다
    (새 명리 계산 없음). 시지는 birth_time_known=False(출생시간 미상)면 생략한다.
    """
    day_master = saju.get("day_master") or ""
    day_elem = saju.get("day_master_elem") or ""
    month_ganji = saju.get("month_ganji") or ""
    time_ganji = saju.get("time_ganji") or ""
    birth_time_known = saju.get("birth_time_known", True)

    if not day_master or not day_elem or len(month_ganji) < 2:
        return None

    month_branch = month_ganji[1]
    season = SEASON_OF_BRANCH.get(month_branch)
    if not season:
        return None
    season_desc = SEASON_DESC[season]

    sentences = [f"일간 {day_master}({day_elem})는 {season_desc}인 {month_branch}월에 태어나 그 계절의 기운을 강하게 받았습니다."]

    if birth_time_known and len(time_ganji) >= 2:
        hour_branch = time_ganji[1]
        hour_elem = JI_ELEM.get(hour_branch, "")
        if hour_elem:
            sentences.append(
                f"{_BRANCH_KO.get(hour_branch, hour_branch)}시(時)생으로 {hour_elem} 기운까지 더해지며 "
                "원국의 흐름이 한층 뚜렷해졌습니다."
            )

    if env_elem:
        if yongsin:
            sentences.append(
                f"그 결과 원국 전체에서 {env_elem} 기운이 가장 강하게 자리잡아, "
                f"이를 다스릴 {'·'.join(yongsin)} 기운이 중요한 열쇠가 됩니다."
            )
        else:
            sentences.append(f"그 결과 원국 전체에서 {env_elem} 기운이 가장 강하게 자리잡았습니다.")

    return " ".join(sentences)


def build_landscape(saju: Dict[str, Any]) -> Dict[str, Any]:
    """saju_data(calculate_saju 산출물) -> {scene, reason, day_master_elem, env_elem, yongsin}.

    개운법(tip)은 섹션2(core_nature) 몫이라 여기 포함하지 않는다 — build_tip() 참고.
    """
    day_elem = saju.get("day_master_elem") or ""
    strength = saju.get("strength") or {}
    elem_power: Dict[str, float] = strength.get("elem_power") or {}
    env_elem = max(elem_power, key=elem_power.get) if elem_power else day_elem
    yongsin: List[str] = strength.get("yongsin") or []

    subject = SUBJECT_IMAGE.get(day_elem, "고요히 서 있는 존재")
    env = ENV_IMAGE.get(env_elem, "잔잔한 풍경")

    return {
        "scene": f"{env} 아래 {subject}",
        "reason": build_reason(saju, env_elem, yongsin),
        "day_master_elem": day_elem or None,
        "env_elem": env_elem or None,
        "yongsin": yongsin,
    }


def build_tip(saju: Dict[str, Any]) -> str:
    """saju_data -> 개운법 한 문단(섹션2 core_nature 의 마지막 요소).

    strength.yongsin(용신, 부족해서 필요한 오행) 1순위가 상징하는 조언을 고른다.
    """
    strength = saju.get("strength") or {}
    yongsin: List[str] = strength.get("yongsin") or []
    tip_elem = yongsin[0] if yongsin else None
    return TIP.get(tip_elem, _DEFAULT_TIP) if tip_elem else _DEFAULT_TIP
