"""공통 사주 판세 엔진 (Saju Pattern Engine).

'타고난 기질'(원국 세력에서 가장 강한 십신군)과 '사주 내 환경 기운'(두 번째로 강한
십신군)을 융합해 1개의 [사주적 풍경 이미지 & 융합 캐릭터]를 정의한다.

이 모듈이 만드는 것은 어디까지나 "Python이 계산하는 구조화된 캐릭터 뼈대"다.
persona_map.py(일간/일지 말투)와 같은 층위 — AI에게 그대로 노출할 고정 그라운딩
텍스트이지, 최종 사용자 문장 자체가 아니다. 모든 도메인 프롬프트는 이 뼈대를
공통으로 참조해야 한다(단편적 1:1 매핑 — "관성=무조건 공무원/경찰" 같은 — 금지).

기질/환경 모두 core/domain_derived.py의 group_power(십신 그룹 세력)에서 가장 강한
두 그룹을 뽑아 정하며, 특정 관직·직업을 단정하지 않고 '작동 방식'을 말한다.
"""
from typing import Any, Dict

from core.sipsin import calculate_sipsin, sipsin_group

_GROUPS = ["비겁", "식상", "재성", "관성", "인성"]

# 기질(타고난 원동력) — 원국 세력에서 가장 강한 십신군이 결정.
TEMPERAMENT: Dict[str, Dict[str, str]] = {
    "비겁": {
        "label": "주체형",
        "desc": "남이 정해준 기준보다 스스로 납득한 기준으로 움직이는, 독립적 추진력이 강한 성향",
        "landscape": "홀로 우뚝 선 나무가 제 뿌리 힘만으로 버티고 자라는 풍경",
    },
    "식상": {
        "label": "모험가형",
        "desc": "머릿속 생각을 곧장 행동과 표현으로 옮기고, 새로운 시도 자체에서 동력을 얻는 성향",
        "landscape": "물줄기가 정해진 길 없이 스스로 새 물길을 내며 뻗어나가는 풍경",
    },
    "재성": {
        "label": "승부사형",
        "desc": "기회를 빠르게 알아보고 실리를 계산해 움직이는, 현실 감각이 발달한 성향",
        "landscape": "시장의 흐름을 읽어 가장 먼저 좋은 자리를 잡는 상인의 풍경",
    },
    "관성": {
        "label": "책임가형",
        "desc": "역할과 규범 안에서 맡은 몫을 흔들림 없이 해내는, 책임감과 지구력이 강한 성향",
        "landscape": "단단한 성벽처럼 정해진 자리를 끝까지 지켜내는 풍경",
    },
    "인성": {
        "label": "탐구가형",
        "desc": "깊이 이해하고 근거를 쌓은 뒤에야 움직이는, 학습과 내실을 중시하는 성향",
        "landscape": "고요한 서재에서 천천히 뿌리를 내리며 자라는 나무의 풍경",
    },
}

# 환경(사주 내 두 번째 기운) — 이 기질이 실제로 발휘되는 무대.
ENVIRONMENT: Dict[str, Dict[str, str]] = {
    "비겁": {"label": "동료·경쟁의 장", "texture": "사람들과 부대끼고 서로 자극을 주고받으며"},
    "식상": {"label": "자유표현의 장", "texture": "규칙보다 창의와 시도가 먼저 허용되는 분위기 속에서"},
    "재성": {"label": "기회와 자원의 장", "texture": "거래·확장·자원 배분이 활발히 오가는 무대 위에서"},
    "관성": {"label": "체계와 제도의 장", "texture": "명확한 규칙과 자격, 위계가 뚜렷한 틀 안에서"},
    "인성": {"label": "지식과 전문성의 장", "texture": "배움과 전문 영역이 존중받는 환경 속에서"},
}

# (기질, 환경) 융합 캐릭터 — 특정 직업/기관을 단정하지 않고 '작동 방식'으로 서술.
_FUSION_ROLE: Dict[str, Dict[str, str]] = {
    "식상": {
        "관성": "단단한 시스템·자격을 지렛대 삼는 독립적 개척자",
        "재성": "스타트업 및 신시장을 여는 창업가형 실행가",
        "인성": "자유로운 전문 연구·기획·개발자",
        "비겁": "동료와 함께 새 판을 짜는 현장형 리더",
        "식상": "표현과 창작 자체가 동력인 순수 크리에이터",
    },
    "비겁": {
        "관성": "조직 안에서 자기 원칙을 지키는 강단 있는 실무 리더",
        "재성": "직접 뛰며 실리를 챙기는 자수성가형 사업가",
        "인성": "묵묵히 실력을 쌓아 인정받는 전문 장인",
        "식상": "자기 색깔을 표현하며 판을 이끄는 주도형 크리에이터",
        "비겁": "누구보다 자기 기준이 뚜렷한 독립불패형",
    },
    "재성": {
        "관성": "명확한 규칙 안에서 승부를 보는 전략적 관리자",
        "식상": "아이디어를 곧장 수익으로 연결하는 기회포착형 사업가",
        "인성": "전문 지식을 자산으로 바꾸는 투자·자문형",
        "비겁": "동료·파트너와 함께 몸집을 키우는 현장 승부사",
        "재성": "기회를 보는 감각이 남다른 타고난 트레이더형",
    },
    "관성": {
        "재성": "조직의 자원을 다루는 신뢰받는 관리자",
        "식상": "규율 안에서도 아이디어를 실현하는 혁신적 실무자",
        "인성": "전문성과 원칙을 겸비한 신뢰받는 전문직",
        "비겁": "동료를 이끌며 책임을 다하는 현장 리더",
        "관성": "역할과 책임에 흔들림 없는 정통 관리자형",
    },
    "인성": {
        "관성": "전문성을 제도 안에서 인정받는 정통 전문가",
        "재성": "지식을 자산으로 연결하는 실용적 연구자",
        "식상": "배운 것을 창작으로 풀어내는 크리에이티브 연구자",
        "비겁": "자기만의 속도로 깊이를 파는 독립 연구자",
        "인성": "배움 그 자체가 목적인 순수 탐구자형",
    },
}

