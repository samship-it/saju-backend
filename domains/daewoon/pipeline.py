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


def _stage_bucket(stage: str) -> str:
    """모든 domain의 life_stage 번역이 공통으로 쓰는 3단계 버킷(미성년=아동+청소년/
    청년/성인). 원래 재물 영역 전용이었으나(STEP2 정책 확정: "life_stage는 특정
    domain 하나에만 적용되는 기능이 아니라 전체 domain의 공통 해석 계층") 9개 영역
    전부가 이 표준 버킷을 공유하도록 일반화했다(2026-09-21 STEP3)."""
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
#
# STEP3(2026-09-21) — life_stage 공통 해석 계층 확장: 9개 영역 전부 {미성년,청년,성인}
# 3버킷(_stage_bucket) 구조로 통일했다. 단순히 "아동/청년/성인" 단어만 바꾼 게 아니라,
# 같은 십신이라도 생애단계마다 실제로 다른 현실 현상으로 번역된다(예: 정관+직업 —
# 미성년="학교·집단의 규칙/책임", 청년="조직의 기준·절차를 따르는 역할",
# 성인="관리·의사결정을 맡는 확대된 책임"). 우선순위(1순위: 직업/재물/애정/결혼,
# 2순위: 가족/친구/학업, 3순위: 자아/형제) 전부 이번에 완료.
# ============================================================================
CAREER_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "비견": "또래와 대등하게 역할을 나누며 규칙을 배우는 구조",
        # STEP9-C(2026-09-22): SELF×겁재에서 이미 고친 "주도성/독립성" 표현이 CAREER
        # 겁재 3단계에도 그대로 남아있었다(STEP9-C 감사, TARGET 불명확). 학교 과제·
        # 조직 방식·상급자 방침이라는 직업다운 구체 대상을 부여해 SELF와 겹치지
        # 않게 했다(자기계발·생활방식 자체는 SELF 영역이므로 배제).
        "겁재": "정해진 역할 분담에 따르지 않고 자기 방식대로 학교 과제나 활동을 맡아 해보려는 구조",
        "식신": "꾸준한 활동으로 인정받는 학교생활 구조",
        "상관": "자기표현으로 존재감을 드러내는 학교생활 구조",
        "정재": "정해진 기준을 착실히 채워가는 학습 구조",
        "편재": "정해진 역할 외에 새로운 임무를 맡아보는 학교생활 구조",
        "정관": "규칙을 따르고 책임을 배우는 학교·집단 구조",
        "편관": "힘든 규율이나 경쟁 속에서 단련되는 구조",
        # STEP9-C(2026-09-22): CAREER×정인 미성년이 STUDY×정인 미성년과 조사 하나만
        # 다른 사실상 동일 문장이었다(직업↔학업 domain 간 정보 반복, STEP9-C 감사).
        # 직업은 "업무 방식을 어른에게서 익힌다"로, 학업은 "교과 내용을 이해한다"로
        # 현실 대상을 분리했다.
        "정인": "맡은 역할을 수행할 때 선배나 담당 어른이 알려주는 방식을 그대로 따라 하며 업무 감각을 익히는 구조",
        "편인": "자기만의 방식으로 특정 분야에 몰입하는 구조",
    },
    "청년": {
        "비견": "동료와 대등한 위치에서 역할을 나눠 맡는 구조",
        "겁재": "조직에서 정해준 방식보다 자신의 방법으로 업무를 처리하려 하며 새로운 역할을 자청하는 구조",
        "식신": "꾸준한 실무 능력으로 평가받는 역할 구조",
        "상관": "새로운 방식이나 아이디어로 존재감을 드러내는 역할 구조",
        "정재": "정해진 성과 기준을 착실히 채워가는 역할 구조",
        "편재": "맡는 업무 범위가 새롭게 늘어나는 역할 구조",
        "정관": "조직이 요구하는 기준과 절차를 따르는 역할 구조",
        "편관": "책임이 무겁거나 압박이 큰 자리를 맡는 역할 구조",
        "정인": "자격이나 전문성으로 인정받는 역할 구조",
        "편인": "특수한 기술이나 전문 영역으로 평가받는 역할 구조",
    },
    "성인": {
        "비견": "동료들과 맡은 업무를 나누어 책임지며 조직 내 자리를 지키는 구조",
        "겁재": "조직의 관행이나 상급자의 방침과 다르더라도 자기 판단으로 업무 방향을 밀어붙이는 구조",
        "식신": "오랜 경험을 바탕으로 안정적으로 실무를 이끄는 구조",
        "상관": "새로운 방향을 제시하며 조직에 영향을 미치는 구조",
        "정재": "쌓아온 성과를 바탕으로 신뢰받는 자리를 지키는 구조",
        "편재": "다른 부서나 프로젝트까지 아울러 맡는 일이 늘어나는 구조",
        "정관": "조직 내 책임이 확대되며 관리와 의사결정을 맡는 구조",
        "편관": "무거운 책임과 위기 상황을 감당하는 관리자 구조",
        "정인": "쌓은 전문성으로 조직의 기준을 세우는 구조",
        "편인": "쌓아온 전문성을 조직의 까다로운 문제 해결에 활용하는 구조",
    },
}

