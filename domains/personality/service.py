"""나의 성격 / 나의 적성 — 원국(원판) 중심. 운(運) 아님. 점수 없음.

런타임 Gemini 호출 없음. 사전 생성 정적 DB(`domains/personality/data/personality_db.json`)
에서 일주(일간·일지) 간지로 성격(character)/적성(aptitude) 6필드를 조회한다.
DB 생성은 `scripts/generate_content_db.py --domain personality` 참고.
DB 에 없으면(일주 계산 실패 등) 고정 폴백을 반환한다(is_fallback=True).

landscape(이 사주의 풍경적 해석)는 domains/lifelong/landscape.py의 build_landscape()를
그대로 재사용한다 — day_master_elem·elem_power·yongsin은 도메인과 무관하게 매 요청마다
동일하게 계산되는 값이라, 평생운세 전용 로직이 아니다.

bridge(아래 성격/적성이 어떤 사주적 해석에서 나오는지 잇는 한 문장)는 일간 오행 5개 ×
신강약 3개(=15개 조합)를 작은 블록 두 개(_ELEM_TRAIT/_VERDICT_TRAIT)의 조합으로 실시간
합성한다 — 일주 60개 × character/aptitude 전용 문구를 새로 만들면 다시 대규모 콘텐츠
생성이 필요해지므로, 이미 계산되는 진짜 명리 사실만으로 충분히 설명 가능한 축(오행·
신강약)을 골랐다. 사주 전문 용어(오행 이름 자체는 이미 UI 전반에서 노출해 온 값이라
제외하고, 신강/신약/중화 같은 원시 용어)는 문장에 그대로 쓰지 않는다.
"""
from typing import Dict, Any, Tuple

from core.saju_base import calculate_saju
from domains.lifelong.landscape import build_landscape
from shared.public import person_summary
from shared.text_format import paragraphize
from domains.personality.content_db import lookup

# 일간 오행이 상징하는 기본 기질 — SUBJECT_IMAGE(형상)와는 다른 축으로, "움직이는 방향"을
# 짧은 수식어로 표현한다.
_ELEM_TRAIT: Dict[str, str] = {
    "목": "곧게 뻗어나가려는",
    "화": "활발하게 표현하려는",
    "토": "묵직하게 자리를 지키려는",
    "금": "분명하게 결단하려는",
    "수": "유연하게 흐르려는",
}
_DEFAULT_ELEM_TRAIT = "고유한 방향으로 나아가려는"

# strength.verdict(신강/신약/중화) → 원국 전체가 움직이는 태도.
_VERDICT_TRAIT: Dict[str, str] = {
    "신강": "스스로의 중심이 단단해 주도적으로 움직이는",
    "신약": "주변의 흐름과 사람들에게 기대어 유연하게 움직이는",
    "중화": "안팎의 균형을 잡으며 상황에 맞게 움직이는",
}


def _verdict_key(strength: Dict[str, Any]) -> str:
    v = strength.get("verdict")
    return v if v in _VERDICT_TRAIT else "중화"


def _character_bridge(day_master_elem: str, verdict: str) -> str:
    elem_trait = _ELEM_TRAIT.get(day_master_elem, _DEFAULT_ELEM_TRAIT)
    verdict_trait = _VERDICT_TRAIT[verdict]
    return (
        f"일간이 {day_master_elem} 기운인 이 사람은 {elem_trait} 힘을 타고났고, "
        f"원국 전체로 보면 {verdict_trait} 유형입니다. 이 두 가지가 만나 아래의 성격으로 "
        "드러납니다."
    )


def _aptitude_bridge(day_master_elem: str, verdict: str) -> str:
    elem_trait = _ELEM_TRAIT.get(day_master_elem, _DEFAULT_ELEM_TRAIT)
    verdict_trait = _VERDICT_TRAIT[verdict]
    return (
        f"일간이 {day_master_elem} 기운인 이 사람은 {elem_trait} 힘을 타고났고, "
        f"원국 전체로 보면 {verdict_trait} 유형입니다. 이 두 가지가 만나 아래의 적성으로 "
        "이어집니다."
    )


def _saju(year, month, day, hour, minute, gender, is_lunar):
    return calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)


