"""평생운세 (LIFELONG_FORTUNE, 250P).

daily/yearly 와 마찬가지로 런타임 Gemini 호출 없이 사전 생성된 정적 DB에서 즉시
조회한다(DB 생성은 scripts/generate_content_db.py --domain lifelong_base /
lifelong_domains / lifelong_stage 참고).

'나이 구간(달력 기준)'을 축으로 삼으면 사람마다 다른 대운수(대운이 시작되는 나이,
1~10세 사이에서 개인마다 다름) 때문에 실제 대운 경계와 안 맞는 문제가 있어, 대신
'대운 순번(1~8번째)'을 축으로 쓴다 — 순번은 대운수와 무관하게 항상 잘 정의된다.
1900~2020년 전수조사로 (일주,월주,순역방향) 조합이 이론상 최대(7,200)와 정확히
일치함을 실측 검증했다(사용자와 논의 후 확정).

세 개의 정적 테이블(domains/lifelong/content_db.py 참고):
1) base_db: life_theme(인생을 관통하는 반복 과제) — 일주(60)당 1건.
   personality(타고난 성향)는 domains/personality/data/personality_db.json 의
   character.base_nature 를 그대로 재사용(다시 만들지 않음 — layer 분리 검증 완료).
2) domains_db: 삶의 4대 영역(재물/직업/가족/사회) — (일주, 현재 대운의 지배
   십신군, 대운 순번) = 60×5×8 = 2,400건. 재물↔재성/직업↔관성/가족↔인성/사회↔비겁
   고정 앵커로 서로 겹치지 않게 한다.
3) stage_db: 시기별 전환점(1~8번째 대운 전부) — (일주, 지배 십신군, 충형관계,
   순번) = 14,000건(수학적 전체 곱이 아니라 실제 달력에서 나오는 조합만 — daily 의
   "일주×일진" 과 같은 성격의 단순화).

core/daewoon.py 의 daewoon_step_facts() 가 실제 개인의 8단계 각각에 대한 '사실'
(간지·십신·십신군·충형관계)을 계산한다. API 응답은 8단계 전체를 반환하고, 그 사람의
실제 나이로 계산한 "지금 몇 번째 대운인지"만 current_step 플래그로 표시한다 —
평생운세의 핵심 가치는 "지금 이 순간"이 아니라 "인생 전체 흐름을 한눈에 보는 것"
이기 때문(daily 와의 차별화 지점, 사용자 확정).
"""
from typing import Dict, Any, List, Tuple, Optional

from core.saju_base import calculate_saju
from core.daewoon import daewoon_step_facts
from domains.lifelong.content_db import lookup_base, lookup_domains, lookup_stage, lookup_stage_detail
from domains.lifelong.landscape import build_landscape
from domains.personality.content_db import lookup as lookup_personality
from shared.public import person_summary

CONTENT_TYPE = "lifelong_fortune"

# (키, 시작나이, 끝나이(포함), 고정 라벨) — AI 가 만들지 않고 Python 이 그대로 박아 넣는다.
_LIFE_STAGES: List[Tuple[str, int, int, str]] = [
    ("stage_1_19", 0, 19, "1~19세 학업/가정/교우"),
    ("stage_20_29", 20, 29, "20~29세 독립/방향설정"),
    ("stage_30_49", 30, 49, "30~49세 커리어/재물/배우자"),
    ("stage_50_69", 50, 69, "50~69세 축적/재정비"),
    ("stage_70_plus", 70, 130, "70세+ 역할전환/정리"),
]

DOMINANT_GROUPS: List[str] = ["비겁", "식상", "재성", "관성", "인성"]