# 재물: 미성년=용돈/청년=수입·지출·자산형성/성인=자산관리·생활안정.
WEALTH_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "정재": "용돈을 계획적으로 관리하는 태도",
        "편재": "정해진 용돈 범위를 넘어 지출이 늘어나는 소비 태도",
        "식신": "좋아하는 것에 꾸준히 용돈을 쓰는 태도",
        "상관": "갖고 싶은 게 생기면 바로 쓰고 싶어하는 소비 태도",
        "비견": "친구와 나눠 쓰는 데 아낌없는 소비 태도",
        "겁재": "자기 뜻대로 쓰고 싶어하는 소비 태도",
    },
    "청년": {
        "정재": "고정적인 수입을 착실히 쌓아가는 재정 구조",
        "편재": "정기 수입 외에 부수입이 새로 생기는 재정 구조",
        "식신": "꾸준한 활동으로 수입을 만들어가는 재정 구조",
        "상관": "새로운 방식으로 수입원을 만들어가는 재정 구조",
        "비견": "동료와 함께 벌고 나누는 재정 구조",
        "겁재": "스스로의 힘으로 벌어들이는 재정 구조",
    },
    "성인": {
        "정재": "이미 쌓은 자산을 안정적으로 관리하는 구조",
        "편재": "정기 소득 외에 투자나 부수입으로 자산을 불려가는 구조",
        "식신": "꾸준한 활동을 자산으로 전환해가는 구조",
        "상관": "새로운 방식으로 자산을 불려가는 구조",
        "비견": "동료와 자산을 함께 관리하거나 나누는 구조",
        "겁재": "스스로 판단해 자산을 운용하는 구조",
    },
}

FAMILY_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        # STEP8-C(2026-09-21): 청년 항목과 "그대로"만 빠진 사실상 동일 문장이었다(MEDIUM,
        # STEP8-A 감사). 미성년=부모의 보호·가르침을 일상 전반에서 그대로 따르는 피동적
        # 관계 / 청년=그 가족 자원을 진학·독립 과정에서 스스로 참고하는 반주도적 관계로
        # 실제 역할이 달라지게 다시 썼다.
        "정인": "부모님의 보살핌과 가르침을 일상 전반에서 그대로 따르는 구조",
        # STEP9-B: 미성년/청년이 완전 동일 문자열이었다(STEP9-A 감사에서 새로 발견,
        # 어느 STEP에서도 편인은 다루지 않았던 사각지대). 단순 명사 교체 대신 미성년=
        # 관심사를 고집하며 혼자만의 시간을 갖는 소극적 거리 / 청년=진학·생활방식을
        # 가족과 다르게 선택하며 만드는 적극적 거리로 실제 행동이 다르게 다시 썼다.
        # 성인 항목은 "거리를 두면서도 챙긴다"는 균형 상태라 이미 둘과 구분되어 유지.
        "편인": "가족과는 다른 자기만의 관심사를 고집하며 혼자만의 시간을 갖는 구조",
        "정재": "부모님이 챙겨주는 살림 안에서 지내는 구조",
        "편재": "부모님께 새로운 것을 배우거나 체험하게 해달라고 조르는 구조",
    },
    "청년": {
        "정인": "진학이나 독립을 준비하며 가족의 조언과 정보를 참고하게 되는 구조",
        "편인": "진학이나 생활 방식을 가족과 다르게 선택하며 독립된 거리를 만들어가는 구조",
        "정재": "가정의 경제적 책임을 맡아가는 구조",
        "편재": "가족의 생활비나 살림에 필요한 것들을 새로 챙기게 되는 구조",
    },
    "성인": {
        "정인": "부모 세대를 이해하고 정서적으로 지지하는 구조",
        "편인": "가족과 거리를 두면서도 자기만의 방식으로 챙기는 구조",
        "정재": "부모님이나 가족의 생활비를 책임지고 챙기는 구조",
        "편재": "부모님이나 가족에게 예상치 못한 지출을 지원하게 되는 구조",
    },
}

# STEP6-1(2026-09-21): 형제자매 vs 친구_인간관계 manifestation 중복 수정. 두 domain
# 모두 groups={비겁}(친구는 +식상)을 공유해 비견/겁재가 뜨면 거의 항상 동시 활성화되는데,
# 기존에는 SIBLINGS_VOCAB도 _relation_label(또래/동료/네트워크)을 공유 prefix로 썼기
# 때문에(친구와 동일 prefix) 비견/겁재 본문까지 비슷한 어휘로 겹쳐 사실상 같은 문장이
# 나왔다(실측: 庚申/辛酉 샘플, STEP6 감사 보고). 형제자매는 "가족/혈연/성장환경" 맥락이
# 반드시 드러나야 하므로 아래부터는 _relation_label 공유 prefix를 쓰지 않고(아래
# _siblings_vocab 참고) 문장 자체에 "형제자매"를 직접 명시하는 완결형 문구로 바꿨다.
SIBLINGS_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "비견": "형제자매와 비슷한 위치에서 역할을 나누며 자라는 구조",
        # STEP10(2026-09-22): "비교당하거나...다투는"이 core 자체에 부정적 결과를
        # 확정해, favorable valence closing("무리 없이 오갈 수 있습니다")과 결합하면
        # 논리적으로 충돌했다(STEP10 감사). 경쟁/분배라는 현실 축은 유지하되, 확정적
        # 갈등 대신 "나누는 방식이 서로 다르게 자리잡는다"는 valence-중립 서술로 바꿔
        # favorable/unfavorable 어느 쪽 closing과도 자연스럽게 결합하게 했다.
        "겁재": "형제자매끼리 물건이나 공간, 역할을 나누는 방식이 각자 다르게 자리잡는 구조",
    },
    "청년": {
        "비견": "독립한 뒤에도 형제자매와 대등하게 오가며 지내는 구조",
        "겁재": "독립 이후 형제자매와 생활비나 거주 공간 같은 부담을 나누는 방식을 새로 정하게 되는 구조",
    },
    "성인": {
        "비견": "형제자매와 부모 부양이나 대소사를 함께 나누어 짊어지는 구조",
        "겁재": "부모 부양이나 집안 대소사가 생기면 형제자매 중 누가 얼마나 맡을지 각자 목소리를 내며 정해가는 구조",
    },
}

