"""평생운세 섹션3 '고민 심화 분석' — selected_concern 4단계 명리 스키마.

AI 호출 없음. 이미 계산돼 있는 실제 명리 사실(day_master_elem, strength.verdict·
yongsin·gisin·heesin·elem_power, daewoon_step_facts)을 조합해 작은 고정 표에서
문장을 고른다 — landscape.py/spouse_outlook.py와 같은 설계다. 도메인별 전용 4단계
콘텐츠를 정적 DB로 새로 만들면 일주×십신군×순번×concern 조합이 다시 폭발하므로,
이미 계산되는 진짜 명리 사실(용신·기신·신강약·대운 십신군 흐름)로 실시간 합성한다.

말투 규칙은 scripts/generate_content_db.py 프롬프트들과 동일: 십신·오행 등 사주
전문 용어(재성/관성/식상/용신/기신 등)는 사용자 문장에 절대 그대로 노출하지 않고
일상 언어로 풀어 쓴다(계산에만 씀).

4단계:
1) common_summary: 해당 영역 전체 흐름 + 운이 열리는 구체적 나이대. 8단계 대운
   중 그 영역의 앵커 기운이 오는 시기를 실제로 찾아(_find_timing_step) 나이로
   명시한다 — 이미 지났으면 "그 시기의 여운", 아직이면 "준비할 시기"로 시제를 나눈다.
2) saju_interpretation: 영역별로 다른 명리 축을 본다(사용자 확정) —
   money: 재물 기운의 용신/기신 여부 + 신강약(식상생재 구조는 오행 상생상 항상
          성립하는 구조적 사실이라 서두에 자연어로 얹는다)
   career: 관성/인성/식상 중 실제 세력이 가장 강한 축 + 신강약 → 추천 직무 방향
   social: 비겁/식상 중 실제 세력이 강한 축(둘 다 약하면 소수 정예형) + 신강약
           → 대인관계 규모(소수/대규모)
   family: 배우자성 유무(spouse_star, 4주 전체 실측) + 신강약 → 가치관/가족관계
3) critical_taboo: 도메인별 1:1 고정 경고(사용자 확정 — money=고위험투자/차용,
   career=수동적 통제환경, social=문서/보증관계, family=지나친 감정간섭). 근거가
   core_nature.weaknesses(성향 기반)와 완전히 달라 안 겹친다.
4) action_plan: 용신 오행(yongsin[0]) 기준 도메인별 즉시 실천 행동.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.constants import FIVE_ELEMENT_RELATIONS

_ELEMENTS = ["목", "화", "토", "금", "수"]

# section4~7(life_domains) 앵커와 동일 — 단일 소스 유지를 위해 domains/lifelong/service.py
# 가 이 상수를 그대로 재수출(import)한다.
DOMAIN_ANCHOR: Dict[str, str] = {"wealth": "재성", "career": "관성", "family": "인성", "social": "비겁"}

CONCERN_TO_DOMAIN: Dict[str, str] = {
    "money": "wealth", "wealth": "wealth", "career": "career", "social": "social", "family": "family",
}
CONCERN_LABELS: Dict[str, str] = {
    "wealth": "돈과 재물", "career": "일과 커리어", "social": "사람과 인맥", "family": "가족 관계",
}


def _elem_for_group(dm_elem: str, group: str) -> str:
    """일간 오행 기준으로 특정 십신군(재성/관성/식상/비겁/인성)에 해당하는 오행 한 글자."""
    for e in _ELEMENTS:
        if FIVE_ELEMENT_RELATIONS.get((dm_elem, e)) == group:
            return e
    return dm_elem


def _polarity(elem: str, strength: Dict[str, Any]) -> str:
    """용신/희신=favorable, 기신=unfavorable, 그 외(한신)=neutral."""
    if elem in (strength.get("gisin") or []):
        return "unfavorable"
    if elem in (strength.get("yongsin") or []) or elem in (strength.get("heesin") or []):
        return "favorable"
    return "neutral"


def _verdict_key(strength: Dict[str, Any]) -> str:
    v = strength.get("verdict")
    return v if v in ("신강", "신약", "중화") else "중화"


def _group_power(elem_power: Dict[str, float], dm_elem: str, group: str) -> float:
    return elem_power.get(_elem_for_group(dm_elem, group), 0.0)


def _find_timing_step(facts: List[Dict[str, Any]], anchor_group: str, current_step: int) -> int:
    """8단계 대운 중 anchor_group 이 지배하는 가장 가까운 단계. 없으면 현재 단계로 폴백
    (해당 기운이 8단계 중 한 번도 안 오는 경우는 실측상 드물지만 방어)."""
    matches = [f["step"] for f in facts if f["sipsin_group"] == anchor_group]
    if not matches:
        return current_step
    if current_step in matches:
        return current_step
    future = [s for s in matches if s > current_step]
    return min(future) if future else max(matches)


# ── 1단계: 공통 총평 ─────────────────────────────────────────────────────
_TENSE_CLAUSE: Dict[str, str] = {
    "current": "지금이 바로 이 흐름 한가운데에 있는 시기입니다.",
    "future": "아직 오지 않은 시기라, 미리 준비해두면 그 흐름을 제대로 탈 수 있습니다.",
    "past": "이미 지나온 시기에 가장 강하게 작용했던 흐름이라, 지금은 그 여운 위에서 다음 기회를 준비할 때입니다.",
}


def build_common_summary(domain: str, timing_step: int, current_step: int, age_range: Tuple[int, int]) -> str:
    label = CONCERN_LABELS[domain]
    tense = "current" if timing_step == current_step else ("future" if timing_step > current_step else "past")
    return (
        f"{label} 영역의 흐름은 만 {age_range[0]}~{age_range[1]}세 무렵 가장 뚜렷하게 열립니다. "
        f"{_TENSE_CLAUSE[tense]}"
    )


# ── 2단계: 명리적 해석 ───────────────────────────────────────────────────
# money: (재물 기운 희기 polarity) x (신강/신약/중화) = 3x3
_MONEY_INTERPRETATION: Dict[str, Dict[str, str]] = {
    "favorable": {
        "신강": "이 사람은 자신이 만들어내는 결과물이 자연스럽게 돈으로 이어지는 흐름을 타고났습니다. 재물 자체도 반가운 기운으로 작용해서, 적극적으로 움직일수록 돈이 따라붙는 구조예요. 기운이 넘치는 만큼 과감하게 확장해도 좋지만, 벌어들인 만큼 관리하는 습관을 함께 들여야 오래갑니다.",
        "신약": "내가 이룬 성과가 자연스럽게 재물로 연결되는 흐름을 가진 사람입니다. 재물운 자체는 반가운 기운이라 애쓴 만큼 결실이 따르지만, 몸과 마음의 에너지가 크지 않은 편이라 무리한 확장보다는 하나씩 차근차근 쌓아가는 쪽이 훨씬 유리합니다.",
        "중화": "내가 낸 결과물이 돈으로 잘 연결되는 균형 잡힌 흐름을 갖고 있습니다. 재물운이 반가운 기운으로 작용하니, 지금의 리듬을 꾸준히 지켜나가는 것만으로도 안정적인 결실을 볼 수 있어요.",
    },
    "unfavorable": {
        "신강": "에너지가 넘치는 만큼 뭐든 밀어붙이고 싶지만, 정작 재물 자체는 부담으로 작용하는 구조라 욕심을 낼수록 오히려 손에 남는 게 줄어들기 쉽습니다. 확장보다는 이미 가진 것을 지키고 다지는 방향이 훨씬 유리합니다.",
        "신약": "몸도 마음도 에너지가 크지 않은데 재물마저 부담스러운 기운으로 작용하는 구조라, 무리한 투자나 확장은 특히 피해야 합니다. 크게 벌기보다 안정적으로 지키는 재물 감각을 기르는 편이 훨씬 이롭습니다.",
        "중화": "균형 잡힌 기운이지만 재물 자체는 다소 까다로운 기운으로 작용하는 구조입니다. 큰 수익을 좇기보다 꾸준하고 안전한 방식으로 자산을 관리하는 쪽이 훨씬 안정적입니다.",
    },
    "neutral": {
        "신강": "내가 만든 결과물이 돈으로 이어지는 구조는 갖고 있지만, 재물 자체가 특별히 좋지도 나쁘지도 않은 자리라 노력한 만큼만 정직하게 돌아옵니다. 기운이 넘치는 시기이니 꾸준한 실행력이 재물운을 끌어올리는 열쇠가 됩니다.",
        "신약": "결과물이 재물로 이어지는 구조는 있지만 재물운 자체는 중립적인 자리라, 무리하지 않고 페이스를 지키는 것이 관건입니다. 에너지를 아껴가며 꾸준히 관리하면 서서히 안정을 찾아갑니다.",
        "중화": "내가 낸 성과가 돈으로 이어지는 자연스러운 구조를 갖고 있고, 재물운 자체도 특별히 치우치지 않은 안정적인 자리입니다. 지금의 균형을 꾸준히 유지하는 것이 가장 좋은 전략입니다.",
    },
}

# career: (관성/인성/식상 중 실세력 우세 축) x (신강/신약/중화) = 3x3
_CAREER_INTERPRETATION: Dict[str, Dict[str, str]] = {
    "관성": {
        "신강": "규율과 책임이 뚜렷한 자리에서 오히려 힘을 내는 구조를 가졌습니다. 기운이 강한 편이라 위로 올라갈수록, 책임이 커질수록 능력이 더 잘 드러나는 타입이에요. 조직이나 공적인 자리에서 리더 역할을 맡아보는 것이 잘 맞습니다.",
        "신약": "책임과 규율이 있는 자리에서 성장하는 구조지만, 에너지가 크지 않은 편이라 처음부터 너무 무거운 책임을 지면 쉽게 지칠 수 있습니다. 단계적으로 역할을 키워가는 조직 생활이 가장 잘 맞습니다.",
        "중화": "체계와 역할이 분명한 환경에서 안정적으로 성장하는 구조를 가졌습니다. 균형 잡힌 기운 덕분에 꾸준히 자리를 지키다 보면 자연스럽게 신뢰와 책임이 쌓입니다.",
    },
    "인성": {
        "신강": "배우고 익히는 과정 자체가 경쟁력이 되는 구조입니다. 기운이 넘치는 편이라 전문 지식이나 자격을 빠르게 쌓아, 그걸 무기로 삼는 직무에서 특히 두각을 나타냅니다.",
        "신약": "배움과 전문성이 곧 힘이 되는 구조를 가졌습니다. 에너지가 크지 않은 편이니 조급하게 넓히기보다 한 분야를 깊게 파고드는 쪽이 훨씬 유리하며, 그 깊이가 결국 인정받는 무기가 됩니다.",
        "중화": "꾸준한 배움이 곧 실력이 되는 균형 잡힌 구조입니다. 서두르지 않고 차곡차곡 전문성을 쌓아가는 학습형 커리어가 가장 잘 맞습니다.",
    },
    "식상": {
        "신강": "아이디어와 표현력이 곧 무기가 되는 구조입니다. 기운이 넘치는 편이라 창의적인 기획이나 콘텐츠, 사람들 앞에 나서는 일에서 에너지를 마음껏 발산할 때 성과가 커집니다.",
        "신약": "생각과 표현이 자연스럽게 재능으로 이어지는 구조를 가졌습니다. 다만 에너지가 크지 않은 편이라 한 번에 너무 많은 걸 벌이기보다, 좋아하는 한 가지 표현 방식에 집중하는 편이 오래갑니다.",
        "중화": "창의성과 표현력이 균형 있게 발휘되는 구조입니다. 기획하고 만들어내는 일에서 꾸준히 실력을 쌓아가면 자연스럽게 자리를 잡습니다.",
    },
}

# social: (비겁/식상 중 실세력 우세 축, 둘 다 약하면 balanced) x (신강/신약/중화) = 3x3
_SOCIAL_INTERPRETATION: Dict[str, Dict[str, str]] = {
    "비겁": {
        "신강": "또래나 동료와 어울릴 때 특히 힘을 내는 구조입니다. 기운이 넘치는 편이라 폭넓은 인맥 속에서 자연스럽게 리더 역할을 맡게 되고, 대규모 모임이나 조직에서도 주눅 들지 않고 존재감을 드러냅니다.",
        "신약": "동료·또래와의 관계 속에서 힘을 얻는 구조지만, 에너지가 크지 않은 편이라 너무 많은 관계를 한꺼번에 챙기면 쉽게 지칠 수 있습니다. 믿을 만한 소수의 동료 그룹을 중심으로 관계를 넓혀가는 편이 좋습니다.",
        "중화": "또래·동료 관계에서 안정적으로 힘을 얻는 균형 잡힌 구조입니다. 자연스럽게 사람이 모이는 편이라 무리하지 않아도 인맥이 꾸준히 넓어집니다.",
    },
    "식상": {
        "신강": "말과 표현으로 사람을 끌어모으는 구조입니다. 기운이 넘치는 편이라 활발하게 나서서 소통할수록 인맥이 눈덩이처럼 불어나는 타입이라, 대규모 네트워크에서도 잘 어울립니다.",
        "신약": "표현력으로 사람의 마음을 끄는 구조를 가졌지만, 에너지가 크지 않은 편이라 너무 많은 자리를 동시에 소화하면 쉽게 소진됩니다. 소중한 몇몇 관계에 정성을 쏟는 편이 훨씬 오래갑니다.",
        "중화": "자연스러운 표현력으로 사람과 편안하게 연결되는 균형 잡힌 구조입니다. 억지로 넓히지 않아도 대화와 소통 속에서 인연이 꾸준히 이어집니다.",
    },
    "balanced": {
        "신강": "넓게 퍼지기보다 깊게 파고드는 관계를 선호하는 구조입니다. 기운이 강한 편이라 소수의 사람들과 깊이 연결되면서도 그 안에서 확실한 존재감을 드러냅니다.",
        "신약": "소수와 깊게 맺는 관계에서 안정을 느끼는 구조입니다. 에너지가 크지 않은 편이니 무리해서 인맥을 넓히기보다, 이미 곁에 있는 소중한 사람들과의 관계를 다지는 데 집중하는 것이 좋습니다.",
        "중화": "소수 정예의 깊은 관계 속에서 편안함을 느끼는 균형 잡힌 구조입니다. 자연스럽게 곁에 남는 사람들과 오래도록 진솔한 관계를 이어갑니다.",
    },
}

# family: (배우자성 유무) x (신강/신약/중화) = 2x3
_FAMILY_INTERPRETATION: Dict[str, Dict[str, str]] = {
    "present": {
        "신강": "배우자와 자녀 모두와의 인연이 비교적 자연스럽게 이어지는 구조입니다. 기운이 넘치는 편이라 가정에서도 주도적인 역할을 맡게 되는데, 가족의 의견을 앞서서 정하기보다 함께 결정하는 태도를 들이면 훨씬 화목해집니다.",
        "신약": "배우자와 자녀 모두와의 인연이 순조롭게 이어지는 구조입니다. 에너지가 크지 않은 편이니 가족을 위해 혼자 다 짊어지려 하지 말고, 가족에게도 역할을 나누어 맡기면 관계가 한결 편안해집니다.",
        "중화": "배우자, 자녀와의 인연이 안정적으로 이어지는 균형 잡힌 구조입니다. 지금처럼 서로를 존중하는 태도를 꾸준히 지켜가면 오래도록 화목한 가정을 이룹니다.",
    },
    "absent": {
        "신강": "배우자나 자녀와의 인연이 저절로 다가오기보다 스스로 만들어가야 하는 구조입니다. 기운이 넘치는 편이라 가정보다 바깥일에 에너지가 쏠리기 쉬우니, 의식적으로 가족과 보내는 시간을 따로 떼어두는 것이 중요합니다.",
        "신약": "배우자나 자녀와의 인연이 적극적으로 움직여야 만들어지는 구조입니다. 에너지가 크지 않은 편이라 가족 관계에서도 무리하지 않는 선에서, 짧더라도 꾸준한 애정 표현으로 관계를 다져가는 것이 좋습니다.",
        "중화": "배우자나 자녀와의 인연이 서서히, 스스로 노력한 만큼 만들어지는 균형 잡힌 구조입니다. 조급해하지 않고 꾸준히 마음을 표현하다 보면 자연스럽게 가까운 인연이 쌓여갑니다.",
    },
}


def build_saju_interpretation(
    domain: str, day_master_elem: str, strength: Dict[str, Any], spouse_present: Optional[bool],
) -> str:
    verdict = _verdict_key(strength)
    if domain == "wealth":
        elem = _elem_for_group(day_master_elem, "재성")
        return _MONEY_INTERPRETATION[_polarity(elem, strength)][verdict]
    if domain == "career":
        elem_power = strength.get("elem_power") or {}
        axis = max(
            ("관성", "인성", "식상"),
            key=lambda g: _group_power(elem_power, day_master_elem, g),
        )
        return _CAREER_INTERPRETATION[axis][verdict]
    if domain == "social":
        elem_power = strength.get("elem_power") or {}
        bigeop = _group_power(elem_power, day_master_elem, "비겁")
        siksang = _group_power(elem_power, day_master_elem, "식상")
        if bigeop >= siksang * 1.3 and bigeop > 0:
            axis = "비겁"
        elif siksang >= bigeop * 1.3 and siksang > 0:
            axis = "식상"
        else:
            axis = "balanced"
        return _SOCIAL_INTERPRETATION[axis][verdict]
    if domain == "family":
        key = "present" if spouse_present else "absent"
        return _FAMILY_INTERPRETATION[key][verdict]
    return ""


# ── 3단계: 치명적 금기 — 도메인별 1:1 고정(사용자 확정), 하단 weaknesses 와 근거 분리 ──
CRITICAL_TABOO: Dict[str, str] = {
    "wealth": "빚을 내서 투자하거나 검증되지 않은 고수익 제안에 뛰어드는 것은 이 사람에게 가장 위험한 선택입니다. 특히 지인의 부탁으로 돈을 빌려주거나 보증을 서는 일은 반드시 피해야 할 금기입니다.",
    "career": "내 의지와 무관하게 모든 걸 통제당하는 수동적인 환경은 이 사람의 기운을 가장 크게 갉아먹습니다. 스스로 판단하고 움직일 여지가 전혀 없는 자리는 아무리 조건이 좋아도 오래 버티기 어렵습니다.",
    "social": "잘 알지 못하는 사람의 부탁으로 서류에 도장을 찍거나 보증을 서는 일은 절대 피해야 합니다. 특히 돈이 얽힌 문서 관계는 아무리 가까운 사이라도 한 번 더 신중하게 따져봐야 합니다.",
    "family": "가족을 아낀다는 이유로 배우자나 자녀의 삶에 지나치게 개입하고 통제하려 드는 것은 오히려 관계를 멀어지게 만드는 가장 큰 금기입니다. 걱정되는 마음이 들어도 한 걸음 물러나 지켜봐 주는 여유가 필요합니다.",
}


# ── 4단계: 맞춤 액션 플랜 — 용신 오행(yongsin[0]) x 도메인 = 5x4 ──
_ACTION_PLAN: Dict[str, Dict[str, str]] = {
    "목": {
        "wealth": "돈 관리에 있어 하루 5분이라도 가계부나 자산 현황을 들여다보는 습관을 들이면 재물운이 서서히 자라납니다. 초록빛 식물을 책상 위에 두는 것도 좋은 기운을 북돋아 줍니다.",
        "career": "새로운 것을 배우는 강의나 책을 하나 정해 꾸준히 진도를 나가보세요. 성장하는 감각 자체가 커리어의 좋은 기운을 끌어옵니다.",
        "social": "오랫동안 연락이 뜸했던 사람에게 먼저 안부를 물어보세요. 관계를 새롭게 틔우는 작은 행동이 인맥운을 키워줍니다.",
        "family": "가족과 함께 산책하거나 화분을 가꾸는 시간을 만들어보세요. 함께 무언가를 키워가는 경험이 가족 사이의 정을 더 깊게 만듭니다.",
    },
    "화": {
        "wealth": "재테크나 투자 관련 정보를 적극적으로 찾아보고 사람들과 이야기 나눠보세요. 활발하게 움직일수록 돈의 흐름이 눈에 들어옵니다.",
        "career": "내 성과를 적극적으로 알리고 발표할 기회를 만들어보세요. 밝고 적극적인 태도가 커리어의 문을 열어줍니다.",
        "social": "모임이나 행사에 먼저 나서서 사람들과 어울려보세요. 밝은 에너지를 나눌수록 좋은 인연이 따라옵니다.",
        "family": "가족에게 오늘 있었던 일을 먼저 밝게 이야기해보세요. 따뜻하고 활기찬 대화가 가족 분위기를 데워줍니다.",
    },
    "토": {
        "wealth": "정기적금처럼 꾸준하고 안정적인 재테크 습관을 하나 정해 실천해보세요. 흔들리지 않는 루틴이 재물을 단단하게 쌓아줍니다.",
        "career": "매일 같은 시간에 가장 중요한 업무를 처리하는 루틴을 만들어보세요. 꾸준함이 신뢰로 이어져 커리어를 다져줍니다.",
        "social": "새로운 사람보다 이미 맺어온 인연을 정기적으로 챙기는 데 집중해보세요. 오래된 관계를 다지는 것이 가장 큰 자산이 됩니다.",
        "family": "매주 정해진 시간에 가족과 함께하는 루틴(식사, 통화 등)을 만들어보세요. 변하지 않는 약속이 가족의 안정감을 키워줍니다.",
    },
    "금": {
        "wealth": "불필요한 지출 항목이나 정리가 필요한 계약을 과감히 정리해보세요. 맺고 끊음이 분명할수록 재물이 깔끔하게 정돈됩니다.",
        "career": "우선순위가 낮은 업무나 관계를 정리하고, 핵심 목표에만 집중하는 시간을 만들어보세요. 결단력이 커리어의 다음 단계를 열어줍니다.",
        "social": "불편한 관계나 소모적인 모임을 정리하고, 진짜 소중한 사람에게 시간을 쓰세요. 명확한 기준이 좋은 인연만 남겨줍니다.",
        "family": "가족 사이의 애매한 역할 분담이나 오해를 이번 기회에 명확하게 정리해보세요. 분명한 대화가 오히려 관계를 편안하게 만듭니다.",
    },
    "수": {
        "wealth": "충동적인 지출을 줄이고, 혼자 조용히 재정 계획을 점검하는 시간을 가져보세요. 차분한 정리가 재물운을 깊게 만듭니다.",
        "career": "혼자 집중할 수 있는 시간과 공간을 확보해 중요한 일을 처리해보세요. 고요함 속에서 나오는 통찰이 커리어를 키워줍니다.",
        "social": "억지로 관계를 넓히기보다, 혼자만의 시간을 가지며 에너지를 채운 뒤 사람을 만나보세요. 여유로운 태도가 오히려 좋은 인연을 끌어당깁니다.",
        "family": "가족과 조용히 마주 앉아 서로의 이야기를 깊이 들어주는 시간을 가져보세요. 잔잔한 대화가 가족 사이의 신뢰를 깊게 만듭니다.",
    },
}

_DEFAULT_ACTION_PLAN: Dict[str, str] = {
    "wealth": "지금의 재정 흐름을 꾸준히 유지하는 것만으로도 충분합니다. 한 달에 한 번, 자산 현황을 점검하는 루틴을 만들어보세요.",
    "career": "지금 맡은 일에 충실하며 페이스를 유지하는 것이 가장 좋은 전략입니다. 작은 성취를 꾸준히 기록해보세요.",
    "social": "지금의 관계를 소중히 유지하는 데 집중해보세요. 가까운 사람에게 안부를 전하는 것만으로도 충분합니다.",
    "family": "지금의 가족 관계를 꾸준히 지켜나가는 것이 가장 좋은 선택입니다. 짧은 안부 인사를 자주 건네보세요.",
}


def build_action_plan(domain: str, yongsin: List[str]) -> str:
    elem = yongsin[0] if yongsin else None
    table = _ACTION_PLAN.get(elem or "", {})
    return table.get(domain) or _DEFAULT_ACTION_PLAN[domain]


def build_highlight(
    selected_concern: Optional[str],
    *,
    day_master_elem: str,
    strength: Dict[str, Any],
    spouse_present: Optional[bool],
    facts: List[Dict[str, Any]],
    current_step: int,
    daewoon_num: int,
) -> Optional[Dict[str, Any]]:
    """사전 질문(selected_concern)에 대한 답변 전용 4단계 하이라이트. 질문을 안 받았거나
    모르는 값이면 None(카드 자체를 숨긴다 — 답변 용도로만 쓴다)."""
    domain = CONCERN_TO_DOMAIN.get((selected_concern or "").strip().lower())
    if not domain:
        return None

    anchor_group = DOMAIN_ANCHOR[domain]
    timing_step = _find_timing_step(facts, anchor_group, current_step)
    start_age = daewoon_num + (timing_step - 1) * 10
    age_range = (start_age, start_age + 9)

    return {
        "selected_concern": selected_concern,
        "title": f"선택하신 [{CONCERN_LABELS[domain]}] 영역 집중 분석",
        "common_summary": build_common_summary(domain, timing_step, current_step, age_range),
        "saju_interpretation": build_saju_interpretation(domain, day_master_elem, strength, spouse_present),
        "critical_taboo": CRITICAL_TABOO[domain],
        "action_plan": build_action_plan(domain, strength.get("yongsin") or []),
    }