# section3(4대 영역) 고정 앵커 십신 — 전통 명리 궁위 기준. 서로 다른 근거에서 출발해
# 내용이 겹치지 않게 하는 핵심 장치(사용자 확인·승인됨).
DOMAIN_ANCHOR: Dict[str, str] = {
    "wealth": "재성",
    "career": "관성",
    "family": "인성",
    "social": "비겁",
}
DOMAIN_FIELDS: Dict[str, Tuple[str, str]] = {
    "wealth": ("style", "management_tip"),
    "career": ("best_fit_work", "success_environment"),
    "family": ("relation_characteristics", "harmony_key"),
    "social": ("connection_style", "network_strategy"),
}

# 대운 순번(1~8) → 참고 인생국면 라벨(Python 고정, AI 관여 없음). 사용자 확인·승인됨.
STAGE_LABELS: Dict[int, str] = {
    1: "학업과 가정·교우관계",
    2: "독립과 방향 설정",
    3: "인생의 기회와 확장",
    4: "인생의 기회와 확장",
    5: "축적과 재정비",
    6: "축적과 재정비",
    7: "역할 전환과 정리",
    8: "역할 전환과 정리",
}
# 순번 → SIPSIN_STAGE_HINTS 의 기존 연령대 키로 매핑(힌트 문구 재사용, 새로 안 만듦).
_STEP_TO_HINT_KEY: Dict[int, str] = {
    1: "stage_1_19", 2: "stage_20_29", 3: "stage_30_49", 4: "stage_30_49",
    5: "stage_50_69", 6: "stage_50_69", 7: "stage_70_plus", 8: "stage_70_plus",
}

# 십신군 × 생애단계 — 배치 생성 프롬프트를 구체화시키는 참고 사건결(그대로 베끼지 말고
# 자연스럽게 풀어 쓰게 유도하는 용도). scripts/generate_content_db.py 가 그대로 재사용한다.
SIPSIN_STAGE_HINTS: Dict[str, Dict[str, str]] = {
    "인성": {
        "stage_1_19": "부모의 보호와 학업적 조력, 스승 복이 따르는 시기",
        "stage_20_29": "전공·자격 심화, 윗사람의 인정과 추천을 받는 시기",
        "stage_30_49": "전문성 축적으로 신뢰를 얻는 시기",
        "stage_50_69": "지식과 경험을 나누는 멘토 역할이 커지는 시기",
        "stage_70_plus": "정신적으로 안정되고 존경받는 원로가 되는 시기",
    },
    "비겁": {
        "stage_1_19": "또래 관계 속에서 자기주장과 경쟁심이 커지는 시기",
        "stage_20_29": "독립을 시도하고 동료와 협업·경쟁하는 시기",
        "stage_30_49": "동업·파트너십이 확대되고 형제·동료 관계가 부각되는 시기",
        "stage_50_69": "인적 네트워크가 재편되며 협력의 결실을 보는 시기",
        "stage_70_plus": "오랜 인연·동년배와의 교류가 활발해지는 시기",
    },
    "식상": {
        "stage_1_19": "재능이 발현되고 자유로운 표현 욕구가 강한 시기",
        "stage_20_29": "사회에 진출해 실무 능력으로 성과를 내는 시기",
        "stage_30_49": "사업·창작 활동이 확장되며 활동 반경이 넓어지는 시기",
        "stage_50_69": "그동안의 성과가 드러나며 결실을 맺는 시기",
        "stage_70_plus": "취미·창작 활동으로 활력을 유지하는 시기",
    },
    "재성": {
        "stage_1_19": "현실 감각이 일찍 트이고 돈에 대한 개념이 자리잡는 시기",
        "stage_20_29": "첫 경제활동을 시작하며 재물 감각이 형성되는 시기",
        "stage_30_49": "자산 형성의 적기로 재물운이 오르는 시기",
        "stage_50_69": "자산을 관리·정리하며 현금흐름을 안정시키는 시기",
        "stage_70_plus": "자산을 정리·승계하며 노후자금을 관리하는 시기",
    },
    "관성": {
        "stage_1_19": "규율과 훈육 속에서 책임감이 형성되는 시기",
        "stage_20_29": "조직에 적응하며 취업·승진의 압박과 기회가 함께 오는 시기",
        "stage_30_49": "중책을 맡아 사회적 책임이 커지는 시기",
        "stage_50_69": "리더십을 발휘하며 명예·지위가 정점에 이르는 시기",
        "stage_70_plus": "역할에서 물러나 존경받는 자리로 전환되는 시기",
    },
}