# 친구_인간관계는 SIBLINGS와 달리 여전히 _relation_label(또래/동료/네트워크) prefix를
# 쓴다(이 단어 자체가 "사회적 관계망" 맥락이라 이 domain에는 그대로 맞음) — 비견/겁재
# 본문만 "새로운 인연/집단/교류/네트워크 확장" 쪽으로 다시 써서 형제자매(가족/혈연)와
# 겹치지 않게 했다. 식신/상관은 이번 중복과 무관해 그대로 유지(SIBLINGS_VOCAB에는
# 애초에 식신/상관 항목이 없다 — 형제자매 domain groups={비겁}뿐이라 겹칠 일이 없음).
# STEP8-C(2026-09-21): 비견 항목이 미성년/청년/성인 내내 "폭/넓히다/교류"만 반복해
# 강도만 다른 동일 사건(관계망 확장)으로 읽혔다(HIGH, STEP8-A 감사). "친구→인맥→네트워크"
# 명사만 바뀌는 대신, 그 나이대에 실제로 "관계를 맺는 방식" 자체가 다르게 다시 썼다 —
# 미성년=주어진 또래집단에 피동적으로 섞여듦 / 청년=새 집단에 스스로 들어가 관계를
# 직접 만듦(능동) / 성인=기존 관계를 추리고 필요한 인연만 골라 들임(선별). 이 함수의
# 문구는 _friendship_vocab()에서 "또래/동료/네트워크와(과) " prefix가 앞에 붙는다.
FRIENDSHIP_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "비견": "정해진 무리 안에 자연스럽게 섞여드는 구조",
        # STEP10(2026-09-22): "신경전이 벌어지는"/"경쟁이 이어지는"이 core 자체에
        # 부정적 사건을 확정해, favorable valence closing("부담 없이 편안하게
        # 넓어집니다")과 결합하면 논리적으로 충돌했다(STEP10 감사, 겁재×친구/형제자매
        # 27건 중 13건에서 확인). 주도권·역할 배분이라는 현실 축은 유지하되, 확정적
        # 갈등 대신 "의견을 내세운다/자리를 조정한다"는 valence-중립 서술로 바꿨다.
        "겁재": "또래 무리 안에서 역할이나 주도권을 놓고 서로 다른 의견을 내세우는 구조",
        "식신": "같은 모임이나 무리 안에서 부담 없이 어울리는 구조",
        # STEP9-B: 미성년/청년이 완전 동일 문자열이었다(STEP9-A 감사, 어느 STEP에서도
        # 상관은 다루지 않았던 사각지대). "주목받는다"는 결과 서술 대신 "표현 방식→관계
        # 형성 방식"이 단계별로 달라지게 다시 썼다 — 미성년=학교·또래 모임에서 말/표현
        # 으로 존재감을 키움 / 청년=동아리·온라인 커뮤니티에서 의견·콘텐츠로 새로 연결됨
        # / 성인=직장 밖 커뮤니티에서 의견·전문성이 관계 안에서 영향력을 가짐.
        "상관": "학교나 동아리 모임에서 말과 표현으로 존재감이 커지는 구조",
    },
    "청년": {
        "비견": "새로운 곳에 들어가 관계를 직접 만들어가는 구조",
        "겁재": "소속 모임이나 커뮤니티에서 주도권과 참여 방식을 새로 조율하게 되는 구조",
        "식신": "같은 모임 활동을 이어가며 동료와 편하게 어울리는 구조",
        "상관": "동아리나 온라인 커뮤니티에서 의견이나 콘텐츠로 새롭게 연결되는 구조",
    },
    "성인": {
        "비견": "유지할 관계를 추리고 필요한 인연만 새로 들이는 구조",
        "겁재": "오랜 모임 안에서 주도권을 놓고 새로 들어온 사람들과 자리를 조정해가는 구조",
        "식신": "오래된 모임이나 커뮤니티에서 꾸준히 얼굴을 마주하는 구조",
        "상관": "직장 밖 커뮤니티에서 자신의 의견이나 전문성이 관계 안에서 영향력을 발휘하는 구조",
    },
}

