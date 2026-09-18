"""평생운세 섹션1 — '사주적 풍경' 카드.

AI 호출도, 정적 DB도 없다. day_master_elem(일간, "나 자신")·elem_power(오행 파워
분포, "나를 둘러싼 배경")·yongsin(용신, "필요한 기운")은 core/saju_base.py가 이미
매 요청마다 실시간으로 계산해 두는 값이라, 오행 5개 × 3역할(주체/배경/개운팁) =
15개의 고정 문구 블록만 미리 써 두고 그 값으로 조합한다(daily HEADLINE_TABLE과
동일한 패턴). 일주(60갑자) 단위 DB가 아니다 — day_master_elem·elem_power·yongsin은
4주(년/월/일/시) 전체로 정해지는 값이라 일주만으로는 결정되지 않기 때문이다.
"""
from typing import Any, Dict, List, Optional

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

# 개운 팁(TIP) — strength.yongsin(용신, 부족해서 필요한 오행) 1순위가 상징하는 조언.
TIP: Dict[str, str] = {
    "목": "🌱 새로운 걸 배우거나 계획을 세워보는 게 좋은 기운이 돼요. 화분 하나 들이거나 초록빛이 많은 곳을 거니는 것도 도움이 됩니다.",
    "화": "🔥 마음을 터놓고 표현하는 시간이 필요해요. 좋아하는 사람들과 어울리며 밝은 에너지를 채워보세요.",
    "토": "⛰️ 규칙적인 생활과 안정된 루틴이 큰 힘이 돼요. 조급해하지 말고 한 걸음씩 차근차근 다져가 보세요.",
    "금": "⚔️ 흐지부지 미뤄둔 결정을 정리할 때예요. 책상 정리처럼 작은 정돈부터 시작해 보세요.",
    "수": "🌊 혼자 고민하기보다 마음을 트고 쉴 수 있는 시간과 공간을 자주 확보해 주세요. 물가를 걷거나 잠깐 멍하니 쉬는 것도 좋아요.",
}

_DEFAULT_TIP = "지금의 균형을 잘 유지하는 것만으로도 충분해요."


def build_landscape(saju: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """saju_data(calculate_saju 산출물) -> {scene, tip, day_master_elem, env_elem, yongsin}."""
    day_elem = saju.get("day_master_elem") or ""
    strength = saju.get("strength") or {}
    elem_power: Dict[str, float] = strength.get("elem_power") or {}
    env_elem = max(elem_power, key=elem_power.get) if elem_power else day_elem
    yongsin: List[str] = strength.get("yongsin") or []
    tip_elem = yongsin[0] if yongsin else None

    subject = SUBJECT_IMAGE.get(day_elem, "고요히 서 있는 존재")
    env = ENV_IMAGE.get(env_elem, "잔잔한 풍경")

    return {
        "scene": f"{env} 아래 {subject}",
        "tip": TIP.get(tip_elem, _DEFAULT_TIP) if tip_elem else _DEFAULT_TIP,
        "day_master_elem": day_elem or None,
        "env_elem": env_elem or None,
        "yongsin": yongsin,
    }
