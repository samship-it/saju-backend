"""10년 대운(daewoon) — 도메인 분석 고정 문구(십신군 5개 기준, AI 미관여).

AI 호출·새 정적 DB 없음. 이미 계산되는 지배 십신군(daewoon_step_facts)에 얹은 작은
고정 표에서 문장을 고른다 — domains/lifelong/highlight.py·life_periods.py와 같은
설계. 사주 전문 용어(재성/관성/식상/비겁/인성)는 사용자 문장에 노출하지 않는다.
"""
from typing import Dict, List, Optional

GROUPS: List[str] = ["비겁", "식상", "재성", "관성", "인성"]

# ── keywords(3개) ────────────────────────────────────────────────────────
KEYWORDS: Dict[str, List[str]] = {
    "비겁": ["동료", "자립", "경쟁"],
    "식상": ["표현", "창작", "확장"],
    "재성": ["실속", "성과", "관리"],
    "관성": ["책임", "성장", "인정"],
    "인성": ["배움", "신뢰", "내실"],
}

# ── decade_tasks(3개, Action Plan) ──────────────────────────────────────
DECADE_TASKS: Dict[str, List[str]] = {
    "비겁": [
        "혼자 다 하려 하지 말고 믿을 만한 동료·파트너를 만드는 것",
        "경쟁심을 동력으로 쓰되 관계를 해치지 않는 선을 지키는 것",
        "내 속도를 지키면서도 협업의 기회를 놓치지 않는 것",
    ],
    "식상": [
        "머릿속 아이디어를 실제 결과물로 완성해내는 것",
        "표현하고 싶은 것을 다듬어 꾸준히 세상에 내놓는 것",
        "새로운 시도를 벌이는 동시에 하나는 끝까지 마무리하는 것",
    ],
    "재성": [
        "눈앞의 이익보다 장기적인 자산 계획을 세우는 것",
        "실속을 챙기되 사람들과의 신뢰를 함께 지키는 것",
        "벌어들인 것을 지키는 관리 습관을 만드는 것",
    ],
    "관성": [
        "책임을 맡되 스스로를 지나치게 몰아붙이지 않는 것",
        "원칙을 지키면서도 주변과 유연하게 소통하는 것",
        "맡은 역할에서 신뢰를 쌓아 다음 기회로 연결하는 것",
    ],
    "인성": [
        "배운 것을 실제 행동과 결과로 옮기는 것",
        "혼자만의 생각에 머물지 않고 사람들과 나누는 것",
        "꾸준히 쌓은 내공을 필요한 순간에 자신 있게 쓰는 것",
    ],
}

# ── career_or_study: 성인기(>=25, core_change/how_it_shows/cautions) ──────
CAREER_ADULT: Dict[str, Dict[str, str]] = {
    "비겁": {
        "core_change": "조직 안에서든 독립적인 활동에서든 스스로 판을 주도하려는 흐름이 강해지는 시기입니다.",
        "how_it_shows": "동료나 파트너와 함께, 혹은 직접 나서서 일을 벌이는 방식으로 성과를 만들어갑니다.",
        "cautions": "혼자 다 짊어지려 하거나 주변과 경쟁하는 데 에너지를 너무 많이 쓰지 않도록 주의하세요.",
    },
    "식상": {
        "core_change": "아이디어와 실행력으로 존재감을 드러내는 흐름이 강해지는 시기입니다.",
        "how_it_shows": "기획하고 만들어내는 일, 표현하는 일에서 성과를 인정받으며 활동 반경이 넓어집니다.",
        "cautions": "한 번에 너무 많은 걸 벌이면 마무리가 흐트러질 수 있으니 완결에 신경 쓰세요.",
    },
    "재성": {
        "core_change": "실속을 챙기며 성과를 만들어가는 흐름이 강해지는 시기입니다.",
        "how_it_shows": "눈에 보이는 결과와 실적으로 입지를 다지고, 현실적인 판단력이 빛을 발합니다.",
        "cautions": "성과에만 몰두하다 관계나 건강을 소홀히 하지 않도록 균형을 챙기세요.",
    },
    "관성": {
        "core_change": "책임 있는 자리를 맡으며 입지가 뚜렷해지는 흐름이 강해지는 시기입니다.",
        "how_it_shows": "관리자나 리더 역할, 공적인 책임이 자연스럽게 늘어나며 신뢰를 쌓습니다.",
        "cautions": "책임에 짓눌려 스스로를 지나치게 몰아붙이지 않도록 페이스 조절이 필요합니다.",
    },
    "인성": {
        "core_change": "전문성과 신뢰를 바탕으로 입지를 다지는 흐름이 강해지는 시기입니다.",
        "how_it_shows": "화려하게 드러나기보다 실력으로 인정받으며, 배움을 통해 성장합니다.",
        "cautions": "생각과 준비에만 머물지 말고 실제 행동으로 옮기는 실행력을 함께 키우세요.",
    },
}

