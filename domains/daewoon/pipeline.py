"""10년 대운 7단계 해석 파이프라인(2026-09-21 신규, AI 호출 없음).

사용자 지정 구조:
1. [원국 분석] 일간·오행 균형·신강/신약·원국 십신 구성
2. [대운 분석] 대운 천간/지지 십신·오행, 원국과의 합/충/형/파/해, 전체 오행 균형 영향
3. [영역별 영향 분석] 9개 영역(자아/성장·학업/전문성·직업/사회·재물·가족/부모·형제자매·
   친구/인간관계·애정/연애·결혼/배우자)에 대운이 어떤 십신군·관계로 걸리는지 매핑
4. [영역별 영향도 계산] 0(직접 영향 없음)~5(매우 강함) 점수
5. [고영역(3~5점) 구체 해석] 십신 화두 + 억부 용신/기신 희기(polarity) 톤을 반영한 문장
6. [저영역(0~2점) 간소화] "상대적으로 핵심적인 변화 영역은 아니며, 기존 흐름이 유지됩니다"
7. [자연어 출력 합성] 5·6단계 결과를 하나의 문단(narrative)으로 합성 — "[10년의 풍경]"
   섹션(decade_theme 아래)과 요약 보조 정보로 쓰인다.

기존 domain_analysis(career_or_study/wealth_flow/relationship/family 등, content.py)를
대체하지 않는다 — 이 파이프라인은 "9개 영역에 걸친 영향도 지도 + 종합 서사"라는 새로운
층을 추가하는 것이고, domain_analysis는 여전히 4~8개 영역의 상세 문단을 담당한다.

Anti-prediction 원칙(daewoon/content.py와 동일): "~할 것이다"처럼 특정 사건을 단정하는
표현은 쓰지 않고, "~가능성이 있습니다/높습니다"류의 완곡한 표현만 쓴다.

억부 용신/기신 희기(polarity) 판정은 content.resolve_decade_polarity()를 그대로
재사용한다 — 단일 소스 유지(같은 사람의 같은 대운이 모듈마다 다른 희기로 계산되면 안 됨).
"""
from typing import Any, Dict, List, Optional

from core.constants import GAN_ELEM, JI_ELEM
from core.daewoon import branch_relation
from domains.daewoon.content import SIPSIN_CHANGE_AREA, _josa, resolve_decade_polarity

# 5분류 십신군 — content.py의 GROUPS와 동일 순서(단일 소스 유지 목적, import는 하지 않고
# 값만 맞춰 둔다 — content.py를 건드리지 않기 위해 상수는 독립적으로 정의).
GROUPS: List[str] = ["비겁", "식상", "재성", "관성", "인성"]

# 연령대 기준 — service.py의 CHILD_AGE_THRESHOLD(20)와 값을 맞춘다(단일 소스는 별도
# 상수라 어긋나면 테스트가 잡아준다. test_daewoon_pipeline.py에서 동치 검증).
CHILD_AGE_THRESHOLD = 20

# 사용자 지정 연령대별 가중 영역.
CHILD_FOCUS_DOMAINS = frozenset({"자아_성장", "학업_전문성", "가족_부모", "친구_인간관계"})
ADULT_FOCUS_DOMAINS = frozenset({"직업_사회", "재물", "애정_연애", "결혼_배우자"})

# 고/저영역 분기 임계값 — 3점 이상이면 "고영역"(구체 해석), 2점 이하면 "저영역"(간소화).
KEY_AREA_MIN_SCORE = 3

# 대운 지지 vs 원국 각 기둥 지지의 관계 강도 — 육합(조화·활성화)과 충(강한 충돌)은 그
# 자체로 "변화가 크다"는 신호라 둘 다 최고 강도로 취급한다(방향의 좋고 나쁨은 polarity가
# 별도로 담당하고, 여기서는 순수하게 "영향의 크기"만 잰다).
_RELATION_IMPACT: Dict[str, int] = {
    "육합": 2, "충": 2, "형": 1, "파": 1, "해": 1, "복음": 1, "자형": 1, "무관": 0,
}


def _relation_key(relation: str) -> str:
    """branch_relation()의 '충(충돌·이동)' 같은 라벨을 위 표의 키로 정규화
    (daily/woon_modifier.py의 _relation_key()와 동일 로직, 단일 소스는 아니지만 동형 유지)."""
    r = relation or "무관"
    if r.startswith("복음"):
        return "자형" if "자형" in r else "복음"
    return r.split("(")[0] if "(" in r else r


def _is_female(gender: str) -> bool:
    return str(gender or "").strip().lower() in {"female", "f", "여", "여자", "여성"}


