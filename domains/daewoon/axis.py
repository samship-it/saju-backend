"""10년 대운 해석 키.

문장을 고르는 조건은 십성 하나가 아니다. 대운 십성, 대운 지지와 원국의
형충회합, 일간 신강/신약, 용신 오행 네 축을 한 키로 묶는다. 사용자 문장에는
십신명·신강/신약·용신·관운/인성운을 넣지 않고, 그 조합이 만드는 현실 장면만 쓴다.
"""
from typing import Any, Dict, Optional

_RELATION_CLASS = {
    "육합": "합", "삼합": "합", "방합": "합", "반합": "합",
    "충": "충",
    "형": "형", "자형": "형",
    "파": "파해", "해": "파해",
    "복음": "반복",
}


def relation_class(relation: str) -> str:
    raw = relation or "무관"
    if raw.startswith("복음"):
        return "형" if "자형" in raw else "반복"
    head = raw.split("(")[0]
    return _RELATION_CLASS.get(head, "무관")


def strength_band(verdict: Optional[str]) -> str:
    if verdict in ("신강", "신약", "중화"):
        return verdict
    return "중화"


def primary_yongsin(strength: Optional[Dict[str, Any]]) -> str:
    names = (strength or {}).get("yongsin") or []
    return names[0] if names else ""


def interpretation_key(sipsin: str, rel: str, band: str, yongsin_elem: str) -> str:
    return f"{sipsin}|{rel}|{band}|{yongsin_elem or '없음'}"


def same_group_run(prev_fact: Optional[Dict[str, Any]], fact: Optional[Dict[str, Any]]) -> bool:
    """이전 대운과 이번 대운의 십성 그룹이 같으면 연속이다. 정관 다음 편관처럼
    10종 이름은 달라도 20년 연속 관성인 경우를 잡는다."""
    if not prev_fact or not fact:
        return False
    prev = prev_fact.get("sipsin_group")
    cur = fact.get("sipsin_group")
    return bool(prev) and prev == cur


def strongest_relation_class(relations: Dict[str, str]) -> str:
    rank = {"충": 4, "합": 3, "형": 2, "파해": 2, "반복": 1, "무관": 0}
    best = "무관"
    best_rank = 0
    for palace in ("year", "month", "day", "hour"):
        rel = relation_class(relations.get(palace, "무관"))
        score = rank.get(rel, 0)
        if score > best_rank:
            best, best_rank = rel, score
    return best


# 영역 카드에 붙는 현실 대상. 미성년 문구에는 직장·연애·배우자·자산 관리를 넣지 않는다.
_FOCUS = {
    ("career", True): "일과 권한",
    ("career", False): "맡은 활동과 규칙",
    ("wealth", True): "수입과 지출",
    ("wealth", False): "용돈과 소비",
    ("relationship", True): "만남과 마음의 거리",
    ("relationship", False): "호감과 마음",
    ("family", True): "가족 안에서 맡는 몫",
    ("family", False): "가족과 지내는 방식",
    ("study", False): "배우고 익히는 방식",
    ("allowance", False): "용돈과 소비",
    ("friendship", True): "모임과 인맥",
    ("friendship", False): "또래 무리",
    ("home", False): "집 안의 분위기",
}

_SCENE = {
    "충": "{focus} 쪽에서 자리와 소속이 크게 흔들립니다.",
    "합": "{focus} 쪽에서 역할이 한곳으로 묶이거나 권한이 넘어갑니다.",
    "형": "{focus} 쪽에서 기준과 사람 사이에 마찰이 납니다.",
    "파해": "{focus} 쪽에서 협조가 어긋나 막힌 고리를 풀어야 합니다.",
    "반복": "{focus} 쪽이 지난 시기와 거의 같은 모양으로 돌아와 정리가 필요합니다.",
    "무관": "{focus} 쪽은 환경이 크게 뒤집히기보다 겉과 속의 결이 갈립니다.",
}

