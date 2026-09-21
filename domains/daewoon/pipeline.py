"""10년 대운 7단계 해석 파이프라인(2026-09-21 신규 → 2026-09-21 전면 재설계 v2).

사용자 지정 구조:
1. [원국 분석] 일간·오행 균형·신강/신약·원국 십신 구성
2. [대운 분석] 대운 천간/지지 십신·오행, 원국과의 합/충/형/파/해, 전체 오행 균형 영향
3. [영역별 영향 분석] 9개 영역(자아/성장·학업/전문성·직업/사회·재물·가족/부모·형제자매·
   친구/인간관계·애정/연애·결혼/배우자)에 대운이 어떤 십신군·관계로 걸리는지 매핑
4. [영역별 영향도 계산] activation 0(직접 영향 없음)~5(매우 강함) + valence(그 영역
   기준 고유 희기)·confidence(신호 개수)·drivers(근거)·manifestation_types(양상 범주)
5. [고영역(3~5점) 구체 해석] 십신 화두 + 영역별 valence 톤을 반영한 문장
6. [저영역(0~2점)·생애단계 부적합 영역 완전 비노출] "변화 없음" 문구조차 만들지 않고
   응답에서 통째로 제외한다(v2 변경점 — v1은 저영역을 고정 문구로 "간소화"만 했지만,
   사용자가 "저영역 문구는 전면 비노출"로 재지정했다).
7. [자연어 출력 합성] 5·6단계 결과(=보이는 영역만)를 하나의 문단(narrative)으로 합성.

**v1→v2 변경 이유(2026-09-21 재설계)**:
- (버그) v1은 모든 영역의 톤(polarity)에 "대운 천간" 하나의 희기값을 그대로 복사해
  썼다 — 사용자가 지적한 "십신 키워드가 모든 영역에 일률 복사되던 프롬프트 구조"의
  정확한 원인. v2는 영역마다 "그 영역을 실제로 움직이는 요소"(대운 천간일 수도, 지지일
  수도 있음)의 오행만 넣어 valence를 독립적으로 계산한다(content.resolve_polarity_for_elem).
- (요구사항) 저영향 영역은 고정 문구로도 노출하지 않고 아예 목록에서 제외한다.
- (요구사항) 생애 단계(아동/청소년/청년/성인) 필터 — 예: 8~17세(아동~청소년)에는
  결혼/배우자 영역 자체가 목록에 나타나지 않는다(활성도 점수와 무관하게 하드 게이트).
- (요구사항) 각 영역 항목에 activation/valence/confidence/drivers/manifestation_types를
  구조화된 필드로 노출 — "각 영역에 필요한 사주 요소를 별도 분석"했다는 근거를 그대로
  드러낸다.

기존 domain_analysis(career_or_study/wealth_flow/relationship/family 등, content.py)를
대체하지 않는다 — 이 파이프라인은 9개 영역에 걸친 영향도 지도 + 종합 서사라는 층을
추가하는 것이고, domain_analysis는 여전히 4~8개 영역의 상세 문단을 담당한다.

Anti-prediction 원칙(daewoon/content.py와 동일): "~할 것이다"처럼 특정 사건을 단정하는
표현은 쓰지 않고, "~가능성이 있습니다/높습니다"류의 완곡한 표현만 쓴다. 십신 하나를 특정
사건 하나에 1:1로 매핑하지 않고(예: "정관=반장"), 화두(변화 영역)와 양상 범주
(manifestation_types)까지만 제시한다.
"""
from typing import Any, Dict, List, Optional

from core.constants import GAN_ELEM, JI_ELEM
from core.daewoon import branch_relation
from domains.daewoon.content import SIPSIN_CHANGE_AREA, _josa, resolve_polarity_for_elem

# 5분류 십신군 — content.py의 GROUPS와 동일 순서(단일 소스 유지 목적, import는 하지 않고
# 값만 맞춰 둔다 — content.py를 건드리지 않기 위해 상수는 독립적으로 정의).
GROUPS: List[str] = ["비겁", "식상", "재성", "관성", "인성"]

# 연령대 기준 — service.py의 CHILD_AGE_THRESHOLD(20)와 값을 맞춘다(단일 소스는 별도
# 상수라 어긋나면 테스트가 잡아준다. test_daewoon_pipeline.py에서 동치 검증).
CHILD_AGE_THRESHOLD = 20