RELATIONSHIP_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "정관": "좋아하는 사람 앞에서도 예의와 규칙을 지키려는 구조",
        # STEP9-C(2026-09-22): 편관 미성년/청년이 "강렬한 감정이 오가는"을 반복했다
        # (STEP9-C 감사). 미성년=짝사랑 같은 감정 자체의 동요 / 청년=실제 만남에서
        # 책임·거리를 조율하는 현실적 국면으로 분리했다(결혼 domain의 "결혼 여부
        # 판단"과 겹치지 않도록 연애 단계에 한정).
        "편관": "짝사랑 같은 강한 호감이 갑자기 찾아와 마음이 크게 흔들리는 구조",
        "정재": "상대의 마음을 있는 그대로 헤아리려는 구조",
        "편재": "친구 무리 안에서 호감이 오가는 구조",
        "식신": "편안하게 마음을 나누는 풋풋한 구조",
        # STEP9-C(2026-09-22): 상관 3단계가 "솔직한 감정표현"만 반복하고 TARGET이
        # 불명확했다(STEP9-C 감사). 미성년=좋아하는 사람 앞에서 감정을 드러내는 행동 /
        # 청년=새 만남에서 취향·의견을 드러내는 행동 / 성인=기존 관계에서 요구를
        # 표현해 방향을 조정하는 행동으로 각각 다른 현실 장면을 부여했다.
        "상관": "좋아하는 사람 앞에서 감정을 숨기지 않고 바로 드러내 관계의 분위기를 이끄는 구조",
    },
    "청년": {
        # STEP8-C(2026-09-21): 성인 항목과 "책임을 중요시/지킨다"로 사실상 동일했다
        # (MEDIUM, STEP8-A 감사). 청년=아직 관계 진입 전, 상대를 볼 때 책임감을 판단
        # 기준으로 삼는 "선택"의 순간 / 성인=이미 만나는 상대와 책임을 나누며 관계를
        # 운영하는 단계로 실제 국면이 다르게 다시 썼다.
        "정관": "연애 상대를 볼 때 약속과 책임감을 기준으로 판단하게 되는 구조",
        "편관": "실제 만남을 이어가면서 서로의 책임과 거리를 어디까지 둘지 조율해야 하는 긴장이 생기는 구조",
        "정재": "현실적인 조건을 함께 고려하는 구조",
        "편재": "새로운 사람과의 만남이 이어지며 호감이 오가는 구조",
        "식신": "자주 연락하고 만나며 편안한 호감을 쌓아가는 구조",
        "상관": "새로 만나는 사람 앞에서 자신의 취향과 의견을 적극적으로 드러내며 호감을 만들어가는 구조",
    },
    "성인": {
        "정관": "만나고 있는 상대와 서로의 책임과 역할을 맞춰가며 관계를 현실적으로 운영하는 구조",
        "편관": "관계에서 큰 감정의 동요나 시험이 찾아오는 구조",
        "정재": "마음이 잘 맞는 상대와 편안하게 가까워지는 구조",
        "편재": "일상 밖에서 만나는 사람들 중 마음이 가는 상대를 눈여겨보게 되는 구조",
        "식신": "익숙해진 상대와 편안한 애정을 주고받는 구조",
        "상관": "만나고 있는 상대에게 서운함이나 원하는 바를 직접 말해 관계의 방향을 조정해가는 구조",
    },
}

MARRIAGE_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {
        "정관": "관계를 진지하게 여기며 책임을 미리 생각해보는 구조",
        "편관": "관계에 대한 부담이나 두려움이 큰 구조",
        "정재": "안정적인 미래를 막연히 그려보는 구조",
        "편재": "여러 가능성을 열어두고 미래를 그리는 구조",
    },
    "청년": {
        "정관": "관계를 공식화하고 책임을 분담하는 현실적 구조",
        # STEP9-C(2026-09-22): 청년/성인이 "큰/굵직한 변화나 결단"만 명사를 바꿔
        # 반복했다(STEP9-C 감사). 청년=결혼 여부·관계 지속을 놓고 아직 결정하지
        # 못한 상태 / 성인=이미 꾸린 결혼생활 안에서 역할·생활방식을 조정하는
        # 상태로 국면을 분리했다.
        "편관": "결혼을 할지 말지, 혹은 지금 만나는 사람과 계속 갈지를 현실적으로 판단해야 하는 구조",
        "정재": "함께 살 준비를 하며 가사와 생활비를 어떻게 나눌지 구체화하는 구조",
        "편재": "결혼 이후 생활 방식이나 거주지를 놓고 새로운 대안을 살펴보는 구조",
    },
    "성인": {
        "정관": "가정을 안정적으로 지키며 책임을 다하는 구조",
        "편관": "이미 꾸린 결혼생활 안에서 역할 분담이나 생활 방식을 다시 조정해야 하는 상황이 찾아오는 구조",
        "정재": "배우자와 정해진 가사와 생활 역할을 꾸준히 지켜가는 구조",
        "편재": "배우자와 함께 집안일뿐 아니라 목돈 지출 같은 굵직한 문제도 새로 분담하는 구조",
    },
}

# STEP9-B(2026-09-21): 겁재 3단계+비견 성인이 "독립성/주도성/판단"이라는 내부 태도만
# 서술해 현실 대상이 없다는 문제가 STEP9-A 감사에서 확인됐다(TOP10 개선후보 1~4위).
# 재물/직업/애정 영역을 침범하지 않는 범위에서 "태도→선택 대상→행동"으로 구체화했다 —
# 겁재는 미성년(하고 싶은 것을 고집)→청년(진학·생활방식 등 구체적 선택을 스스로 결정)
# →성인(생활 전반을 자기 판단으로 조정)으로 실제 변화 단계가 드러나게, 비견 성인은
# "협력적으로 안정을 이끄는" 겁재와 대비되는 성격을 살려 자기계발/시간 활용이라는
# 구체 대상을 추가했다.
SELF_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {"비견": "친구들과 비슷한 결정을 내리면서도 내 방식을 조금씩 고집해보는 구조", "겁재": "하고 싶은 활동이나 생활 방식을 스스로 정하려고 고집하는 구조"},
    "청년": {"비견": "다른 사람 기준이 아니라 내가 정한 기준으로 진로나 선택을 정하는 구조", "겁재": "진학이나 생활 방식처럼 중요한 선택을 스스로 정하려는 구조"},
    "성인": {"비견": "자기계발이나 시간 활용의 우선순위를 스스로 정해 생활을 이끌어가는 구조", "겁재": "주변 기준보다 자신의 판단에 따라 생활 방식과 중요한 선택을 조정하는 구조"},
}