def _character_fallback() -> dict:
    return {
        "base_nature": "자기 기준이 뚜렷하고, 하고 싶은 일이 생기면 스스로 방향을 정해 움직이는 편입니다. 남이 정해준 길보다 내가 납득한 길에서 힘이 납니다. 다만 페이스가 빠르다 보니 주변이 따라오는 속도를 놓칠 때가 있어요.",
        "strengths": "핵심을 빨리 파악하고, 한번 정한 건 끝까지 밀고 갑니다. 위기 상황에서 오히려 침착해지는 유형이라, 급한 일이 생겼을 때 사람들이 당신을 찾게 됩니다.",
        "weaknesses": "내 판단에 확신이 강해서 다른 의견을 늦게 받아들입니다. 성과에 몰입하다 휴식과 감정 관리를 뒤로 미루는 습관도 있어요.",
        "supplement": "결정 전에 신뢰하는 한 사람에게 먼저 말해보는 루틴, 그리고 주 1회는 아무 목적 없는 휴식을 의무적으로 넣어보세요. 부족한 결을 채워줍니다.",
        "relationships": "말이 앞서기보다 행동으로 챙기는 스타일이라 가까운 사람에겐 신뢰가 두텁습니다. 대신 표현이 담백해서 처음엔 차갑게 느껴질 수 있어요. 먼저 안부를 묻는 연습이 관계를 넓혀줍니다.",
        "work_style": "명확한 목표와 자율성이 주어질 때 최고의 성과를 냅니다. 마이크로매니징을 받으면 급격히 동력이 떨어져요. 스스로 마감과 우선순위를 설계하는 환경이 잘 맞습니다.",
    }


def _aptitude_fallback() -> dict:
    return {
        "fit_task": "기획하고 구조를 짜는 일, 문제를 분해해 해결책을 만드는 일에 강합니다. 반복 업무보다 새로 설계하는 업무에서 몰입도가 올라갑니다.",
        "fit_field": "전략/기획, 전문 기술·연구, 1인 사업이나 전문직처럼 결과가 명확히 드러나는 분야가 잘 맞습니다.",
        "good_env": "목표만 주고 방법은 맡기는 조직, 성과를 투명하게 인정하는 문화에서 능력이 커집니다.",
        "org_style": "수평적이고 실무 중심 팀에서 자기 몫을 확실히 하는 스타일. 형식적인 보고 라인이 길면 답답해합니다.",
        "tiring_env": "잦은 방향 전환, 불명확한 지시, 감정 소모가 큰 인간관계가 겹치면 빠르게 지칩니다.",
        "favorable_direction": "속도를 조금 늦추고 주변 피드백을 자산으로 삼을 때, 그리고 내 강점이 드러나는 전문 영역을 깊게 팔 때 가장 유리합니다.",
    }


def _shape(saju: Dict[str, Any], content_type: str, fallback: dict, raw: dict, bridge: str) -> dict:
    landscape = build_landscape(saju)
    return {
        "content_type": content_type,
        "saju_info": person_summary(saju),
        "landscape": {"scene": landscape["scene"], "reason": landscape["reason"]},
        "bridge": bridge,
        "report": {k: paragraphize(str(raw.get(k, ""))) for k in fallback},
    }


def analyze_character(year, month, day, hour=None, minute=0, gender="female", is_lunar=False) -> Tuple[dict, bool]:
    saju = _saju(year, month, day, hour, minute, gender, is_lunar)
    entry = lookup(saju.get("day_ganji") or "", "character")
    is_fallback = entry is None
    raw = _character_fallback() if is_fallback else entry
    bridge = _character_bridge(saju.get("day_master_elem") or "", _verdict_key(saju.get("strength") or {}))
    return _shape(saju, "나의 성격", _character_fallback(), raw, bridge), is_fallback


def analyze_aptitude(year, month, day, hour=None, minute=0, gender="female", is_lunar=False) -> Tuple[dict, bool]:
    saju = _saju(year, month, day, hour, minute, gender, is_lunar)
    entry = lookup(saju.get("day_ganji") or "", "aptitude")
    is_fallback = entry is None
    raw = _aptitude_fallback() if is_fallback else entry
    bridge = _aptitude_bridge(saju.get("day_master_elem") or "", _verdict_key(saju.get("strength") or {}))
    return _shape(saju, "나의 적성", _aptitude_fallback(), raw, bridge), is_fallback