# 사용자 지정 연령대별 가중 영역(activation 계산용, 생애단계 게이트와는 다른 축).
CHILD_FOCUS_DOMAINS = frozenset({"자아_성장", "학업_전문성", "가족_부모", "친구_인간관계"})
ADULT_FOCUS_DOMAINS = frozenset({"직업_사회", "재물", "애정_연애", "결혼_배우자"})

# 고/저영역 분기 임계값 — 3점 이상만 "핵심 영역"으로 최종 노출한다.
KEY_AREA_MIN_SCORE = 3

# 대운 지지 vs 원국 각 기둥 지지의 관계 강도 — 육합(조화·활성화)과 충(강한 충돌)은 그
# 자체로 "변화가 크다"는 신호라 둘 다 최고 강도로 취급한다(방향의 좋고 나쁨은 valence가
# 별도로 담당하고, 여기서는 순수하게 "영향의 크기"만 잰다).
_RELATION_IMPACT: Dict[str, int] = {
    "육합": 2, "충": 2, "형": 1, "파": 1, "해": 1, "복음": 1, "자형": 1, "무관": 0,
}

# 관계 종류 → 양상 범주(manifestation type). 십신-사건 1:1 매핑을 피하고 "어떤 결의
# 변화인지"만 범주로 제시한다.
_RELATION_MANIFESTATION: Dict[str, Optional[str]] = {
    "육합": "조화/결합", "충": "급격한 변화", "형": "마찰/조정", "파": "어긋남",
    "해": "방해/구설", "복음": "반복/누적", "자형": "내적 갈등", "무관": None,
}
# 십신군 → 양상 범주.
_GROUP_MANIFESTATION: Dict[str, str] = {
    "비겁": "관계/경쟁", "식상": "표현/활동", "재성": "확장/소비", "관성": "책임/압박", "인성": "지원/학습",
}

_PALACE_LABEL: Dict[str, str] = {"year": "년주", "month": "월주", "day": "일주", "hour": "시주"}


def _relation_key(relation: str) -> str:
    """branch_relation()의 '충(충돌·이동)' 같은 라벨을 위 표의 키로 정규화
    (daily/woon_modifier.py의 _relation_key()와 동일 로직, 단일 소스는 아니지만 동형 유지)."""
    r = relation or "무관"
    if r.startswith("복음"):
        return "자형" if "자형" in r else "복음"
    return r.split("(")[0] if "(" in r else r


def _is_female(gender: str) -> bool:
    return str(gender or "").strip().lower() in {"female", "f", "여", "여자", "여성"}


# ============================================================================
# 생애 단계(아동/청소년/청년/성인) — 영역별 노출 게이트 전용. service.py의
# CHILD_AGE_THRESHOLD(20, 아동+청소년 통합 vs 성인 2분류)와는 다른, 이 파이프라인만의
# 더 세분화된 4단계 축이다(사용자 지정: "생애 단계(아동/청소년/청년/성인) 필터링").
# ============================================================================
LIFE_STAGE_ORDER: List[str] = ["아동", "청소년", "청년", "성인"]
_LIFE_STAGE_BOUNDS = [(0, 12, "아동"), (13, 19, "청소년"), (20, 34, "청년")]


def life_stage(age: int) -> str:
    for lo, hi, name in _LIFE_STAGE_BOUNDS:
        if lo <= age <= hi:
            return name
    return "성인"