# STEP9-C(2026-09-22): 정인 미성년이 CAREER×정인 미성년과 거의 동일 문장이었고
# (위 CAREER_VOCAB 참고), 편인 미성년/청년이 "좁고 깊게 파고드는"이라는 어구를
# 명사만 바꿔 반복했다(STEP9-C 감사). 정인은 "교과 학습" 대상으로, 편인은
# 미성년=정규 수업 밖 개인 탐색 / 청년=전공·진로 선택 시점으로 재구성했다.
STUDY_VOCAB: Dict[str, Dict[str, str]] = {
    "미성년": {"정인": "수업이나 교과 내용을 선생님의 설명대로 받아들이며 이해를 넓혀가는 구조", "편인": "정규 수업과 별개로 스스로 흥미를 느낀 분야를 혼자 파고들어 알아가는 구조"},
    "청년": {"정인": "체계적으로 배우고 인정받는 구조", "편인": "전공이나 진로를 정할 때 남들이 가지 않는 자신만의 관심 분야를 선택해 파고드는 구조"},
    "성인": {"정인": "쌓아온 전문성을 나누고 인정받는 구조", "편인": "특정 분야를 남들보다 깊이 파고들며 지식을 쌓아가는 구조"},
}

# 영역별 valence 종결 어휘(STEP8-B 재설계, 2026-09-21) — "사주 전체 균형" 같은 전역
# 문구를 재사용하지 않는다는 원래 원칙은 유지하되, STEP8-A 감사에서 확인된 두 가지
# 문제를 근본적으로 고친다.
# 1. WHAT 반복 금지: closing이 manifestation의 명사("...하는 구조")를 다시 언급하지
#    않는다 — 대신 그 domain의 "무엇의 HOW인지"(판단/선택, 학습/습득, 조직/책임,
#    자산/수입, 가족지원, 형제자매 간 거리/역할, 교류/인맥, 호감/감정, 공동생활/배우자
#    역할)만 말한다. _build_sentence()의 core가 더 이상 "~흐름입니다"로 끝나지 않으므로
#    (아래 참고) closing도 전부 "~흐름입니다"로 끝낼 필요가 없어졌다 — 문장 종결어를
#    domain·valence마다 다르게 써서 "구조/흐름" 기계적 반복을 끊는다.
# 2. domain 간 접미부 재사용 금지: 27개 항목 중 어느 것도 서로 동일한 문장 또는 동일한
#    결말 어구를 공유하지 않는다(특히 형제자매↔친구_인간관계는 이전에 neutral이 완전
#    동일했던 항목이라 셋 다 별도로 설계).
_VALENCE_CLOSING: Dict[str, Dict[str, str]] = {
    "자아_성장": {
        "favorable": "이 시기의 판단과 선택이 실제로 좋은 결과로 이어지기 쉽습니다.",
        "neutral": "이 시기의 판단과 선택은 서두르지도 미루지도 않고 천천히 자리를 잡아갑니다.",
        "unfavorable": "이 시기의 판단과 선택이 뜻대로 되지 않아 스스로 버거움을 느낄 수 있습니다.",
    },
    "학업_전문성": {
        "favorable": "이 시기의 배움과 습득이 순조롭게 실력으로 쌓여갑니다.",
        "neutral": "이 시기의 배움과 습득은 유난히 빨라지지도 더뎌지지도 않습니다.",
        "unfavorable": "이 시기의 배움과 습득이 뜻대로 풀리지 않아 답답함을 느낄 수 있습니다.",
    },
    "직업_사회": {
        "favorable": "이 시기의 역할과 책임이 눈에 띄는 성과로 드러나기 쉽습니다.",
        "neutral": "이 시기의 역할과 책임은 특별히 힘들지도 수월하지도 않게 흘러갑니다.",
        "unfavorable": "이 시기의 역할과 책임에 예상보다 큰 부담이 실릴 수 있습니다.",
    },
    "재물": {
        "favorable": "이 시기의 자산과 수입 관리가 비교적 순조롭게 풀립니다.",
        "neutral": "이 시기의 자산과 수입 관리는 특별히 좋아지지도 나빠지지도 않습니다.",
        "unfavorable": "이 시기의 자산과 수입을 관리하는 데 부담이 붙기 쉽습니다.",
    },
    "가족_부모": {
        "favorable": "이 시기의 가족 지원과 역할 분담이 큰 갈등 없이 자리를 잡습니다.",
        "neutral": "이 시기의 가족 지원과 역할 분담은 특별한 굴곡 없이 지나갑니다.",
        "unfavorable": "이 시기의 가족 지원과 역할 분담이 버겁게 느껴질 수 있습니다.",
    },
    "형제자매": {
        "favorable": "이 시기 형제자매 사이의 거리와 역할이 무리 없이 오갈 수 있습니다.",
        "neutral": "이 시기 형제자매 사이의 거리와 역할은 특별한 사건 없이 지금 상태를 유지합니다.",
        "unfavorable": "이 시기 형제자매 사이에서 비교당하거나 부딪히는 느낌이 들 수 있습니다.",
    },
    "친구_인간관계": {
        "favorable": "이 시기의 교류와 인맥이 부담 없이 편안하게 넓어집니다.",
        "neutral": "이 시기의 교류와 인맥은 눈에 띄는 굴곡 없이 꾸준히 지속됩니다.",
        "unfavorable": "이 시기의 교류와 인맥 관리에서 쉽게 지치거나 위축될 수 있습니다.",
    },
    "애정_연애": {
        "favorable": "이 시기의 호감과 감정 교류가 순조롭게 무르익습니다.",
        "neutral": "이 시기의 호감과 감정 교류는 서두르지도 막히지도 않습니다.",
        "unfavorable": "이 시기의 호감과 감정 교류를 이어가는 일이 쉽지 않게 느껴질 수 있습니다.",
    },
    "결혼_배우자": {
        "favorable": "이 시기의 공동생활과 배우자 역할이 순조롭게 틀을 잡아갑니다.",
        "neutral": "이 시기의 공동생활과 배우자 역할은 서두르거나 미뤄지지 않고 제자리를 지킵니다.",
        "unfavorable": "이 시기의 공동생활과 배우자 역할을 다지는 데 여러 변수가 끼어들 수 있습니다.",
    },
}