# ── career_or_study: 청소년기(<25, growth_flow/study_style/cautions) ──────
CAREER_YOUTH: Dict[str, Dict[str, str]] = {
    "비겁": {
        "growth_flow": "또래 관계 속에서 자립심과 경쟁심이 함께 자라나는 시기입니다.",
        "study_style": "친구들과 어울려 함께 공부하거나 경쟁하며 실력을 키우는 스타일이 잘 맞습니다.",
        "cautions": "지기 싫은 마음에 무리하게 비교하지 말고 내 속도를 지키는 연습이 필요합니다.",
    },
    "식상": {
        "growth_flow": "재능과 표현 욕구가 자유롭게 피어나는 시기입니다.",
        "study_style": "흥미를 느끼는 분야에 몰입하고, 발표하거나 만들어보는 활동에서 두각을 나타냅니다.",
        "cautions": "흥미 위주로만 움직이면 기초가 흔들릴 수 있으니 꾸준함도 함께 길러야 합니다.",
    },
    "재성": {
        "growth_flow": "현실 감각이 일찍 트이고 목표 지향적인 태도가 자라나는 시기입니다.",
        "study_style": "목표와 결과가 뚜렷할 때 집중력이 올라가며, 실용적인 학습을 선호합니다.",
        "cautions": "당장의 결과에만 치중하다 기초가 되는 폭넓은 공부를 놓치지 않도록 하세요.",
    },
    "관성": {
        "growth_flow": "책임감과 규율 속에서 성장하는 시기입니다.",
        "study_style": "계획을 세우고 꾸준히 실천하는 성실한 학습 스타일이 잘 맞습니다.",
        "cautions": "완벽하게 해내야 한다는 부담이 너무 커지지 않도록 스스로를 다독여 주세요.",
    },
    "인성": {
        "growth_flow": "배움과 정서적 안정 속에서 성장하는 시기입니다.",
        "study_style": "혼자 깊이 파고드는 학습 스타일을 선호하며, 이해와 사고력이 강점이 됩니다.",
        "cautions": "생각에만 머물지 말고 배운 것을 직접 활용해보는 경험을 늘려보세요.",
    },
}

# ── wealth_flow: earning_style/cash_flow/management_caution ───────────────
WEALTH_FLOW: Dict[str, Dict[str, str]] = {
    "비겁": {
        "earning_style": "동료·파트너와 함께, 혹은 스스로의 힘으로 벌어들이는 방식이 잘 맞는 시기입니다.",
        "cash_flow": "씀씀이도 자기 뜻대로 결정하는 편이라 수입과 지출의 변동이 있을 수 있습니다.",
        "management_caution": "계획 없이 크게 쓰지 않도록 정기적으로 지출을 점검하는 습관이 필요합니다.",
    },
    "식상": {
        "earning_style": "아이디어와 활동을 통해 수입을 만들어내는 흐름이 활발해지는 시기입니다.",
        "cash_flow": "수입이 늘어나는 만큼 씀씀이도 커질 수 있어 흐름의 변동폭이 큰 편입니다.",
        "management_caution": "충동적인 지출을 줄이고 일정 부분은 꼭 따로 떼어 모아두세요.",
    },
    "재성": {
        "earning_style": "재물을 불리는 감각이 가장 활발해지는 시기입니다.",
        "cash_flow": "수입원이 다양해지고 자산이 눈에 띄게 늘어날 가능성이 큽니다.",
        "management_caution": "욕심을 내다 무리한 투자로 이어지지 않도록 신중한 판단이 필요합니다.",
    },
    "관성": {
        "earning_style": "안정적인 소득과 지위를 바탕으로 자산을 쌓아가는 시기입니다.",
        "cash_flow": "큰 변동 없이 꾸준하고 예측 가능한 흐름을 유지하는 편입니다.",
        "management_caution": "안정에 안주하기보다 신용과 원칙을 지키며 관리하는 태도가 필요합니다.",
    },
    "인성": {
        "earning_style": "지식이나 전문성을 통해 수입을 만들어가는 시기입니다.",
        "cash_flow": "당장의 수익보다 장기적인 가치를 우선시하는 흐름을 보입니다.",
        "management_caution": "배움에 투자하는 것도 좋지만 실질적인 수익 계획도 함께 세워두세요.",
    },
}