# 9개 영역 정의: groups(주로 반응하는 십신군), palace(원국 어느 기둥의 지지와 대운 지지의
# 관계를 볼지), stages(이 영역이 노출될 수 있는 생애 단계 — 여기 없으면 activation 점수와
# 무관하게 응답에서 완전히 제외된다). 애정/연애·결혼/배우자는 배우자성(성별에 따라
# 여=관성/남=재성, core.strength.spouse_star와 동일 규칙)을 score_domains()에서 동적으로
# 더한다 — groups는 그 외에 함께 반응하는 축만 담는다.
DOMAIN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "자아_성장": {
        "label": "자아/성장", "groups": frozenset({"비겁"}), "palace": "day",
        "stages": frozenset(LIFE_STAGE_ORDER),
    },
    "학업_전문성": {
        "label": "학업/전문성", "groups": frozenset({"인성"}), "palace": "month",
        "stages": frozenset(LIFE_STAGE_ORDER),
    },
    "직업_사회": {
        "label": "직업/사회", "groups": frozenset({"관성"}), "palace": "month",
        "stages": frozenset({"청소년", "청년", "성인"}),  # 아동기엔 사회적 역할 개념이 약함
    },
    "재물": {
        "label": "재물", "groups": frozenset({"재성"}), "palace": "month",
        "stages": frozenset({"청소년", "청년", "성인"}),  # 아동기 재물은 용돈 수준(다른 모듈)
    },
    "가족_부모": {
        "label": "가족/부모", "groups": frozenset({"인성", "재성"}), "palace": "month",
        "stages": frozenset(LIFE_STAGE_ORDER),
    },
    "형제자매": {
        "label": "형제자매", "groups": frozenset({"비겁"}), "palace": "month",
        "stages": frozenset(LIFE_STAGE_ORDER),
    },
    "친구_인간관계": {
        "label": "친구/인간관계", "groups": frozenset({"비겁", "식상"}), "palace": "year",
        "stages": frozenset(LIFE_STAGE_ORDER),
    },
    "애정_연애": {
        "label": "애정/연애", "groups": frozenset({"식상"}), "palace": "day",
        "stages": frozenset({"청소년", "청년", "성인"}),  # 아동기엔 노출 안 함
    },
    "결혼_배우자": {
        "label": "결혼/배우자", "groups": frozenset(), "palace": "day",
        "stages": frozenset({"청년", "성인"}),  # 아동·청소년(8~19세)엔 절대 노출 안 함(핵심 회귀)
    },
}
DOMAIN_ORDER: List[str] = list(DOMAIN_DEFINITIONS.keys())


# ============================================================================
# 1단계: 원국 분석
# ============================================================================
def analyze_natal_stage(saju: Dict[str, Any]) -> Dict[str, Any]:
    """saju(core.saju_base.calculate_saju 산출물) -> 일간/오행균형/신강신약/원국 십신 구성."""
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
    """saju + daewoon_step_facts()의 fact(하나) -> 대운 천간/지지 십신·오행, 원국 각 기둥과의
    합/충/형/파/해, 대운 "천간" 기준 억부 희기(polarity — decade_theme 등 기존 필드용으로
    유지), 전체 오행 균형에 미치는 영향(balance_shift)."""
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

    # 전체 오행 균형 영향: 이 대운의 천간/지지가 더해졌을 때 오행 세력 편차(최대-최소)가
    # 더 벌어지면(widens) 기존 신강/신약 경향이 심화되고, 좁아지면(narrows) 중화 쪽으로
    # 이동한다는 뜻 — core/strength.analyze_strength()가 이미 계산해 둔 elem_power(천간
    # 1.0 + 지장간 가중)를 그대로 재사용해 단일 소스를 유지한다.
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