# STEP8-B: confidence 부연이 9개 domain 전부 완전히 동일한 문구였던 문제(STEP8-A
# 감사에서 확인)를 고친다 — evidence 조합(gan+ji/relation+하나/기타)에 따른 3가지
# "근거" 어휘는 그대로 유지하되(새 WHAT을 만들지 않는다는 원칙 유지), 어느 domain의
# 신호인지 나타내는 영역어를 덧붙여 동일 대운에서 여러 domain이 동시에 high-confidence로
# 뜨더라도 부연 문장이 카드마다 그대로 반복되지 않게 한다. 영역어는 _VALENCE_CLOSING과
# 동일한 "무엇의 HOW인지" 명사를 재사용해 새 사건을 추가하지 않는다.
_CONFIDENCE_AREA_LABEL: Dict[str, str] = {
    "자아_성장": "판단과 선택",
    "학업_전문성": "배움과 습득",
    "직업_사회": "역할과 책임",
    "재물": "자산과 수입",
    "가족_부모": "가족 지원과 역할",
    "형제자매": "형제자매 사이의 거리와 역할",
    "친구_인간관계": "교류와 인맥",
    "애정_연애": "호감과 감정 교류",
    "결혼_배우자": "공동생활과 배우자 역할",
}


def _confidence_elaboration(domain_key: str, gan_matched: bool, ji_matched: bool, relation_matched: bool) -> str:
    """"driver 하나=결론 하나" 금지(사용자 명시) — confidence가 high(신호 2개 이상)일 때만
    "왜 뚜렷한지"를 실제 근거 조합에서 그대로 조립해 덧붙인다. 도메인×십신 하드코딩이
    아니라 evidence 구성 자체에서 동적으로 만든다. 새로운 사건/예측은 추가하지 않고
    오직 "신호의 선명도"만 domain별 영역어로 설명한다(STEP8-B)."""
    if gan_matched and ji_matched:
        basis = "대운 천간과 지지가 함께"
    elif relation_matched and (gan_matched or ji_matched):
        basis = "대운 간지와 원국의 관계가 함께"
    else:
        basis = "여러 근거가 함께"
    area = _CONFIDENCE_AREA_LABEL.get(domain_key, "이 영역")
    return f"{basis} {area} 쪽 신호를 가리키고 있어, 이 변화가 비교적 뚜렷하게 나타날 수 있습니다."


# STEP8-B: core 문장이 항상 "~구조가 나타나는 흐름입니다"로 끝나던 고정 골격을 고친다
# — manifestation(*_VOCAB)이 이미 "...하는 구조"로 끝나는데 그 뒤에 "~흐름입니다"까지
# 붙이면, closing도 "~흐름입니다"로 끝나는 domain(6/9)에서 "구조"·"흐름입니다"가 한
# 문단 안에 각 2회씩 반복됐다(STEP8-A 감사 실측 확인). core는 manifestation의 WHAT을
# 그대로 보존한 채 "나타납니다"로 짧게 끝내고, "그 시기 체감이 어떤지"(HOW)는 오직
# closing이 전담한다 — closing 쪽은 이제 domain마다 다른 종결어를 쓰므로(위 참고)
# "~흐름입니다" 반복도 함께 해소된다.
def _build_sentence(domain_key: str, domain_label: str, manifestation_phrase: str, valence: str, confidence: str,
                     gan_matched: bool, ji_matched: bool, relation_matched: bool) -> str:
    eun_neun = _josa(domain_label, "은", "는")
    manifest_josa = _josa(manifestation_phrase, "이", "가")
    core = f"{domain_label}{eun_neun} {manifestation_phrase}{manifest_josa} 나타납니다."
    closing = _VALENCE_CLOSING.get(domain_key, {}).get(valence, "")
    parts = [core]
    if closing:
        parts.append(closing)
    if confidence == "high":
        parts.append(_confidence_elaboration(domain_key, gan_matched, ji_matched, relation_matched))
    return " ".join(parts)