# ── relationship: flow(단정 안 함) + 현재 대운 한정 상태별 가이드 ──────────
RELATIONSHIP_FLOW: Dict[str, str] = {
    "비겁": "인연이 또래·동료 관계 속에서 자연스럽게 이어지거나, 스스로 관계를 주도하는 흐름을 보일 수 있습니다.",
    "식상": "표현력과 매력이 도드라지며 새로운 인연이 자연스럽게 다가올 수 있는 흐름입니다.",
    "재성": "현실적인 조건과 상황 속에서 인연이 이어지거나 발전할 가능성이 있는 흐름입니다.",
    "관성": "책임감 있는 관계, 혹은 공적인 자리에서 만난 인연이 이어질 수 있는 흐름입니다.",
    "인성": "정서적으로 깊이 통하는 인연, 혹은 오래된 관계가 더 단단해질 수 있는 흐름입니다.",
}

# ProfileStatus.tsx의 RelationshipStatus 값과 동일 어휘("single"/"dating"/"married") —
# domains/daily/status_variants.py 와 같은 스키마(사용자 확정, 임의로 다른 이름 금지).
RELATIONSHIP_STATUS_GUIDE: Dict[str, str] = {
    "single": "지금은 새로운 인연에 마음을 열어보기 좋은 흐름이니, 익숙한 관계 안에서든 새로운 자리에서든 자연스럽게 다가오는 기회를 놓치지 마세요.",
    "dating": "지금의 관계를 더 단단하게 다질 수 있는 흐름이니, 서로의 속도를 맞추며 신뢰를 쌓아가는 데 집중해 보세요.",
    "married": "부부 사이의 역할과 소통을 다시 한번 점검하기 좋은 흐름이니, 서로에게 고마움을 표현하는 작은 습관을 만들어보세요.",
}

# ── family: change_flow/warning ────────────────────────────────────────
FAMILY_FLOW: Dict[str, Dict[str, str]] = {
    "비겁": {
        "change_flow": "가족 안에서도 각자의 독립성을 존중하는 방향으로 관계가 변화할 수 있는 시기입니다.",
        "warning": "가족과도 지나치게 경쟁하듯 대하지 않도록 부드러운 태도가 필요합니다.",
    },
    "식상": {
        "change_flow": "가족과 감정을 풍부하게 나누며 표현이 늘어나는 시기입니다.",
        "warning": "감정 기복이 가족에게 그대로 전달되지 않도록 조절하는 노력이 필요합니다.",
    },
    "재성": {
        "change_flow": "가족을 위한 경제적 책임이 커지거나 현실적인 문제들을 챙기게 되는 시기입니다.",
        "warning": "돈 문제로 가족과 갈등이 생기지 않도록 미리 소통해두는 것이 좋습니다.",
    },
    "관성": {
        "change_flow": "가족 안에서 책임 있는 역할, 기둥 역할이 커지는 시기입니다.",
        "warning": "원칙을 앞세우다 가족의 마음을 헤아리지 못하지 않도록 유연함이 필요합니다.",
    },
    "인성": {
        "change_flow": "가족에게 정서적 지지와 조언을 아끼지 않게 되는 시기입니다.",
        "warning": "가족의 일에 지나치게 관여하지 않도록 적당한 거리를 유지하는 것도 중요합니다.",
    },
}


def _get(table: Dict[str, str], group: str, default: str) -> str:
    return table.get(group, default)


def build_career_or_study(group: str, is_adult: bool) -> Dict[str, str]:
    table = CAREER_ADULT if is_adult else CAREER_YOUTH
    return dict(table.get(group) or next(iter(table.values())))


def build_wealth_flow(group: str) -> Dict[str, str]:
    return dict(WEALTH_FLOW.get(group) or next(iter(WEALTH_FLOW.values())))


def build_relationship(group: str, love_status: Optional[str], is_current: bool) -> Dict[str, object]:
    guide = None
    if is_current and love_status in RELATIONSHIP_STATUS_GUIDE:
        guide = {love_status: RELATIONSHIP_STATUS_GUIDE[love_status]}
    elif is_current:
        guide = dict(RELATIONSHIP_STATUS_GUIDE)
    return {
        "flow": RELATIONSHIP_FLOW.get(group, RELATIONSHIP_FLOW["비겁"]),
        "guide_by_status": guide,
    }


def build_family(group: str) -> Dict[str, str]:
    return dict(FAMILY_FLOW.get(group) or next(iter(FAMILY_FLOW.values())))