_ADULT_CAREER_SCENE = {
    "충": "일과 권한 쪽에서 이직이나 조직 개편으로 자리가 크게 바뀝니다.",
    "합": "일과 권한 쪽에서 승진이나 권한 이양처럼 역할이 한곳으로 묶입니다.",
    "형": "일과 권한 쪽에서 조직 안의 기준과 사람이 부딪힙니다.",
    "파해": "일과 권한 쪽에서 협조가 어긋나 맡은 범위를 다시 나눠야 합니다.",
    "반복": "일과 권한 쪽이 지난 10년과 같은 모양으로 돌아와, 이미 가진 권한을 넘기고 다듬는 일이 앞에 섭니다.",
    "무관": "일과 권한 쪽은 환경이 크게 뒤집히기보다, 맡은 일과 받치는 조건의 결이 갈립니다.",
}

_SPLIT = {
    True: "겉으로 맡는 일과 밑에서 받치는 환경이 다른 방향이라, 안에서 조율하는 갈등이 따라옵니다.",
    False: "겉으로 맡는 일과 밑의 환경이 같은 결이라, 지난 단계 위에 한 단을 더 쌓는 발전으로 이어집니다.",
}

_BAND = {
    "신강": "판을 직접 밀 여력은 있는 편입니다.",
    "신약": "한꺼번에 바꾸기보다 나눠 대응하는 편이 맞습니다.",
    "중화": "속도를 조절하며 정해 둔 기준대로 가면 됩니다.",
}

_YONGSIN_WORK = {
    "목": "이때 힘이 실리는 일은 새 판을 여는 쪽입니다.",
    "화": "이때 힘이 실리는 일은 성과를 드러내는 쪽입니다.",
    "토": "이때 힘이 실리는 일은 신뢰를 쌓아 자리를 다지는 쪽입니다.",
    "금": "이때 힘이 실리는 일은 기준을 세우고 정리하는 쪽입니다.",
    "수": "이때 힘이 실리는 일은 상황을 읽고 유연하게 넘기는 쪽입니다.",
}

# 연속 대운에서 점수 카드 한 줄(명사구). 십신 기본 정의 대신 환경 변화만 말한다.
_PIPE_FOCUS = {
    "직업_사회": "일과 권한",
    "재물": "수입과 지출",
    "애정_연애": "만남과 마음의 거리",
    "결혼_배우자": "함께 사는 역할",
    "가족_부모": "가족 안에서 맡는 몫",
    "형제자매": "형제자매와 나누는 몫",
    "친구_인간관계": "모임과 교류",
    "자아_성장": "스스로 정하는 선택",
    "학업_전문성": "배우고 익히는 방식",
}

_PIPE_MINOR_FOCUS = {
    "직업_사회": "맡은 활동과 규칙",
    "재물": "용돈과 소비",
    "애정_연애": "호감과 마음",
    "결혼_배우자": "관계를 진지하게 보는 태도",
    "가족_부모": "가족과 지내는 방식",
    "형제자매": "형제자매와 나누는 방식",
    "친구_인간관계": "또래 무리",
    "자아_성장": "스스로 정하는 생활",
    "학업_전문성": "배우고 익히는 방식",
}

_PIPE_TAIL = {
    "충": "{focus} 쪽에서 자리와 환경이 크게 흔들리는 구조",
    "합": "{focus} 쪽에서 역할이 한곳으로 묶이는 구조",
    "형": "{focus} 쪽에서 기준과 사람이 부딪히는 구조",
    "파해": "{focus} 쪽에서 협조가 어긋난 고리를 푸는 구조",
    "반복": "{focus} 쪽이 지난 시기와 같은 모양으로 돌아와 정리가 필요한 구조",
    "무관": "{focus} 쪽에서 겉뜻은 이어지고 속의 결만 달라지는 구조",
}


def continued_manifestation(domain_key: str, stage_bucket: str, rel: str) -> str:
    minor = stage_bucket == "미성년"
    table = _PIPE_MINOR_FOCUS if minor else _PIPE_FOCUS
    focus = table.get(domain_key, "이 영역의 역할")
    return _PIPE_TAIL.get(rel, _PIPE_TAIL["무관"]).format(focus=focus)