# 5분류 안전망(STEP3 정책 항목5) — *_VOCAB에 이 십신 항목이 없을 때만(주로 activation
# 이 낮아 base=0인 영역) 쓰는 최후의 fallback. 십신 10종별 정적 문장을 새로 늘리는 게
# 아니라 5개짜리 일반 문구 하나로 묶어 "정적 문장 계속 늘리는 것 금지" 원칙을 지킨다.
_GROUP_FALLBACK_MANIFESTATION: Dict[str, str] = {
    "비겁": "주변과의 관계 속에서 은은하게 작용하는 구조",
    "식상": "활동과 표현 속에서 은은하게 작용하는 구조",
    "재성": "자원과 성과 속에서 은은하게 작용하는 구조",
    "관성": "책임과 역할 속에서 은은하게 작용하는 구조",
    "인성": "지원과 배움 속에서 은은하게 작용하는 구조",
}


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
    return CAREER_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _wealth_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return WEALTH_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _family_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return FAMILY_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _siblings_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    # STEP6-1: 더 이상 _relation_label(또래/동료/네트워크)을 붙이지 않는다 — 그 prefix가
    # 친구_인간관계와 동일해 중복의 원인이었다. SIBLINGS_VOCAB 문구 자체가 "형제자매"를
    # 직접 명시하는 완결형 문장이라 그대로 반환한다.
    return SIBLINGS_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _friendship_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    base = FRIENDSHIP_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)
    if not base:
        return None
    return f"{_relation_label(ctx.life_stage)}와(과) {base}"


def _relationship_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return RELATIONSHIP_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _marriage_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return MARRIAGE_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _self_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return SELF_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