# 9개 영역 정의: groups(주로 반응하는 십신군), palace(원국 어느 기둥의 지지와 대운 지지의
# 관계를 볼지 — 년주=사회적 기반, 월주=부모/형제/조직, 일주=자기 자신·배우자궁).
# 애정/연애·결혼/배우자는 배우자성(성별에 따라 여=관성/남=재성, core.strength.spouse_star와
# 동일 규칙)을 score_domains()에서 동적으로 더한다 — groups는 그 외에 함께 반응하는 축만 담는다.
DOMAIN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "자아_성장": {"label": "자아/성장", "groups": frozenset({"비겁"}), "palace": "day"},
    "학업_전문성": {"label": "학업/전문성", "groups": frozenset({"인성"}), "palace": "month"},
    "직업_사회": {"label": "직업/사회", "groups": frozenset({"관성"}), "palace": "month"},
    "재물": {"label": "재물", "groups": frozenset({"재성"}), "palace": "month"},
    "가족_부모": {"label": "가족/부모", "groups": frozenset({"인성", "재성"}), "palace": "month"},
    "형제자매": {"label": "형제자매", "groups": frozenset({"비겁"}), "palace": "month"},
    "친구_인간관계": {"label": "친구/인간관계", "groups": frozenset({"비겁", "식상"}), "palace": "year"},
    "애정_연애": {"label": "애정/연애", "groups": frozenset({"식상"}), "palace": "day"},
    "결혼_배우자": {"label": "결혼/배우자", "groups": frozenset(), "palace": "day"},
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
    합/충/형/파/해, 억부 희기(polarity), 전체 오행 균형에 미치는 영향(balance_shift)."""
    ganji = fact.get("ganji", "")
    gan = ganji[0] if ganji else ""
    ji = ganji[1] if len(ganji) > 1 else ""
    gan_elem = GAN_ELEM.get(gan, "")
    ji_elem = JI_ELEM.get(ji, "")
    strength = saju.get("strength") or {}
    polarity = resolve_decade_polarity(gan, strength)

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
# 3·4단계: 영역별 영향 분석 + 영향도 계산(0~5)
# ============================================================================
def score_domains(daewoon_stage: Dict[str, Any], age: int, gender: str) -> List[Dict[str, Any]]:
    """9개 영역 각각의 영향도(0~5)를 계산한다.

    base = (대운 천간 십신군이 이 영역의 groups에 속하면 +2) + (대운 지지 십신군이
    groups에 속하면 +1) — 이 영역을 실제로 지배하는 힘(십신)이 이번 대운에 있는지.

    relation_bonus = 이 영역의 palace 기둥 지지와 대운 지지의 합/충/형/파/해 강도
    (_RELATION_IMPACT, 0~2)인데, base가 0(이 영역의 지배 십신이 이번 대운에 전혀 없음)
    이면 육합/충처럼 아주 강한 관계여도 절반(최대 +1)만 반영한다 — palace가 여러 영역에
    걸쳐 공유되기 때문에(예: 월주=부모/형제/직업/재물), 관계 신호만으로 무관한 영역까지
    전부 끌어올리지 않도록 하는 안전장치.

    + (연령대가 이 영역에 가중되면 +1 — CHILD_FOCUS_DOMAINS/ADULT_FOCUS_DOMAINS)
    0~5로 클램프.
    """
    spouse_group = "관성" if _is_female(gender) else "재성"
    gan_group = daewoon_stage.get("gan_group", "")
    ji_group = daewoon_stage.get("ji_group", "")
    gan_sipsin = daewoon_stage.get("gan_sipsin", "")
    ji_sipsin = daewoon_stage.get("ji_sipsin", "")
    relations = daewoon_stage.get("relations") or {}

    results: List[Dict[str, Any]] = []
    for key in DOMAIN_ORDER:
        defn = DOMAIN_DEFINITIONS[key]
        groups = set(defn["groups"])
        if key in ("애정_연애", "결혼_배우자"):
            groups.add(spouse_group)

        base = 0
        if gan_group and gan_group in groups:
            base += 2
        if ji_group and ji_group in groups:
            base += 1

        relation = relations.get(defn["palace"], "무관")
        relation_raw = _RELATION_IMPACT.get(_relation_key(relation), 0)
        relation_bonus = relation_raw if base > 0 else min(relation_raw, 1)

        score = base + relation_bonus
        if age < CHILD_AGE_THRESHOLD and key in CHILD_FOCUS_DOMAINS:
            score += 1
        elif age >= CHILD_AGE_THRESHOLD and key in ADULT_FOCUS_DOMAINS:
            score += 1

        score = max(0, min(5, score))
        # 이 영역을 실제로 움직이는 십신(10종) — 천간이 이 영역의 groups에 속하면 천간
        # 십신을, 아니면(지지만 속하면) 지지 십신을 "화두"의 근거로 쓴다(build_domain_sentence).
        # KEY_AREA_MIN_SCORE(3) 이상이려면 base>0(둘 중 하나는 반드시 속함)이 필수이므로
        # 고영역 문장 생성 시 이 값이 항상 의미 있게 채워진다.
        if gan_group and gan_group in groups:
            driving_sipsin = gan_sipsin
        elif ji_group and ji_group in groups:
            driving_sipsin = ji_sipsin
        else:
            driving_sipsin = gan_sipsin
        results.append({
            "domain": key,
            "label": defn["label"],
            "score": score,
            "relation": relation,
            "matched_groups": sorted(groups & {gan_group, ji_group} - {""}),
            "driving_sipsin": driving_sipsin,
        })
    return results


# ============================================================================
# 5·6단계: 고영역 구체 해석 / 저영역 간소화
# ============================================================================
_LOW_AREA_TEMPLATE = "{label}은(는) 이 대운에서 상대적으로 핵심적인 변화 영역은 아니며, 기존 흐름이 유지됩니다."

# polarity별 톤 — Anti-prediction 원칙: 완곡한 가능성 표현만 쓰고 특정 사건은 단정하지 않는다.
_POLARITY_TONE: Dict[str, str] = {
    "favorable": "이 사람의 기운과 잘 맞아떨어지는 방향이라 순탄하게 느껴질 가능성이 높습니다",
    "unfavorable": "이 사람의 기운에는 부담을 더하는 방향이라 뜻대로 되지 않거나 힘겹게 느껴지는 순간이 있을 수 있습니다",
    "neutral": "뚜렷하게 한쪽으로 쏠리지 않고 무난하게 흘러갈 가능성이 있습니다",
}


def build_domain_sentence(entry: Dict[str, Any], polarity: str) -> str:
    """5·6단계: entry(score_domains()의 항목 하나)를 문장으로 변환.

    score < KEY_AREA_MIN_SCORE(3) -> 저영역 간소화 고정 문구(사용자 지정 문구 그대로).
    score >= 3 -> 이 영역을 실제로 움직이는 십신(entry["driving_sipsin"], 도메인마다
    다를 수 있다) 기준 화두(SIPSIN_CHANGE_AREA, decade_theme과 동일 표 재사용) + 억부
    희기(polarity) 톤을 반영한 구체적 문장. 구체적 사건은 단정하지 않는다.
    """
    label = entry["label"]
    if entry["score"] < KEY_AREA_MIN_SCORE:
        return _LOW_AREA_TEMPLATE.format(label=label)

    eun_neun = _josa(label, "은", "는")
    tone = _POLARITY_TONE.get(polarity, _POLARITY_TONE["neutral"])
    change_area = SIPSIN_CHANGE_AREA.get(entry.get("driving_sipsin", ""), "")
    change_clause = ""
    if change_area:
        gwa_wa = _josa(change_area, "과", "와")
        change_clause = f" 특히 **{change_area}**{gwa_wa} 관련된 화두가 두드러질 수 있습니다."
    return f"{label}{eun_neun} 이번 대운에서 핵심적으로 영향을 받는 영역입니다.{change_clause} {tone}."


# ============================================================================
# 7단계: 자연어 출력 합성
# ============================================================================
def _build_narrative(domain_entries: List[Dict[str, Any]]) -> str:
    key_areas = sorted(
        (d for d in domain_entries if d["is_key_area"]), key=lambda d: -d["score"]
    )
    quiet_areas = [d for d in domain_entries if not d["is_key_area"]]

    if key_areas:
        key_labels = ", ".join(d["label"] for d in key_areas)
        intro = f"이 10년은 {key_labels} 영역에서 변화가 가장 두드러지게 나타날 수 있는 시기입니다."
        detail = " ".join(d["sentence"] for d in key_areas)
    else:
        intro = "이 10년은 어느 한 영역에 크게 치우치기보다 전반적으로 무난하게 흘러갈 수 있는 시기입니다."
        detail = ""

    outro = ""
    if quiet_areas:
        quiet_labels = ", ".join(d["label"] for d in quiet_areas)
        outro = f"그 밖에 {quiet_labels}는 상대적으로 유지되는 흐름이라 크게 신경 쓰지 않아도 됩니다."

    return " ".join(part for part in (intro, detail, outro) if part)


def build_domain_pipeline(
    saju: Dict[str, Any], fact: Dict[str, Any], age: int, gender: str,
) -> Dict[str, Any]:
    """7단계 파이프라인 전체 실행. saju=calculate_saju 산출물, fact=daewoon_step_facts()의
    선택된 단계 하나, age=이 대운을 보는 기준 나이(effective_age), gender=원국 성별."""
    natal = analyze_natal_stage(saju)
    daewoon = analyze_daewoon_stage(saju, fact)
    scored = score_domains(daewoon, age, gender)

    domain_entries: List[Dict[str, Any]] = []
    for entry in scored:
        is_key_area = entry["score"] >= KEY_AREA_MIN_SCORE
        sentence = build_domain_sentence(entry, daewoon["polarity"])
        domain_entries.append({
            "domain": entry["domain"],
            "label": entry["label"],
            "score": entry["score"],
            "is_key_area": is_key_area,
            "sentence": sentence,
        })

    return {
        "natal_summary": natal,
        "daewoon_summary": daewoon,
        "domain_scores": domain_entries,
        "narrative": _build_narrative(domain_entries),
    }