FUSION_GUIDANCE = (
    "이 융합 캐릭터는 이 사람의 '작동 방식'(무엇에서 동력을 얻고, 어떤 무대에서 그 동력이 "
    "발휘되는지)을 요약한 것이다. 모든 해석의 뼈대로 삼되, 이 문장을 그대로 반복하지 말고 "
    "자연스럽게 녹여 쓸 것. 특정 직업·기관을 '무조건 ~이다'식으로 단정하지 말 것 "
    "(예: 관성=무조건 공무원/경찰 같은 기계적 1:1 매핑 금지) — 여러 직업·환경에 두루 적용되는 "
    "'일하는 방식'으로 풀어서 말할 것."
)


def _weighted_top2(group_power: Dict[str, float]) -> tuple:
    ranked = sorted(_GROUPS, key=lambda g: (-group_power.get(g, 0.0), _GROUPS.index(g)))
    return ranked[0], ranked[1] if len(ranked) > 1 else ranked[0]


def ilju_temperament_group(day_master: str, day_branch: str) -> str:
    """전체 4주 없이 일주(일간·일지)만으로 정하는 '타고난 기질' 그룹.

    personality_db(60일주 전용, 시간 불필요)처럼 원국 전체를 쓸 수 없는 도메인용.
    일지가 일간에 대해 갖는 십신 그룹 — domains/lifelong 이 life_theme 근거로 이미
    쓰던 것과 동일한 축을 재사용해, 도메인 간 '기질'의 정의가 갈라지지 않게 한다.
    """
    if not day_master or not day_branch:
        return "비겁"
    return sipsin_group(calculate_sipsin(day_master, day_branch, is_gan=False))


def fusion_lookup(temperament_group: str, environment_group: str) -> Dict[str, str]:
    """(기질 그룹, 환경 그룹) → 라벨/융합 역할/풍경. 두 값이 같으면 강화형 조합."""
    temperament_group = temperament_group if temperament_group in TEMPERAMENT else "비겁"
    environment_group = environment_group if environment_group in ENVIRONMENT else temperament_group

    temperament = TEMPERAMENT[temperament_group]
    environment = ENVIRONMENT[environment_group]
    fusion_role = _FUSION_ROLE[temperament_group][environment_group]
    landscape_image = f"{temperament['landscape']} — {environment['texture']} 펼쳐지는 모습"

    return {
        "temperament_group": temperament_group,
        "temperament_label": temperament["label"],
        "temperament_desc": temperament["desc"],
        "environment_group": environment_group,
        "environment_label": environment["label"],
        "fusion_role": fusion_role,
        "landscape_image": landscape_image,
        "guidance": FUSION_GUIDANCE,
    }


def analyze_fusion_character(saju: Dict[str, Any]) -> Dict[str, Any]:
    """saju: calculate_saju() 산출물(derived.group_power 포함, 전체 4주 필요).

    반환: 기질/환경 그룹과 라벨, 융합 역할, 풍경 이미지, AI 프롬프트용 가이드 문구.
    """
    group_power = (saju.get("derived") or {}).get("group_power") or {}
    temperament_group, environment_group = _weighted_top2(group_power)
    return fusion_lookup(temperament_group, environment_group)


def fusion_prompt_block(temperament_group: str, environment_group: str, *, title: str = "공통 사주 판세") -> str:
    """Gemini 프롬프트에 그대로 삽입할 그라운딩 블록. persona_prompt()와 같은 층위."""
    f = fusion_lookup(temperament_group, environment_group)
    return "\n".join([
        f"[{title} — 이 사람의 융합 캐릭터. 모든 해석의 뼈대로 삼을 것]",
        f"- 타고난 기질: {f['temperament_label']} ({f['temperament_desc']})",
        f"- 사주 내 환경 기운: {f['environment_label']}",
        f"- 융합 캐릭터: {f['fusion_role']}",
        f"- 사주적 풍경: {f['landscape_image']}",
        f"- {f['guidance']}",
    ])


def fusion_character_prompt(saju: Dict[str, Any]) -> str:
    """전체 4주가 있는 saju dict 기준 그라운딩 블록(런타임 도메인용)."""
    f = analyze_fusion_character(saju)
    return fusion_prompt_block(f["temperament_group"], f["environment_group"])