def hint_for_step(dominant_group: str, step: int) -> str:
    """대운 순번(1~8) + 지배 십신군 → 참고 사건결 문구. _STEP_TO_HINT_KEY 로 기존
    SIPSIN_STAGE_HINTS(연령대 키) 를 재사용한다."""
    hint_key = _STEP_TO_HINT_KEY.get(step, "stage_1_19")
    return SIPSIN_STAGE_HINTS.get(dominant_group, {}).get(hint_key, "")


def _ilju(saju: Dict[str, Any]) -> str:
    return saju.get("day_ganji") or f"{saju.get('day_master', '')}{saju.get('day_branch', '')}"


def _current_step(daewoon_num: int, age: int) -> int:
    """그 사람의 실제 나이가 몇 번째 대운에 해당하는지. 아직 첫 대운 전(어린 나이)이면
    가장 가까운 다가올 시기인 1번째를 보여준다."""
    if age < daewoon_num:
        return 1
    step = (age - daewoon_num) // 10 + 1
    return max(1, min(8, step))


def _fallback_stage_entry(dominant_group: str, step: int) -> dict:
    return {
        "theme_line": STAGE_LABELS.get(step, "인생의 한 시기"),
        "keyword": "차분한 흐름",
    }


def _fallback_stage_detail(dominant_group: str, step: int) -> dict:
    hint = hint_for_step(dominant_group, step) or "차분히 흐름을 따라가는 시기"
    return {
        "event_narrative": f"{hint}입니다. 주어진 흐름에 맞춰 무리하지 않는 태도가 도움이 됩니다.",
        "strategy": "지금 맡은 일에 충실하면서, 무리한 확장보다 기본기를 다지는 선택이 유리합니다.",
        "obstacle": "조급한 마음에 성급히 결정을 내리면 오히려 되돌리는 데 시간이 더 걸릴 수 있습니다.",
        "turning_point": (
            "이전 국면 없이 시작되는 인생의 첫 전환점입니다." if step == 1
            else "직전 시기와는 결이 다른 변화가 찾아오는 구간이며, 다음 시기로 넘어가며 지금의 "
                 "흐름이 이어지거나 자연스럽게 전환될 수 있습니다."
        ),
    }


_FALLBACK_LIFE_THEME = "꾸준함으로 신뢰를 쌓아가는 인생"
_FALLBACK_PERSONALITY = "안정적인 흐름 속에서 자기 페이스를 지키는 성향입니다."
_FALLBACK_DOMAINS = {
    "wealth": {"style": "무리하지 않는 안정 지향형", "management_tip": "고정지출을 먼저 점검하세요."},
    "career": {"best_fit_work": "꾸준함이 필요한 전문 분야", "success_environment": "신뢰를 기반으로 한 조직"},
    "family": {"relation_characteristics": "가족과의 유대를 중요하게 여기는 편", "harmony_key": "정기적인 대화 시간"},
    "social": {"connection_style": "소수와 깊게 사귀는 편", "network_strategy": "기존 인연을 꾸준히 관리하기"},
}