def _study_vocab(ctx: "DaewoonContext", sipsin: str) -> Optional[str]:
    return STUDY_VOCAB.get(_stage_bucket(ctx.life_stage), {}).get(sipsin)


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
        driving_sipsin, driving_elem, driving_group = gan_sipsin, gan_elem, gan_group
    elif ji_matched:
        driving_sipsin, driving_elem, driving_group = ji_sipsin, ji_elem, ji_group
    else:
        # base=0(이 영역의 groups와 실제 매치가 없음) — activation은 낮게 유지되고
        # (KEY_AREA_MIN_SCORE 미만이라 domain_scores에 노출 안 됨), manifestation도
        # 아래에서 *_VOCAB이 아니라 5분류 안전망(_GROUP_FALLBACK_MANIFESTATION)을
        # 쓴다. gan_elem을 그대로 쓰는 건 "대운 천간" 자체가 이 대운의 기본 배경
        # 오행이라 완전히 근거 없는 값은 아니지만, STEP2 정책 확정대로 이 valence는
        # "이 영역의 실질적 판단"으로 취급하지 않는다(디버그 전용).
        driving_sipsin, driving_elem, driving_group = gan_sipsin, gan_elem, gan_group

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
    # STEP3 정책 항목5: *_VOCAB에 없는 십신이 원문 그대로 노출되던 fallback
    # (`f"{driving_sipsin} 기운이 작용하는 구조"`)을 제거하고, 5분류 그룹 수준의
    # 일반 안전망으로 교체한다 — 십신별 정적 문장을 새로 늘리지 않으면서도(원칙 §3)
    # 명리 용어(십신명)가 사용자 문장에 그대로 새지 않도록 막는다.
    manifestation_phrase = vocab_fn(ctx, driving_sipsin) or _GROUP_FALLBACK_MANIFESTATION.get(
        driving_group, "이 사람의 기운이 은은하게 작용하는 구조"
    )
    label = defn["label"]
    sentence = _build_sentence(domain_key, label, manifestation_phrase, valence, confidence, gan_matched, ji_matched, relation_matched)

    return {
        "domain": domain_key,
        "label": label,
        # eligible/life_stage(2026-09-21 3차 개편 STEP1 신규): 이전엔 build_domain_pipeline()
        # 호출부가 사후에 덧붙였다(비-debug 경로에서는 게이트 통과 영역만 애초에 analyzer가
        # 호출돼 eligible을 못 붙이는 경우도 있었음). 이제 _analyze_domain() 자체가 매번
        # 채워 넣어서, 어떤 경로로 호출되든(단위 테스트에서 analyze_career() 등을 직접
        # 불러도) 표준 구조가 항상 동일하게 나온다.
        "eligible": ctx.life_stage in DOMAIN_DEFINITIONS[domain_key]["stages"],
        "life_stage": ctx.life_stage,
        "activation": activation,
        # driving_sipsin/driving_group(STEP5-A 신규): driving_sipsin=구체적 십신(10종),
        # driving_group=그 십신이 속한 5분류. manifestation은 이미 driving_sipsin으로
        # vocab_fn을 조회해 왔지만(내부 변수), 필드로 노출된 적은 없었다 — additive 추가.
        "driving_sipsin": driving_sipsin,
        "driving_group": driving_group,
        # specificity(STEP5-A 신규): 1/len(scope) — activation 계산에는 전혀 관여하지
        # 않고(STEP4-C~E에서 반복 검증됨), priority tier 내부의 표시 순서 전용으로만
        # 쓰인다(아래 _assign_priority_tiers 참고). scope는 dynamic_spouse가 있으면
        # 이미 배우자성이 더해진 실제 런타임 집합 크기를 쓴다(애정_연애=2, 결혼_배우자=1).
        "specificity": round(1 / len(groups), 3) if groups else 0.0,
        # is_primary(STEP3 정책 §1): activation>=KEY_AREA_MIN_SCORE(3)인 것만 "주요 운세
        # 콘텐츠"로 취급한다 — 그 미만은 계산은 유지하되 valence/manifestation/sentence를
        # "이 영역의 실질적 판단"으로 해석하지 않는다(매치 없이 대운 천간으로 계산된
        # fallback valence이기 쉬움). build_domain_pipeline()의 domain_scores는 이 값이
        # True인 것만 담는다 — debug_all_domains에서는 False인 것도 그대로 확인 가능.
        "is_primary": activation >= KEY_AREA_MIN_SCORE,
        # source(STEP3 정책 §3, OPTION2): 이 결과가 domain_pipeline에서 나왔는지 표시.
        # 현재는 이 함수가 항상 성공하므로 "domain_pipeline" 고정값만 나온다 —
        # "legacy_fallback"은 향후 domain_pipeline 계산이 실패하거나 필수 필드가
        # 누락됐을 때 content.py 결과로 대체하는 상위 오케스트레이션 레이어가 생기면
        # 그쪽에서 채워 넣을 예약된 값이다(이번 STEP3에서는 그 레이어를 만들지 않음).
        "source": "domain_pipeline",
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


# ============================================================================
# Priority tier(STEP5-A 신규, STEP4-D~E 시뮬레이션에서 확정한 정책 그대로 구현) —
# activation 공식은 전혀 바꾸지 않고(Formula D=현재 그대로), "여러 domain이 동시에
# 활성화된 대운에서 무엇을 먼저 보여줄지"만 이 함수가 결정한다.
#
# 규칙(STEP4-E에서 실측 검증됨):
# 1. is_primary(activation>=KEY_AREA_MIN_SCORE)면서 eligible한 domain만 대상.
# 2. 이 대운에서 나온 activation 값들을 내림차순으로 정렬해 "band"를 만든다
#    (예: 5,5,4,3 -> band는 [5,4,3] 3개).
# 3. 최고 band(전부) = primary. 그 다음 band(전부) = secondary. 나머지 = supporting.
#    **동일 band에 속한 domain은 몇 개든 전부 같은 tier**(임의로 하나만 고르지 않음).
# 4. confidence는 tier 결정에 전혀 관여하지 않는다(필드로만 보존).
# 5. specificity(1/len(scope))는 tier를 절대 바꾸지 않고, **같은 tier 내부의 표시
#    순서**에만 쓴다(activation이 다르면 specificity가 아무리 커도 역전 불가 —
#    band가 애초에 activation 값으로만 나뉘므로 구조적으로 역전이 불가능하다).
# 6. activation·confidence·specificity가 완전히 동일한 completely-tied domain은
#    같은 tier 안에 공동으로 남긴다 — dict 순서·선언 순서·문자열 순서 같은 임의의
#    4번째 기준을 쓰지 않는다(표시 순서만 DOMAIN_ORDER를 stable-sort 최종 tiebreak로
#    쓰는데, 이건 "우선순위를 결정하는 의미론적 기준"이 아니라 단순 표시 안정성용).
# ============================================================================
_PRIORITY_TIER_RANK = {"primary": 0, "secondary": 1, "supporting": 2}


def _assign_priority_tiers(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """entries: is_primary=True(eligible+activation>=3)인 domain 결과 리스트. 각
    entry에 "priority_tier"를 채워 넣고, tier -> activation DESC -> specificity DESC
    -> (원래 순서, DOMAIN_ORDER 기반 stable) 순으로 정렬한 새 리스트를 반환한다."""
    if not entries:
        return []
    bands = sorted({e["activation"] for e in entries}, reverse=True)
    tier_of_band = {}
    if len(bands) >= 1:
        tier_of_band[bands[0]] = "primary"
    if len(bands) >= 2:
        tier_of_band[bands[1]] = "secondary"
    for b in bands[2:]:
        tier_of_band[b] = "supporting"

    for e in entries:
        e["priority_tier"] = tier_of_band[e["activation"]]

    original_index = {key: i for i, key in enumerate(DOMAIN_ORDER)}
    ordered = sorted(
        entries,
        key=lambda e: (
            _PRIORITY_TIER_RANK[e["priority_tier"]],
            -e["activation"],
            -e["specificity"],
            original_index.get(e["domain"], 0),
        ),
    )
    return ordered


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

    # eligible/life_stage는 이제 _analyze_domain() 자체가 채워 넣으므로(STEP1 개편) 여기서
    # 다시 덧씌울 필요가 없다 — get_eligible_domains(age)는 keys_to_analyze를 고르는 데만 쓴다.
    results: List[Dict[str, Any]] = [_ANALYZERS[key](ctx) for key in keys_to_analyze]

    # is_primary(activation>=3)는 기존 그대로 유지(하위호환, STEP5-A §10) — "activation
    # threshold를 넘었는가"라는 의미. priority_tier(_assign_priority_tiers)는 그중에서
    # "여러 활성 domain 중 어느 tier인가"를 결정하는 새로운 source of truth다.
    meaningful = [r for r in results if r["eligible"] and r["is_primary"]]
    meaningful = _assign_priority_tiers(meaningful)
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
