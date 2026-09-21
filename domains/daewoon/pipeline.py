"""10년 대운 해석 엔진(v3, 2026-09-21 3차 개편) — "원국 × 대운 × 생애단계 × 영역별 구조" 기반.

**이 파일의 이력**: v1(7단계 파이프라인 최초 구현) → v2(생애단계 게이트 + 영역별 독립
valence) → **v3(이번 개편)**: 2차 코드 감사에서 확인된 잔여 문제 두 가지를 근본적으로
제거했다.
1. `SIPSIN_CHANGE_AREA`(10종→문구 1개, "영역" 축이 없는 전역 테이블)를 여러 영역이
   공유해 같은 십신이 여러 영역을 동시에 구동하면(예: 己未 대운의 천간·지지가 둘 다
   정관) "신분과 공적 신뢰"가 직업/애정/결혼에 그대로 복사되던 문제 — **영역별 vocab
   테이블**(CAREER_VOCAB/WEALTH_VOCAB/... 이하)로 교체해 영역마다 다른 현실 언어로
   번역한다.
2. `_DOMAIN_POLARITY_NOTE`("사주 전체 균형에는 부담을...")를 모든 영역에 동일하게
   append하던 문제 — 전체 균형 판단은 `global_context`(1회만 등장)로 분리하고, 영역별
   valence 문구는 **영역마다 다른 어휘**(_VALENCE_CLOSING, 이하)로 새로 썼다.

**아키텍처**: `DaewoonContext`(원국+대운+생애단계+성별+강약을 한데 묶은 공통 입력) →
`get_eligible_domains(age)`(분석 "전"에 생애단계로 먼저 걸러냄, 사후 필터 아님) →
9개 독립 analyzer 함수(analyze_self/analyze_study/analyze_career/analyze_wealth/
analyze_family/analyze_siblings/analyze_friendship/analyze_relationship/
analyze_marriage) → 각각 activation/valence/confidence/drivers/evidence/
manifestation/sentence를 반환 → activation>=3인 것만(=meaningful) 최종 노출,
나머지는 "변화 없음" 문구조차 없이 완전히 생략.

**"driver 하나=결론 하나" 금지**(2차 개편 신규): confidence(신호 개수)가 "high"일
때만 근거가 겹쳤다는 동적 부연 문장을 덧붙인다 — 이 부연은 도메인×십신 하드코딩이
아니라 실제 evidence 구성(천간/지지/관계 중 무엇이 맞았는지)에서 그대로 조립한다.

**회고형/검증 불가 문장 금지**(2차 개편 신규): "~했을 가능성이 있습니다"류의 과거
회고형 표현 대신 "~구조", "~흐름", "~경향"처럼 구조적 현재 시제만 쓴다.

기존 domain_analysis(career_or_study/wealth_flow/relationship/family 등,
content.py의 5분류+뉘앙스 표 기반)는 **이번 개편에서 건드리지 않았다** — 사용자가
"기존 UI/DB를 깨뜨리지 않는 방식으로 단계적으로" 진행하라고 명시했고, 이번 2차 감사
+개편의 명시적 성공 기준(4개 질문) 전부가 이 v3 엔진(domain_pipeline)을 대상으로
하기 때문. content.py 5분류 표 자체의 잔여 반복 문제는 별도 후속 작업으로 남겨둔다
(최종 보고서 "F. 남아 있는 한계" 참고).
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.constants import GAN_ELEM, JI_ELEM
from core.daewoon import branch_relation
from domains.daewoon.content import _josa, resolve_polarity_for_elem

GROUPS: List[str] = ["비겁", "식상", "재성", "관성", "인성"]

CHILD_AGE_THRESHOLD = 20  # service.py와 값 일치(테스트로 검증) — content.py 쪽 축.
KEY_AREA_MIN_SCORE = 3  # 이 이상만 "meaningful"로 최종 노출.

_RELATION_IMPACT: Dict[str, int] = {
    "육합": 2, "충": 2, "형": 1, "파": 1, "해": 1, "복음": 1, "자형": 1, "무관": 0,
}
_PALACE_LABEL: Dict[str, str] = {"year": "년주", "month": "월주", "day": "일주", "hour": "시주"}


def _relation_key(relation: str) -> str:
    r = relation or "무관"
    if r.startswith("복음"):
        return "자형" if "자형" in r else "복음"
    return r.split("(")[0] if "(" in r else r


def _is_female(gender: str) -> bool:
    return str(gender or "").strip().lower() in {"female", "f", "여", "여자", "여성"}


# ============================================================================
# 생애 단계(아동/청소년/청년/성인) — 영역별 노출 게이트.
# ============================================================================
LIFE_STAGE_ORDER: List[str] = ["아동", "청소년", "청년", "성인"]
_LIFE_STAGE_BOUNDS = [(0, 12, "아동"), (13, 19, "청소년"), (20, 34, "청년")]


def life_stage(age: int) -> str:
    for lo, hi, name in _LIFE_STAGE_BOUNDS:
        if lo <= age <= hi:
            return name
    return "성인"


def _relation_label(stage: str) -> str:
    """형제/친구 영역에서 생애단계에 따라 같은 비겁 구조를 다른 말로 번역할 때 쓰는
    호칭(사용자 지정: 어린 시기=또래, 청년=동료, 성인=네트워크)."""
    if stage in ("아동", "청소년"):
        return "또래"
    if stage == "청년":
        return "동료"
    return "네트워크"


def _wealth_stage_bucket(stage: str) -> str:
    """재물 영역 전용 3단계 버킷(사용자 지정: 아동·청소년=용돈, 청년=수입·지출·자산형성,
    성인=자산관리·생활안정)."""
    if stage in ("아동", "청소년"):
        return "미성년"
    if stage == "청년":
        return "청년"
    return "성인"


# ============================================================================
# DaewoonContext — 원국+대운+생애단계+성별+강약을 한데 묶은 공통 입력.
# ============================================================================
@dataclass
class DaewoonContext:
    natal: Dict[str, Any]
    daewoon: Dict[str, Any]
    life_stage: str
    gender: str
    strength: Dict[str, Any] = field(default_factory=dict)

    @property
    def spouse_group(self) -> str:
        return "관성" if _is_female(self.gender) else "재성"


# ============================================================================
# 1단계: 원국 분석
# ============================================================================
def analyze_natal_stage(saju: Dict[str, Any]) -> Dict[str, Any]:
    strength = saju.get("strength") or {}
    sipsin_map = saju.get("sipsin") or {}
    natal_sipsin: Dict[str, Dict[str, str]] = {}
    for pos in ("year", "month", "day", "hour"):
        gan_key, ji_key = f"{pos}_gan", f"{pos}_ji"
        if gan_key in sipsin_map:
            natal_sipsin[pos] = {"gan": sipsin_map.get(gan_key, ""), "ji": sipsin_map.get(ji_key, "")}
    return {
        "day_master": saju.get("day_master", ""),
        "day_master_elem": saju.get("day_master_elem", ""),
        "five_elements": dict(saju.get("five_elements") or {}),
        "strength_verdict": strength.get("verdict", "중화"),
        "yongsin": list(strength.get("yongsin") or []),
        "heesin": list(strength.get("heesin") or []),
        "gisin": list(strength.get("gisin") or []),
        "natal_sipsin": natal_sipsin,
    }


# ============================================================================
# 2단계: 대운 분석
# ============================================================================
def analyze_daewoon_stage(saju: Dict[str, Any], fact: Dict[str, Any]) -> Dict[str, Any]:
    ganji = fact.get("ganji", "")
    gan = ganji[0] if ganji else ""
    ji = ganji[1] if len(ganji) > 1 else ""
    gan_elem = GAN_ELEM.get(gan, "")
    ji_elem = JI_ELEM.get(ji, "")
    strength = saju.get("strength") or {}
    polarity = resolve_polarity_for_elem(gan_elem, strength)

    pillar_ganji: Dict[str, str] = {
        "year": saju.get("year_ganji", ""),
        "month": saju.get("month_ganji", ""),
        "day": saju.get("day_ganji", ""),
    }
    time_ganji = saju.get("time_ganji", "")
    if time_ganji:
        pillar_ganji["hour"] = time_ganji

    relations: Dict[str, str] = {}
    for pos, gz in pillar_ganji.items():
        natal_branch = gz[1] if len(gz) > 1 else ""
        relations[pos] = branch_relation(natal_branch, ji) if natal_branch and ji else "무관"

    elem_power = dict(strength.get("elem_power") or {})
    balance_shift = "neutral"
    if elem_power:
        before_spread = max(elem_power.values()) - min(elem_power.values())
        after = dict(elem_power)
        if gan_elem:
            after[gan_elem] = after.get(gan_elem, 0.0) + 1.0
        if ji_elem:
            after[ji_elem] = after.get(ji_elem, 0.0) + 0.6
        after_spread = max(after.values()) - min(after.values())
        if after_spread > before_spread + 0.05:
            balance_shift = "widens"
        elif after_spread < before_spread - 0.05:
            balance_shift = "narrows"

    return {
        "ganji": ganji,
        "gan_sipsin": fact.get("sipsin", ""),
        "ji_sipsin": fact.get("sipsin_ji", ""),
        "gan_group": fact.get("sipsin_group", ""),
        "ji_group": fact.get("sipsin_group_ji", ""),
        "gan_elem": gan_elem,
        "ji_elem": ji_elem,
        "relations": relations,
        "polarity": polarity,
        "balance_shift": balance_shift,
    }


def get_eligible_domains(age: int) -> frozenset:
    """생애단계 기준으로 "분석 대상이 될 수 있는" 영역만 먼저 골라낸다(사용자 지정:
    "생애단계 필터는 문장 생성 후 삭제가 아니라 분석 전에 적용"). build_domain_pipeline()
    은 이 결과에 없는 영역은 아예 analyzer를 호출하지 않는다(디버그 모드 제외)."""
    stage = life_stage(age)
    return frozenset(key for key, defn in DOMAIN_DEFINITIONS.items() if stage in defn["stages"])


# ============================================================================
# 영역별 vocab — "십신 하나 = 전역 문구 하나"가 아니라 영역마다 다른 현실 언어로
# 번역한다(사용자 명시 금지사항: "정관=신분과 공적 신뢰"를 직업·연애·결혼에 그대로
# 복사). 각 표는 그 영역에서 실제로 유의미한 십신만 담는다(영역별 groups와 1:1 대응).
# ============================================================================
CAREER_VOCAB: Dict[str, str] = {
    "비견": "동료와 대등한 위치에서 역할을 나눠 맡는 구조",
    "겁재": "스스로 판을 주도하거나 독립적으로 움직이는 역할 구조",
    "식신": "꾸준한 실무 능력으로 평가받는 역할 구조",
    "상관": "새로운 방식이나 아이디어로 존재감을 드러내는 역할 구조",
    "정재": "정해진 성과 기준을 착실히 채워가는 역할 구조",
    "편재": "여러 기회를 넓게 다루는 역할 구조",
    "정관": "조직이 요구하는 기준과 절차를 따르는 역할 구조",
    "편관": "책임이 무겁거나 압박이 큰 자리를 맡는 역할 구조",
    "정인": "자격이나 전문성으로 인정받는 역할 구조",
    "편인": "특수한 기술이나 전문 영역으로 평가받는 역할 구조",
}

# 재물: 생애단계별 3버킷(미성년=용돈/청년=수입·지출·자산형성/성인=자산관리·생활안정).
WEALTH_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "정재": "용돈을 계획적으로 관리하는 태도",
        "편재": "여러 곳에 씀씀이가 퍼지는 소비 태도",
        "식신": "좋아하는 것에 꾸준히 용돈을 쓰는 태도",
        "상관": "갖고 싶은 게 생기면 바로 쓰고 싶어하는 소비 태도",
        "비견": "친구와 나눠 쓰는 데 아낌없는 소비 태도",
        "겁재": "자기 뜻대로 쓰고 싶어하는 소비 태도",
    },
    "청년": {
        "정재": "고정적인 수입을 착실히 쌓아가는 재정 구조",
        "편재": "여러 기회로 수입을 넓혀가는 재정 구조",
        "식신": "꾸준한 활동으로 수입을 만들어가는 재정 구조",
        "상관": "새로운 방식으로 수입원을 만들어가는 재정 구조",
        "비견": "동료와 함께 벌고 나누는 재정 구조",
        "겁재": "스스로의 힘으로 벌어들이는 재정 구조",
    },
    "성인": {
        "정재": "이미 쌓은 자산을 안정적으로 관리하는 구조",
        "편재": "자산을 여러 곳에 배분하며 운용하는 구조",
        "식신": "꾸준한 활동을 자산으로 전환해가는 구조",
        "상관": "새로운 방식으로 자산을 불려가는 구조",
        "비견": "동료와 자산을 함께 관리하거나 나누는 구조",
        "겁재": "스스로 판단해 자산을 운용하는 구조",
    },
}

FAMILY_VOCAB: Dict[str, str] = {
    "정인": "가족의 정서적 지지를 받아들이는 구조",
    "편인": "가족과는 다른, 자기만의 방식으로 거리를 두는 구조",
    "정재": "가정의 경제적 책임을 맡아가는 구조",
    "편재": "가족을 위해 여러 방면으로 기회를 넓히는 구조",
}

SIBLINGS_VOCAB: Dict[str, str] = {
    "비견": "대등한 위치에서 협력하는 관계 구조",
    "겁재": "경쟁하거나 비교당하는 관계 구조",
}

FRIENDSHIP_VOCAB: Dict[str, str] = {
    "비견": "서로 대등하게 협력하는 관계 구조",
    "겁재": "경쟁심이나 주도권 다툼이 섞인 관계 구조",
    "식신": "느긋하고 편안하게 어울리는 관계 구조",
    "상관": "표현이 두드러지며 주목받는 관계 구조",
}

RELATIONSHIP_VOCAB: Dict[str, str] = {
    "정관": "관계에서의 책임과 약속을 중요하게 여기는 구조",
    "편관": "긴장감이나 강렬한 감정이 오가는 구조",
    "정재": "현실적인 조건을 함께 고려하는 구조",
    "편재": "폭넓은 만남 속에서 인연을 찾는 구조",
    "식신": "편안하고 꾸준한 애정을 쌓아가는 구조",
    "상관": "감정 표현이 솔직하고 두드러지는 구조",
}

MARRIAGE_VOCAB: Dict[str, str] = {
    "정관": "관계를 공식화하고 책임을 분담하는 현실적 구조",
    "편관": "관계에 큰 변화나 결단이 요구되는 구조",
    "정재": "생활 기반과 현실 조건을 함께 다지는 구조",
    "편재": "관계의 폭을 넓히며 현실적 선택지를 살피는 구조",
}

SELF_VOCAB: Dict[str, str] = {
    "비견": "동료와 나란히 서며 자립심을 키우는 구조",
    "겁재": "스스로 판을 주도하며 독립성을 키우는 구조",
}

STUDY_VOCAB: Dict[str, str] = {
    "정인": "체계적으로 배우고 인정받는 구조",
    "편인": "좁고 깊게 파고드는 전문 학습 구조",
}

# 영역별 valence 종결 어휘 — "사주 전체 균형" 같은 전역 문구를 재사용하지 않고
# 영역마다 다른 말로 쓴다(사용자 명시 금지: 영역별 부담 문구를 전역에서 복붙).
_VALENCE_CLOSING: Dict[str, Dict[str, str]] = {
    "자아_성장": {
        "favorable": "이 시기의 독립적인 움직임이 실제로 힘이 되는 흐름입니다.",
        "neutral": "이 흐름이 뚜렷하게 힘들지도 편하지도 않게 흘러가는 시기입니다.",
        "unfavorable": "이 시기의 독립적인 움직임이 뜻대로 풀리지 않아 버겁게 느껴질 수 있는 흐름입니다.",
    },
    "학업_전문성": {
        "favorable": "이 시기의 배움이 순조롭게 실력으로 이어지는 흐름입니다.",
        "neutral": "이 흐름은 배움의 속도를 특별히 밀거나 늦추지 않는 시기입니다.",
        "unfavorable": "이 시기의 배움이 뜻대로 되지 않아 답답하게 느껴질 수 있는 흐름입니다.",
    },
    "직업_사회": {
        "favorable": "이 역할이 실제로 인정과 성과로 이어지기 쉬운 흐름입니다.",
        "neutral": "이 역할이 특별히 순조롭지도 힘들지도 않게 흘러가는 시기입니다.",
        "unfavorable": "이 역할을 감당하는 것이 버겁게 느껴질 수 있는 흐름입니다.",
    },
    "재물": {
        "favorable": "이 재정 구조가 실제로 순조롭게 풀리기 쉬운 흐름입니다.",
        "neutral": "이 재정 구조가 특별히 좋지도 나쁘지도 않게 흘러가는 시기입니다.",
        "unfavorable": "이 재정 구조를 관리하는 것이 부담스럽게 느껴질 수 있는 흐름입니다.",
    },
    "가족_부모": {
        "favorable": "이 가족 구조가 순탄하게 느껴지기 쉬운 흐름입니다.",
        "neutral": "이 가족 구조가 특별한 굴곡 없이 흘러가는 시기입니다.",
        "unfavorable": "이 가족 구조를 감당하는 것이 버겁게 느껴질 수 있는 흐름입니다.",
    },
    "형제자매": {
        "favorable": "이 관계 구조가 순탄하게 느껴지기 쉬운 흐름입니다.",
        "neutral": "이 관계 구조가 특별한 부침 없이 흘러가는 시기입니다.",
        "unfavorable": "이 관계 구조에서 부딪히거나 비교당하는 느낌이 들 수 있는 흐름입니다.",
    },
    "친구_인간관계": {
        "favorable": "이 관계 구조가 편안하게 느껴지기 쉬운 흐름입니다.",
        "neutral": "이 관계 구조가 특별한 부침 없이 흘러가는 시기입니다.",
        "unfavorable": "이 관계 구조에서 쉽게 지치거나 위축될 수 있는 흐름입니다.",
    },
    "애정_연애": {
        "favorable": "이 관계 구조가 순조롭게 풀리기 쉬운 흐름입니다.",
        "neutral": "이 관계 구조가 특별히 밀어붙이지도 막지도 않는 시기입니다.",
        "unfavorable": "이 관계 구조를 이어가는 것이 쉽지 않게 느껴질 수 있는 흐름입니다.",
    },
    "결혼_배우자": {
        "favorable": "이 현실적 구조가 순조롭게 자리 잡기 쉬운 흐름입니다.",
        "neutral": "이 현실적 구조가 특별히 서두르거나 미뤄지지 않는 시기입니다.",
        "unfavorable": "이 현실적 구조를 다져가는 것이 쉽지 않게 느껴질 수 있는 흐름입니다.",
    },
}


def _confidence_elaboration(gan_matched: bool, ji_matched: bool, relation_matched: bool) -> str:
    """"driver 하나=결론 하나" 금지(사용자 명시) — confidence가 high(신호 2개 이상)일 때만
    "왜 뚜렷한지"를 실제 근거 조합에서 그대로 조립해 덧붙인다. 도메인×십신 하드코딩이
    아니라 evidence 구성 자체에서 동적으로 만든다."""
    if gan_matched and ji_matched:
        basis = "대운 천간과 지지가 함께"
    elif relation_matched and (gan_matched or ji_matched):
        basis = "대운 간지와 원국의 관계가 함께"
    else:
        basis = "여러 근거가 함께"
    return f"{basis} 이 방향을 가리키고 있어, 이 흐름이 비교적 뚜렷하게 나타날 수 있습니다."


def _build_sentence(domain_label: str, manifestation_phrase: str, valence: str, confidence: str,
                     gan_matched: bool, ji_matched: bool, relation_matched: bool) -> str:
    eun_neun = _josa(domain_label, "은", "는")
    manifest_josa = _josa(manifestation_phrase, "이", "가")
    core = f"{domain_label}{eun_neun} {manifestation_phrase}{manifest_josa} 나타나는 흐름입니다."
    closing = _VALENCE_CLOSING.get(domain_label_to_key(domain_label), {}).get(valence, "")
    parts = [core]
    if closing:
        parts.append(closing)
    if confidence == "high":
        parts.append(_confidence_elaboration(gan_matched, ji_matched, relation_matched))
    return " ".join(parts)


def domain_label_to_key(label: str) -> str:
    for key, defn in DOMAIN_DEFINITIONS.items():
        if defn["label"] == label:
            return key
    return ""


# ============================================================================
# 영역 정의 — groups(주로 반응하는 십신군, 사용자 지정대로 영역별 "중점"에 맞게
# 확장됨), palace(대운 지지와의 관계를 볼 원국 기둥), stages(생애단계 게이트),
# vocab_fn(ctx, sipsin) -> 이 영역만의 현실 언어 문구.
# ============================================================================
def _career_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return CAREER_VOCAB.get(sipsin)


def _wealth_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    bucket = _wealth_stage_bucket(ctx.life_stage)
    return WEALTH_VOCAB.get(bucket, {}).get(sipsin)


def _family_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return FAMILY_VOCAB.get(sipsin)


def _siblings_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    base = SIBLINGS_VOCAB.get(sipsin)
    if not base:
        return None
    return f"{_relation_label(ctx.life_stage)}와(과) {base}"


def _friendship_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    base = FRIENDSHIP_VOCAB.get(sipsin)
    if not base:
        return None
    return f"{_relation_label(ctx.life_stage)}와(과) {base}"


def _relationship_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return RELATIONSHIP_VOCAB.get(sipsin)


def _marriage_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return MARRIAGE_VOCAB.get(sipsin)


def _self_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return SELF_VOCAB.get(sipsin)


def _study_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return STUDY_VOCAB.get(sipsin)


DOMAIN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "자아_성장": {
        "label": "자아/성장", "groups": frozenset({"비겁"}), "palace": "day",
        "stages": frozenset(LIFE_STAGE_ORDER), "vocab_fn": _self_vocab, "dynamic_spouse": False,
    },
    "학업_전문성": {
        "label": "학업/전문성", "groups": frozenset({"인성"}), "palace": "month",
        "stages": frozenset(LIFE_STAGE_ORDER), "vocab_fn": _study_vocab, "dynamic_spouse": False,
    },
    "직업_사회": {
        # 사용자 지정 "중점": 관성/식상/재성/인성/비겁 — 5개 그룹 전부(=career는 어느
        # 십신이 와도 어떤 형태로든 반응한다는 의미, 대신 번역되는 "역할의 성격"이 다르다).
        "label": "직업/사회", "groups": frozenset({"관성", "식상", "재성", "인성", "비겁"}), "palace": "month",
        "stages": frozenset({"청소년", "청년", "성인"}), "vocab_fn": _career_vocab, "dynamic_spouse": False,
    },
    "재물": {
        "label": "재물", "groups": frozenset({"재성", "식상", "비겁"}), "palace": "month",
        "stages": frozenset({"청소년", "청년", "성인"}), "vocab_fn": _wealth_vocab, "dynamic_spouse": False,
    },
    "가족_부모": {
        "label": "가족/부모", "groups": frozenset({"인성", "재성"}), "palace": "month",
        "stages": frozenset(LIFE_STAGE_ORDER), "vocab_fn": _family_vocab, "dynamic_spouse": False,
    },
    "형제자매": {
        "label": "형제자매", "groups": frozenset({"비겁"}), "palace": "month",
        "stages": frozenset(LIFE_STAGE_ORDER), "vocab_fn": _siblings_vocab, "dynamic_spouse": False,
    },
    "친구_인간관계": {
        "label": "친구/인간관계", "groups": frozenset({"비겁", "식상"}), "palace": "year",
        "stages": frozenset(LIFE_STAGE_ORDER), "vocab_fn": _friendship_vocab, "dynamic_spouse": False,
    },
    "애정_연애": {
        "label": "애정/연애", "groups": frozenset({"식상"}), "palace": "day",
        "stages": frozenset({"청소년", "청년", "성인"}), "vocab_fn": _relationship_vocab, "dynamic_spouse": True,
    },
    "결혼_배우자": {
        "label": "결혼/배우자", "groups": frozenset(), "palace": "day",
        "stages": frozenset({"청년", "성인"}), "vocab_fn": _marriage_vocab, "dynamic_spouse": True,
    },
}
DOMAIN_ORDER: List[str] = list(DOMAIN_DEFINITIONS.keys())


# ============================================================================
# 공통 analyzer 엔진 — 9개 analyze_*() 공개 함수는 이 함수를 domain_key 하나로
# 호출하는 얇은 래퍼다. 점수식(activation)과 evidence 조립은 동일한 구조를 쓰되,
# 영역마다 다른 groups/palace/vocab_fn/stages 설정으로 실제 결과가 갈린다 — "영역별
# 독립 분석"이 "복붙된 점수식"이 아니라 "다른 입력 축 + 다른 어휘"로 구현되어 있다.
# ============================================================================
def _analyze_domain(ctx: DaewoonContext, domain_key: str) -> Dict[str, Any]:
    defn = DOMAIN_DEFINITIONS[domain_key]
    groups = set(defn["groups"])
    if defn["dynamic_spouse"]:
        groups.add(ctx.spouse_group)

    daewoon = ctx.daewoon
    ganji = daewoon.get("ganji", "")
    gan_char = ganji[0] if ganji else ""
    ji_char = ganji[1] if len(ganji) > 1 else ""
    gan_group, ji_group = daewoon.get("gan_group", ""), daewoon.get("ji_group", "")
    gan_sipsin, ji_sipsin = daewoon.get("gan_sipsin", ""), daewoon.get("ji_sipsin", "")
    gan_elem, ji_elem = daewoon.get("gan_elem", ""), daewoon.get("ji_elem", "")

    gan_matched = bool(gan_group) and gan_group in groups
    ji_matched = bool(ji_group) and ji_group in groups
    base = (2 if gan_matched else 0) + (1 if ji_matched else 0)

    palace = defn["palace"]
    relation = (daewoon.get("relations") or {}).get(palace, "무관")
    relation_key = _relation_key(relation)
    relation_raw = _RELATION_IMPACT.get(relation_key, 0)
    relation_matched = relation_raw > 0
    relation_bonus = relation_raw if base > 0 else min(relation_raw, 1)

    stage = ctx.life_stage
    is_child_focus = domain_key in CHILD_FOCUS_DOMAINS
    is_adult_focus = domain_key in ADULT_FOCUS_DOMAINS
    age_focus = (
        (stage in ("아동", "청소년") and is_child_focus)
        or (stage in ("청년", "성인") and is_adult_focus)
    )

    activation = max(0, min(5, base + relation_bonus + (1 if age_focus else 0)))

    if gan_matched:
        driving_sipsin, driving_elem = gan_sipsin, gan_elem
    elif ji_matched:
        driving_sipsin, driving_elem = ji_sipsin, ji_elem
    else:
        driving_sipsin, driving_elem = gan_sipsin, gan_elem  # 저영역 폴백(노출 안 됨)

    valence = resolve_polarity_for_elem(driving_elem, ctx.strength)

    signal_count = int(gan_matched) + int(ji_matched) + int(relation_matched)
    confidence = "high" if signal_count >= 2 else ("medium" if signal_count == 1 else "low")

    drivers: List[str] = []
    evidence: List[Dict[str, str]] = []
    if gan_matched:
        drivers.append(f"대운 천간 {gan_sipsin}({gan_group})")
        evidence.append({"source": "daewoon_gan", "factor": gan_char, "role": gan_sipsin})
    if ji_matched:
        drivers.append(f"대운 지지 {ji_sipsin}({ji_group})")
        evidence.append({"source": "daewoon_ji", "factor": ji_char, "role": ji_sipsin})
    if defn["dynamic_spouse"] and (gan_group == ctx.spouse_group or ji_group == ctx.spouse_group):
        drivers.append(f"배우자성({ctx.spouse_group})")
        evidence.append({"source": "spouse_star", "factor": ctx.spouse_group, "role": "배우자성"})
    if relation_matched:
        drivers.append(f"{_PALACE_LABEL.get(palace, palace)}와(과)의 {relation}")
        evidence.append({"source": f"daewoon_vs_{palace}", "factor": relation, "role": _PALACE_LABEL.get(palace, palace)})
    if age_focus:
        drivers.append(f"{stage} 생애단계 가중")
        evidence.append({"source": "life_stage", "factor": stage, "role": "연령대 가중"})

    vocab_fn: Callable[[DaewoonContext, str], Optional[str]] = defn["vocab_fn"]
    manifestation_phrase = vocab_fn(ctx, driving_sipsin) or f"{driving_sipsin} 기운이 작용하는 구조"
    label = defn["label"]
    sentence = _build_sentence(label, manifestation_phrase, valence, confidence, gan_matched, ji_matched, relation_matched)

    return {
        "domain": domain_key,
        "label": label,
        "activation": activation,
        "valence": valence,
        "confidence": confidence,
        "drivers": drivers,
        "evidence": evidence,
        "manifestation": [manifestation_phrase, {"favorable": "순한 흐름", "neutral": "무난한 흐름", "unfavorable": "부담스러운 흐름"}[valence]],
        "sentence": sentence,
    }


CHILD_FOCUS_DOMAINS = frozenset({"자아_성장", "학업_전문성", "가족_부모", "친구_인간관계"})
ADULT_FOCUS_DOMAINS = frozenset({"직업_사회", "재물", "애정_연애", "결혼_배우자"})


def analyze_self(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "자아_성장")


def analyze_study(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "학업_전문성")


def analyze_career(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "직업_사회")


def analyze_wealth(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "재물")


def analyze_family(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "가족_부모")


def analyze_siblings(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "형제자매")


def analyze_friendship(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "친구_인간관계")


def analyze_relationship(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "애정_연애")


def analyze_marriage(ctx: DaewoonContext) -> Dict[str, Any]:
    return _analyze_domain(ctx, "결혼_배우자")


_ANALYZERS: Dict[str, Callable[[DaewoonContext], Dict[str, Any]]] = {
    "자아_성장": analyze_self,
    "학업_전문성": analyze_study,
    "직업_사회": analyze_career,
    "재물": analyze_wealth,
    "가족_부모": analyze_family,
    "형제자매": analyze_siblings,
    "친구_인간관계": analyze_friendship,
    "애정_연애": analyze_relationship,
    "결혼_배우자": analyze_marriage,
}


# ============================================================================
# global_context — "사주 전체 균형" 판단은 여기서 "딱 한 번만" 서술한다(사용자 명시:
# 영역마다 자동 append 금지, 필요하면 총평에서 한 번). 영역별 valence 문구
# (_VALENCE_CLOSING)와는 다른 축 — 이건 대운 "천간" 전체의 억부 희기(기존
# analyze_daewoon_stage의 polarity)를 근거로 삼는다.
# ============================================================================
_GLOBAL_CONTEXT_TEMPLATE: Dict[str, str] = {
    "favorable": "이 사람은 {verdict} 사주인데, 이번 대운의 기운이 전체 균형에 순하게 힘을 보태는 방향이라 전반적으로 흐름을 타기 쉬운 10년입니다.",
    "unfavorable": "이 사람은 {verdict} 사주인데, 이번 대운의 기운이 전체 균형에는 부담을 더하는 방향이라 전반적으로 애쓴 만큼 결과가 따라오지 않거나 버겁게 느껴질 수 있는 10년입니다.",
    "neutral": "이 사람은 {verdict} 사주인데, 이번 대운의 기운이 전체 균형에 뚜렷하게 쏠리지 않아 무난하게 흘러갈 수 있는 10년입니다.",
}

# 대운 지지가 원국 4기둥 중 어디와 가장 강하게 관계를 맺는지 — 같은 사람의 두 대운이
# 천간 오행(gan_elem)까지 우연히 같아도(戊/己=토), 원국과의 합충형파해 관계는 서로
# 다를 수 있다(실측: 1983-05-14 여성의 戊午는 시주와 육합, 己未는 시주와 복음). 이
# 관계를 global_context에 한 구절 더해 "대운-원국 상호작용"을 전체 총평 수준에서도
# 반영한다(사용자 지정 섹션 4·10).
_RELATION_GLOBAL_NOTE: Dict[str, str] = {
    "육합": "조화롭게 이어지는", "충": "크게 흔들리는", "형": "마찰이 생기는",
    "파": "어긋나는", "해": "방해받는", "복음": "그대로 반복되는", "자형": "내적으로 부딪히는",
}


def _strongest_relation(relations: Dict[str, str]) -> Optional[tuple]:
    best: Optional[tuple] = None
    best_impact = 0
    for palace in ("year", "month", "day", "hour"):
        relation = relations.get(palace, "무관")
        key = _relation_key(relation)
        impact = _RELATION_IMPACT.get(key, 0)
        if impact > best_impact:
            best_impact, best = impact, (palace, key)
    return best


def _build_global_context(natal: Dict[str, Any], daewoon: Dict[str, Any]) -> str:
    verdict = natal.get("strength_verdict", "중화")
    template = _GLOBAL_CONTEXT_TEMPLATE.get(daewoon.get("polarity", "neutral"), _GLOBAL_CONTEXT_TEMPLATE["neutral"])
    sentence = template.format(verdict=verdict)
    strongest = _strongest_relation(daewoon.get("relations") or {})
    if strongest:
        palace, relation_key = strongest
        note = _RELATION_GLOBAL_NOTE.get(relation_key)
        if note:
            sentence += f" 특히 {_PALACE_LABEL.get(palace, palace)}와(과) {note} 흐름이 두드러집니다."
    return sentence


def _build_narrative(meaningful: List[Dict[str, Any]]) -> str:
    if not meaningful:
        return "이 10년은 어느 한 영역에 크게 치우치기보다 전반적으로 무난하게 흘러갈 수 있는 시기입니다."
    ordered = sorted(meaningful, key=lambda d: -d["activation"])
    labels = ", ".join(d["label"] for d in ordered)
    intro = f"이 10년은 {labels} 영역에서 변화가 가장 두드러지게 나타날 수 있는 시기입니다."
    detail = " ".join(d["sentence"] for d in ordered)
    return f"{intro} {detail}"


def build_domain_pipeline(
    saju: Dict[str, Any], fact: Dict[str, Any], age: int, gender: str, debug: bool = False,
) -> Dict[str, Any]:
    """엔진 전체 실행. saju=calculate_saju 산출물, fact=daewoon_step_facts()의 선택된
    단계 하나, age=이 대운을 보는 기준 나이, gender=원국 성별.

    debug=False(기본): 생애단계 게이트를 통과한 영역만 analyzer를 호출하고(section 13
    "분석 전에 적용"), 그중 activation>=KEY_AREA_MIN_SCORE인 것만 domain_scores에
    담는다 — 나머지는 완전히 생략(문구조차 없음).
    debug=True: 9개 영역 전부를 계산해 debug_all_domains에 담는다(eligible/미달 여부
    포함, 내부 검증용).
    """
    strength = saju.get("strength") or {}
    natal = analyze_natal_stage(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    stage = life_stage(age)
    ctx = DaewoonContext(natal=natal, daewoon=daewoon, life_stage=stage, gender=gender, strength=strength)

    eligible = get_eligible_domains(age)
    keys_to_analyze = DOMAIN_ORDER if debug else [k for k in DOMAIN_ORDER if k in eligible]

    results: List[Dict[str, Any]] = []
    for key in keys_to_analyze:
        r = _ANALYZERS[key](ctx)
        r["eligible"] = key in eligible
        results.append(r)

    meaningful = [r for r in results if r["eligible"] and r["activation"] >= KEY_AREA_MIN_SCORE]
    meaningful.sort(key=lambda r: -r["activation"])
    global_context = _build_global_context(natal, daewoon)

    output: Dict[str, Any] = {
        "natal_summary": natal,
        "daewoon_summary": daewoon,
        "life_stage": stage,
        "global_context": global_context,
        "domain_scores": meaningful,
        "narrative": _build_narrative(meaningful),
    }
    if debug:
        output["debug_all_domains"] = results
    return output