def axis_note(rel: str, stem_splits: bool, band: str, yongsin_elem: str, continued: bool) -> str:
    """문장 뒤에 붙는 네 축 설명. 연속 대운이면 환경·겉과 속을 앞에 둔다."""
    parts = []
    if continued:
        parts.append("지난 시기의 기본 뜻은 반복하지 않고, 환경 변화와 겉과 속의 차이에 무게를 둡니다.")
    scene = _SCENE.get(rel, "")
    if rel != "무관" and not continued:
        parts.append(scene.format(focus="주변"))
    parts.append(_SPLIT[stem_splits])
    parts.append(_BAND.get(band, _BAND["중화"]))
    yong = _YONGSIN_WORK.get(yongsin_elem, "")
    if yong:
        parts.append(yong)
    return " ".join(parts)


def visible_rider(slot: str, adult: bool, rel: str, stem_splits: bool, band: str, yongsin_elem: str, continued: bool) -> str:
    if slot == "career" and adult:
        scene = _ADULT_CAREER_SCENE.get(rel, _ADULT_CAREER_SCENE["무관"])
    else:
        focus = _FOCUS.get((slot, adult)) or _FOCUS.get((slot, False), "이 영역")
        scene = _SCENE.get(rel, _SCENE["무관"]).format(focus=focus)
    lead = "지난 시기의 기본 뜻은 접어 두고, " if continued else ""
    parts = [f"{lead}{scene}", _SPLIT[stem_splits], _BAND.get(band, _BAND["중화"])]
    yong = _YONGSIN_WORK.get(yongsin_elem, "")
    if yong:
        parts.append(yong)
    return " ".join(parts)


def shape_lead(original: str, rider: str, continued: bool) -> str:
    original = (original or "").strip()
    if continued:
        return f"{rider} {original}".strip()
    if not original:
        return rider
    return f"{original} {rider}"


_LEAD_FIELD = {
    "career_or_study": ("core_change", "career", True),
    "wealth_flow": ("earning_style", "wealth", True),
    "relationship": ("flow", "relationship", True),
    "family": ("change_flow", "family", True),
}

_YOUTH_LEAD = {
    "career_or_study": ("growth_flow", "career", False),
}

_CHILD_LEAD = {
    "study_growth": ("school_life", "study", False),
    "allowance_economy": ("allowance_flow", "allowance", False),
    "friendship": ("peer_relationship", "friendship", False),
    "family_environment": ("parent_relationship", "home", False),
}


def overlay_domain_analysis(
    analysis: Dict[str, Any],
    *,
    rel: str,
    stem_splits: bool,
    band: str,
    yongsin_elem: str,
    continued: bool,
    child: bool,
) -> Dict[str, Any]:
    """영역 카드의 첫 문장에 네 축을 반영한다. 연속 대운이면 환경 문장을 앞에 둔다.
    기존 체감 문장(희기 톤)은 뒤에 남겨 같은 십성 안에서의 강약 차이는 유지한다."""
    out: Dict[str, Any] = {}
    for key, value in analysis.items():
        if not isinstance(value, dict):
            out[key] = value
            continue
        copied = dict(value)
        if child:
            field_spec = _CHILD_LEAD.get(key)
        elif key == "career_or_study" and "growth_flow" in copied and "core_change" not in copied:
            field_spec = _YOUTH_LEAD[key]
        else:
            field_spec = _LEAD_FIELD.get(key)
        if field_spec and field_spec[0] in copied and isinstance(copied[field_spec[0]], str):
            field, slot, adult = field_spec
            if child:
                adult = False
            rider = visible_rider(slot, adult, rel, stem_splits, band, yongsin_elem, continued)
            copied[field] = shape_lead(copied[field], rider, continued)
        out[key] = copied
    return out


def rewrite_decade_theme(
    theme: Optional[Dict[str, str]],
    *,
    rel: str,
    stem_splits: bool,
    band: str,
    yongsin_elem: str,
    continued: bool,
    adult: bool,
) -> Optional[Dict[str, str]]:
    if not theme:
        return theme
    rider = visible_rider("career" if adult else "study", adult, rel, stem_splits, band, yongsin_elem, continued)
    # 풍경 하단 문장은 십신 이름(관운·인성운) 대신 환경과 현실 장면만 남긴다.
    # 십신 정의는 saju_relation 한 곳에만 둔다.
    return {"pair_sipsin": theme.get("pair_sipsin", ""), "sentence": rider}