# ============================================================================
# 3·4단계: 영역별 영향 분석 + 영향도(activation 0~5) + valence/confidence/drivers/
# manifestation_types — "영역별 독립 분석" 요구사항의 핵심. 십신 키워드나 톤을 모든
# 영역에 그대로 복사하지 않고, 영역마다 자신을 실제로 움직인 요소만 근거로 삼는다.
# ============================================================================
def score_domains(
    daewoon_stage: Dict[str, Any], age: int, gender: str, strength: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """9개 영역 각각의 영향도/톤/근거를 계산한다(생애단계 게이트는 여기서 적용하지
    않는다 — build_domain_pipeline()이 이 결과를 받아 노출 여부를 최종 결정한다).

    activation = base(대운 천간/지지 십신군이 이 영역의 groups에 속하면 각각 +2/+1)
               + relation_bonus(이 영역의 palace 기둥과 대운 지지의 합/충/형/파/해
                 강도, base가 0이면 절반만 반영 — palace가 여러 영역에 걸쳐 공유되므로
                 무관한 영역까지 관계만으로 부풀려지지 않게 하는 안전장치)
               + age_focus(연령대가 이 영역에 가중되면 +1)
               0~5로 클램프.
    valence  = "이 영역을 실제로 움직인 요소"(천간이 매치했으면 천간 오행, 아니면
               지지 오행)의 용신/기신 희기 — 영역마다 독립적으로 계산되므로 같은
               대운이라도 영역별로 톤이 달라질 수 있다(대운 천간 하나의 희기를
               모든 영역에 그대로 복사하던 v1 버그 수정).
    confidence = 근거 신호(천간 매치/지지 매치/관계) 개수 기준 "high"(2개 이상)/
               "medium"(1개)/"low"(0개).
    """
    spouse_group = "관성" if _is_female(gender) else "재성"
    gan_group = daewoon_stage.get("gan_group", "")
    ji_group = daewoon_stage.get("ji_group", "")
    gan_sipsin = daewoon_stage.get("gan_sipsin", "")
    ji_sipsin = daewoon_stage.get("ji_sipsin", "")
    gan_elem = daewoon_stage.get("gan_elem", "")
    ji_elem = daewoon_stage.get("ji_elem", "")
    relations = daewoon_stage.get("relations") or {}

    results: List[Dict[str, Any]] = []
    for key in DOMAIN_ORDER:
        defn = DOMAIN_DEFINITIONS[key]
        groups = set(defn["groups"])
        if key in ("애정_연애", "결혼_배우자"):
            groups.add(spouse_group)

        gan_matched = bool(gan_group) and gan_group in groups
        ji_matched = bool(ji_group) and ji_group in groups
        base = (2 if gan_matched else 0) + (1 if ji_matched else 0)

        palace = defn["palace"]
        relation = relations.get(palace, "무관")
        relation_key = _relation_key(relation)
        relation_raw = _RELATION_IMPACT.get(relation_key, 0)
        relation_matched = relation_raw > 0
        relation_bonus = relation_raw if base > 0 else min(relation_raw, 1)

        stage_now = life_stage(age)
        age_focus = (
            (age < CHILD_AGE_THRESHOLD and key in CHILD_FOCUS_DOMAINS)
            or (age >= CHILD_AGE_THRESHOLD and key in ADULT_FOCUS_DOMAINS)
        )

        score = base + relation_bonus + (1 if age_focus else 0)
        score = max(0, min(5, score))

        # 이 영역을 실제로 움직이는 십신/오행 — 천간이 매치하면 천간을, 아니면(지지만
        # 매치) 지지를 근거로 삼는다. 영역별 valence를 독립적으로 계산하는 핵심.
        if gan_matched:
            driving_sipsin, driving_elem = gan_sipsin, gan_elem
        elif ji_matched:
            driving_sipsin, driving_elem = ji_sipsin, ji_elem
        else:
            driving_sipsin, driving_elem = gan_sipsin, gan_elem  # 저영역 폴백(노출 안 됨)

        valence = resolve_polarity_for_elem(driving_elem, strength)

        signal_count = int(gan_matched) + int(ji_matched) + int(relation_matched)
        confidence = "high" if signal_count >= 2 else ("medium" if signal_count == 1 else "low")

        drivers: List[str] = []
        if gan_matched:
            drivers.append(f"대운 천간 {gan_sipsin}({gan_group})")
        if ji_matched:
            drivers.append(f"대운 지지 {ji_sipsin}({ji_group})")
        if key in ("애정_연애", "결혼_배우자") and (gan_group == spouse_group or ji_group == spouse_group):
            drivers.append(f"배우자성({spouse_group})")
        if relation_matched:
            drivers.append(f"{_PALACE_LABEL.get(palace, palace)}와(과)의 {relation}")
        if age_focus:
            drivers.append(f"{stage_now} 생애단계 가중")

        manifestation_types: List[str] = []
        group_manifest = _GROUP_MANIFESTATION.get(gan_group if gan_matched else ji_group if ji_matched else "")
        if group_manifest:
            manifestation_types.append(group_manifest)
        relation_manifest = _RELATION_MANIFESTATION.get(relation_key)
        if relation_manifest and relation_manifest not in manifestation_types:
            manifestation_types.append(relation_manifest)

        results.append({
            "domain": key,
            "label": defn["label"],
            "activation": score,
            "valence": valence,
            "confidence": confidence,
            "drivers": drivers,
            "manifestation_types": manifestation_types,
            "driving_sipsin": driving_sipsin,
            "stages": defn["stages"],
        })
    return results


# ============================================================================
# 5·6단계: 고영역 구체 해석 / 저영역·생애단계 부적합 영역 완전 비노출
# ============================================================================
_VALENCE_TONE: Dict[str, str] = {
    "favorable": "이 사람의 기운과 잘 맞아떨어지는 방향이라 순탄하게 느껴질 가능성이 높습니다",
    "unfavorable": "이 사람의 기운에는 부담을 더하는 방향이라 뜻대로 되지 않거나 힘겹게 느껴지는 순간이 있을 수 있습니다",
    "neutral": "뚜렷하게 한쪽으로 쏠리지 않고 무난하게 흘러갈 가능성이 있습니다",
}


def build_domain_sentence(entry: Dict[str, Any]) -> str:
    """5단계: entry(score_domains()의 항목 하나, 이미 고영역·생애단계 통과분만 들어옴)를
    문장으로 변환. 십신 화두(SIPSIN_CHANGE_AREA, decade_theme과 동일 표 재사용) + 이
    영역 고유의 valence 톤을 반영한다. 구체적 사건은 단정하지 않는다(anti-prediction)."""
    label = entry["label"]
    eun_neun = _josa(label, "은", "는")
    tone = _VALENCE_TONE.get(entry["valence"], _VALENCE_TONE["neutral"])
    change_area = SIPSIN_CHANGE_AREA.get(entry.get("driving_sipsin", ""), "")
    change_clause = ""
    if change_area:
        gwa_wa = _josa(change_area, "과", "와")
        change_clause = f" 특히 **{change_area}**{gwa_wa} 관련된 화두가 두드러질 수 있습니다."
    return f"{label}{eun_neun} 이번 대운에서 핵심적으로 영향을 받는 영역입니다.{change_clause} {tone}."


# ============================================================================
# 7단계: 자연어 출력 합성 — 보이는(=핵심 영역) 영역만으로 구성한다. 저영역·생애단계
# 부적합 영역은 "변화 없음"류 문구조차 만들지 않고 완전히 침묵한다(사용자 명시 요구:
# "영향도 낮은 영역의 '변화 없음' 문구는 전면 비노출").
# ============================================================================
def _build_narrative(domain_entries: List[Dict[str, Any]]) -> str:
    if not domain_entries:
        return "이 10년은 어느 한 영역에 크게 치우치기보다 전반적으로 무난하게 흘러갈 수 있는 시기입니다."
    ordered = sorted(domain_entries, key=lambda d: -d["activation"])
    labels = ", ".join(d["label"] for d in ordered)
    intro = f"이 10년은 {labels} 영역에서 변화가 가장 두드러지게 나타날 수 있는 시기입니다."
    detail = " ".join(d["sentence"] for d in ordered)
    return f"{intro} {detail}"


def build_domain_pipeline(
    saju: Dict[str, Any], fact: Dict[str, Any], age: int, gender: str,
) -> Dict[str, Any]:
    """7단계 파이프라인 전체 실행. saju=calculate_saju 산출물, fact=daewoon_step_facts()의
    선택된 단계 하나, age=이 대운을 보는 기준 나이(effective_age), gender=원국 성별.

    domain_scores에는 (1) activation>=KEY_AREA_MIN_SCORE(핵심 영역)이고 (2) 이 나이의
    생애 단계가 그 영역의 stages에 포함되는 항목만 담긴다 — 나머지는 완전히 제외된다
    (사용자 명시 요구, v1의 "저영역 간소화 고정 문구"를 대체).
    """
    strength = saju.get("strength") or {}
    natal = analyze_natal_stage(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    stage_now = life_stage(age)
    scored = score_domains(daewoon, age, gender, strength)

    domain_entries: List[Dict[str, Any]] = []
    for entry in scored:
        if entry["activation"] < KEY_AREA_MIN_SCORE:
            continue
        if stage_now not in entry["stages"]:
            continue
        sentence = build_domain_sentence(entry)
        domain_entries.append({
            "domain": entry["domain"],
            "label": entry["label"],
            "activation": entry["activation"],
            "valence": entry["valence"],
            "confidence": entry["confidence"],
            "drivers": entry["drivers"],
            "manifestation_types": entry["manifestation_types"],
            "sentence": sentence,
        })

    return {
        "natal_summary": natal,
        "daewoon_summary": daewoon,
        "life_stage": stage_now,
        "domain_scores": domain_entries,
        "narrative": _build_narrative(domain_entries),
    }