def analyze_lifelong_fortune(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환. 정적 DB 조회만 — Gemini 호출 없음.

    평생운세는 "지금 이 순간"이 아니라 "인생 전체 흐름"이 핵심이므로 1~8번째 대운을
    전부 반환하고, 그 사람의 실제 나이로 계산한 current_step 만 별도 표시한다.
    """
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)
    ilju = _ilju(saju)
    day_master = saju.get("day_master", "")
    day_branch = saju.get("day_branch", "")
    month_ganji = saju.get("month_ganji", "")
    daewoon = saju.get("daewoon") or {}
    daewoon_num = daewoon.get("daewoon_num", 1)
    is_forward = daewoon.get("direction") == "순행"
    age = saju.get("age", 0) or 0

    facts = daewoon_step_facts(day_master, day_branch, month_ganji, is_forward, count=8)
    current_step = _current_step(daewoon_num, age)

    is_fallback = False

    # section1: life_theme(신규) + personality(personality_db 재사용)
    base = lookup_base(ilju)
    life_theme = (base or {}).get("life_theme") or _FALLBACK_LIFE_THEME
    if base is None:
        is_fallback = True
    character = lookup_personality(ilju, "character")
    personality = (character or {}).get("base_nature") or _FALLBACK_PERSONALITY
    if character is None:
        is_fallback = True

    # section2: 1~8번째 대운 전체
    life_stages = []
    for f in facts:
        step = f["step"]
        start_age = daewoon_num + (step - 1) * 10
        entry = lookup_stage(ilju, f["sipsin_group"], f["branch_relation"], step)
        if entry is None:
            is_fallback = True
            entry = _fallback_stage_entry(f["sipsin_group"], step)
        life_stages.append({
            "step": step,
            "stage_label": STAGE_LABELS.get(step, ""),
            "age_range": [start_age, start_age + 9],
            "is_current": step == current_step,
            "theme_line": entry.get("theme_line", ""),
            "keyword": entry.get("keyword", ""),
        })

    # section3: 삶의 4대 영역(현재 대운 기준)
    current_fact = next((f for f in facts if f["step"] == current_step), facts[0])
    domains_entry = lookup_domains(ilju, current_fact["sipsin_group"], current_step)
    if domains_entry is None:
        is_fallback = True
    life_domains = domains_entry or _FALLBACK_DOMAINS

    data = {
        # 섹션1: 사주적 풍경(AI/DB 없음 — day_master_elem·elem_power·yongsin 실시간 조합)
        "landscape": build_landscape(saju),
        "core_nature": {"personality": personality, "life_theme": life_theme},
        "life_domains": life_domains,
        "life_stages": life_stages,
        "current_step": current_step,
    }

    return {
        "content_type": CONTENT_TYPE,
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, is_fallback


CONTENT_TYPE_STAGE_DETAIL = "lifelong_stage_detail"


def analyze_lifelong_stage_detail(
    year: int, month: int, day: int, step: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
) -> Tuple[dict, bool]:
    """특정 대운(1~8번째)의 '상세 리포트'(전략/방해요소/전환점 등). 메인 평생운세 응답에는
    포함되지 않고, 유저가 해당 시기를 클릭했을 때만 별도로 조회한다."""
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)
    ilju = _ilju(saju)
    day_master = saju.get("day_master", "")
    day_branch = saju.get("day_branch", "")
    month_ganji = saju.get("month_ganji", "")
    daewoon = saju.get("daewoon") or {}
    is_forward = daewoon.get("direction") == "순행"

    step = max(1, min(8, int(step)))
    facts = daewoon_step_facts(day_master, day_branch, month_ganji, is_forward, count=8)
    fact = next((f for f in facts if f["step"] == step), facts[0])

    entry = lookup_stage_detail(ilju, fact["sipsin_group"], fact["branch_relation"], step)
    is_fallback = entry is None
    detail = entry or _fallback_stage_detail(fact["sipsin_group"], step)

    return {
        "content_type": CONTENT_TYPE_STAGE_DETAIL,
        "step": step,
        "stage_label": STAGE_LABELS.get(step, ""),
        "saju_info": person_summary(saju),
        "data": {
            "event_narrative": detail.get("event_narrative", ""),
            "strategy": detail.get("strategy", ""),
            "obstacle": detail.get("obstacle", ""),
            "turning_point": detail.get("turning_point", ""),
        },
    }, is_fallback
