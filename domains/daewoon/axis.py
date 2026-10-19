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


# 카테고리마다 문장 골격이 달라야 한다. "{대상} 쪽에서 …" 한 틀을 명사만 바꿔 붙이면
# 학업·용돈·교우·부모가 같은 말로 읽힌다.
_SLOT_LINE = {
    "study": {
        "충": "학교나 학년이 바뀌면서 수업 환경이 흔들립니다.",
        "합": "같은 반과 선생님 아래로 공부하는 방식이 모입니다.",
        "형": "지키라는 규칙과 하고 싶은 공부 사이에 마찰이 있습니다.",
        "파해": "공부 계획과 실제 도움이 어긋나 흐름이 끊깁니다.",
        "반복": "앞서와 비슷한 공부 방식이 그대로 이어집니다.",
        "무관": "배움의 환경이 크게 바뀌기보다 익히는 속도만 달라집니다.",
    },
    "friendship": {
        "충": "친구 사이가 갈라지거나 무리가 새로 나뉩니다.",
        "합": "마음이 맞는 친구들과 한 무리로 모입니다.",
        "형": "친구들 사이에서 지켜야 할 선과 감정 사이에 마찰이 있습니다.",
        "파해": "약속과 만남이 어긋나 사이가 멀어집니다.",
        "반복": "같은 친구 관계가 이전과 비슷한 모양으로 이어집니다.",
        "무관": "친구 관계가 크게 뒤집히기보다 거리만 조금 달라집니다.",
    },
    "home": {
        "충": "집안의 규칙이나 부모와의 거리가 크게 흔들립니다.",
        "합": "가족의 기대와 역할이 한쪽으로 모입니다.",
        "형": "부모의 기준과 아이 마음 사이에 마찰이 있습니다.",
        "파해": "가족의 도움과 실제 생활이 어긋납니다.",
        "반복": "집안의 분위기가 이전과 비슷한 모양으로 이어집니다.",
        "무관": "집안 분위기가 크게 바뀌기보다 기대의 무게만 달라집니다.",
    },
    "allowance": {
        "충": "들어오고 나가는 돈이 불규칙하게 흔들립니다.",
        "합": "버는 일과 쓰는 일이 한 틀로 묶입니다.",
        "형": "모으려는 기준과 써야 하는 곳 사이에 마찰이 있습니다.",
        "파해": "들어올 돈과 나갈 돈이 어긋납니다.",
        "반복": "돈의 흐름이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "돈의 규모가 크게 바뀌기보다 쓰는 방식만 달라집니다.",
    },
    "career_minor": {
        "충": "맡은 활동과 소속 모임이 갑자기 바뀝니다.",
        "합": "활동의 역할이 한 팀 안으로 모입니다.",
        "형": "정해진 규칙과 하고 싶은 방식 사이에 마찰이 있습니다.",
        "파해": "역할 분담과 실제 도움이 어긋납니다.",
        "반복": "맡은 활동이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "활동의 종류가 크게 바뀌기보다 책임의 무게만 달라집니다.",
    },
    "career": {
        "충": "일자리나 소속이 이직이나 조직 개편으로 크게 바뀝니다.",
        "합": "승진이나 권한 이양으로 역할이 한곳에 모입니다.",
        "형": "조직의 기준과 사람 사이에 마찰이 있습니다.",
        "파해": "맡은 일과 협조가 어긋나 범위를 다시 나누게 됩니다.",
        "반복": "일의 결은 비슷하고, 이미 가진 권한을 다듬게 됩니다.",
        "무관": "일의 종류가 크게 바뀌기보다 책임의 무게만 달라집니다.",
    },
    "wealth": {
        "충": "수입과 지출의 균형이 크게 흔들립니다.",
        "합": "버는 경로와 모으는 방식이 한 틀로 묶입니다.",
        "형": "지키려는 예산과 나가야 하는 돈 사이에 마찰이 있습니다.",
        "파해": "들어올 돈과 나갈 돈이 어긋납니다.",
        "반복": "돈의 흐름이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "자산의 크기가 크게 바뀌기보다 관리하는 방식만 달라집니다.",
    },
    "relationship": {
        "충": "만나던 거리와 감정의 온도가 크게 흔들립니다.",
        "합": "마음이 가는 사람과 약속이 한쪽으로 모입니다.",
        "형": "지키고 싶은 원칙과 감정 사이에 마찰이 있습니다.",
        "파해": "만남의 기대와 실제 연락이 어긋납니다.",
        "반복": "관계의 결이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "관계의 형태가 크게 바뀌기보다 감정의 거리만 달라집니다.",
    },
    "family": {
        "충": "가족 안에서 맡는 역할이 크게 흔들립니다.",
        "합": "가족의 살림과 책임이 한쪽으로 모입니다.",
        "형": "지키려는 원칙과 가족의 감정 사이에 마찰이 있습니다.",
        "파해": "도와야 하는 곳과 실제 여유가 어긋납니다.",
        "반복": "가족 안의 역할이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "가족 관계가 크게 바뀌기보다 책임의 무게만 달라집니다.",
    },
    "marriage": {
        "충": "함께 사는 방식과 역할 분담이 크게 흔들립니다.",
        "합": "살림과 책임이 한 집으로 모입니다.",
        "형": "각자의 기준과 같이 사는 방식 사이에 마찰이 있습니다.",
        "파해": "기대하던 역할과 실제 살림이 어긋납니다.",
        "반복": "같이 사는 결이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "같이 사는 형태가 크게 바뀌기보다 역할의 무게만 달라집니다.",
    },
    "siblings": {
        "충": "형제자매와 나누는 몫이 크게 흔들립니다.",
        "합": "형제자매의 역할이 한쪽으로 모입니다.",
        "형": "형제자매 사이에서 기준과 감정 사이에 마찰이 있습니다.",
        "파해": "도와야 할 일과 실제 형편이 어긋납니다.",
        "반복": "형제자매와의 거리가 이전과 비슷한 모양으로 이어집니다.",
        "무관": "형제자매 관계가 크게 바뀌기보다 맡는 몫만 달라집니다.",
    },
    "self": {
        "충": "스스로 정하던 생활 방식이 크게 흔들립니다.",
        "합": "선택과 기준이 한 방향으로 모입니다.",
        "형": "하고 싶은 것과 해야 하는 것 사이에 마찰이 있습니다.",
        "파해": "세운 계획과 실제 하루가 어긋납니다.",
        "반복": "생활의 결이 이전과 비슷한 모양으로 이어집니다.",
        "무관": "생활이 크게 바뀌기보다 선택의 속도만 달라집니다.",
    },
}

_DOMAIN_SLOT = {
    "직업_사회": "career",
    "재물": "wealth",
    "애정_연애": "relationship",
    "결혼_배우자": "marriage",
    "가족_부모": "family",
    "형제자매": "siblings",
    "친구_인간관계": "friendship",
    "자아_성장": "self",
    "학업_전문성": "study",
}

_THEME_REL = {
    "충": "자리와 소속이 크게 흔들리는 환경",
    "합": "사람과 역할이 한곳으로 모이는 환경",
    "형": "기준과 마음 사이에 마찰이 있는 환경",
    "파해": "계획과 현실이 어긋나는 환경",
    "반복": "이전과 비슷한 모양이 돌아오는 환경",
    "무관": "환경이 크게 뒤집히기보다 속도와 무게만 달라지는 환경",
}

_BAND_LINE = {
    "신강": "직접 밀어 볼 여력은 있는 편입니다.",
    "신약": "한꺼번에 바꾸기보다 나눠 대응하는 편이 맞습니다.",
    "중화": "정해 둔 속도대로 가면 되는 균형입니다.",
}

_PAST_SUFFIXES = (
    ("않았을 가능성이 있습니다", "않았던 시기였습니다"),
    ("없었을 가능성이 있는 시기입니다", "없었던 시기였습니다"),
    ("않았을 가능성이 있는 시기입니다", "않았던 시기였습니다"),
    ("했을 가능성이 높습니다", "했던 시기였습니다"),
    ("했을 가능성이 높은 시기입니다", "했던 시기였습니다"),
    ("했을 가능성이 있는 시기입니다", "했던 시기였습니다"),
    ("했을 가능성이 있습니다", "했던 시기였습니다"),
    ("았을 가능성이 있습니다", "았던 시기였습니다"),
    ("었을 가능성이 있습니다", "었던 시기였습니다"),
    ("였을 가능성이 있습니다", "였던 시기였습니다"),
    ("수 있는 10년입니다", "수 있었던 10년이었습니다"),
    ("10년입니다", "10년이었습니다"),
    ("시기입니다", "시기였습니다"),
    ("흐름입니다", "흐름이었습니다"),
    ("쪽입니다", "쪽이었습니다"),
    ("편입니다", "편이었습니다"),
    ("균형입니다", "균형이었습니다"),
    ("맞습니다", "맞았던 시기였습니다"),
    ("필요합니다", "필요했던 시기였습니다"),
    ("좋습니다", "좋았던 시기였습니다"),
    ("쉽습니다", "쉬웠던 시기였습니다"),
    ("있습니다", "있었던 시기였습니다"),
    ("흔들립니다", "흔들리던 시기였습니다"),
    ("모입니다", "모이던 시기였습니다"),
    ("끊깁니다", "끊기던 시기였습니다"),
    ("이어집니다", "이어지던 시기였습니다"),
    ("달라집니다", "달라지던 시기였습니다"),
    ("멀어집니다", "멀어지던 시기였습니다"),
    ("어긋납니다", "어긋나던 시기였습니다"),
    ("바뀝니다", "바뀌던 시기였습니다"),
    ("나뉩니다", "나뉘던 시기였습니다"),
    ("묶입니다", "묶이던 시기였습니다"),
    ("됩니다", "되었던 시기였습니다"),
    ("보입니다", "보였던 시기였습니다"),
    ("얻습니다", "얻었던 시기였습니다"),
    ("애씁니다", "애썼던 시기였습니다"),
    ("지냅니다", "지냈던 시기였습니다"),
    ("따릅니다", "따랐던 시기였습니다"),
    ("느낍니다", "느꼈던 시기였습니다"),
    ("남깁니다", "남겼던 시기였습니다"),
    ("맺습니다", "맺었던 시기였습니다"),
    ("둡니다", "두었던 시기였습니다"),
    ("두드러집니다", "두드러졌던 시기였습니다"),
    ("많습니다", "많았던 시기였습니다"),
    ("잡습니다", "잡았던 시기였습니다"),
    ("합니다", "했던 시기였습니다"),
    ("갑니다", "갔던 시기였습니다"),
    ("랍니다", "랐던 시기였습니다"),
    ("입니다", "이었습니다"),
    ("습니다", "던 시기였습니다"),
)


def _past_sentence(sentence: str) -> str:
    text = sentence.strip()
    if not text:
        return text
    period = text.endswith(".")
    body = text[:-1] if period else text
    if any(mark in body for mark in ("였습니다", "었습니다", "었던 시기", "했던 시기", "았던 시기")):
        return text
    if body.endswith("마세요"):
        body = body[:-3] + "말아야 했던 시기였습니다"
    elif body.endswith("세요"):
        body = body[:-2] + "해야 했던 시기였습니다"
    else:
        for src, dst in _PAST_SUFFIXES:
            if body.endswith(src):
                body = body[: -len(src)] + dst
                break
    return body + ("." if period else "")


def to_past(text: str) -> str:
    """이미 끝난 대운의 현재·미래형 문장을 회고로 바꾼다. '~했던 시기였습니다'를 쓰고,
    금지된 '했을 가능성이 있습니다' 꼴은 남기지 않는다."""
    if not text:
        return text
    parts = text.split(". ")
    changed = [_past_sentence(part if part.endswith(".") or i == len(parts) - 1 else part + ".") for i, part in enumerate(parts)]
    # _past_sentence may re-add the period; normalize the join.
    normalized = []
    for part in changed:
        piece = part.strip()
        if piece.endswith("."):
            piece = piece[:-1]
        normalized.append(piece)
    return ". ".join(normalized) + ("." if text.rstrip().endswith(".") else "")


def past_task(task: str) -> str:
    body = (task or "").strip().rstrip(".")
    if body.endswith("는 것"):
        return body[:-3] + "던 일이었습니다."
    return to_past(body + ".")


def household_clause(past: bool) -> str:
    """18세 미만에는 용돈 칸을 두지 않고, 금전은 집안 형편과 부모의 영향으로만 말한다."""
    text = "살림의 여유와 부족한 부분이 부모님을 통해 집안에 배어 있습니다."
    return to_past(text) if past else text


def slot_line(slot: str, rel: str, minor: bool = False) -> str:
    key = "career_minor" if slot == "career" and minor else slot
    table = _SLOT_LINE.get(key) or _SLOT_LINE["self"]
    return table.get(rel) or table["무관"]


def domain_relation_line(domain_key: str, rel: str, minor: bool = False) -> str:
    slot = _DOMAIN_SLOT.get(domain_key, "self")
    return slot_line(slot, rel, minor=minor)


def theme_sentence(rel: str, continued: bool, past: bool, band: str, yongsin_elem: str) -> str:
    scene = _THEME_REL.get(rel, _THEME_REL["무관"])
    if continued:
        head = f"같은 주제가 10년 더 이어집니다. 달라진 점은 {scene}입니다."
    else:
        head = f"이 10년은 {scene}입니다."
    parts = [head, _BAND_LINE.get(band, _BAND_LINE["중화"])]
    yong = _YONGSIN_WORK.get(yongsin_elem, "")
    if yong:
        parts.append(yong)
    text = " ".join(parts)
    return to_past(text) if past else text


def overlay_domain_analysis(
    analysis: Dict[str, Any],
    *,
    rel: str,
    stem_splits: bool,
    band: str,
    yongsin_elem: str,
    continued: bool,
    child: bool,
    past: bool = False,
    arc_role: Optional[str] = None,
) -> Dict[str, Any]:
    """영역 카드에는 그 카테고리만의 한 문장을 덧붙인다. 연속 십성·신강·용신 설명은
    풍경 문장 한 곳에만 두고, 카드마다 같은 첫머리를 붙이지 않는다.
    20년 묶음이면 그 구간의 역할(시작/안착) 한 줄을 리드 칸에만 더한다."""
    del stem_splits, band, yongsin_elem, continued
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
            line = slot_line(slot, rel, minor=not adult)
            original = copied[field].strip()
            if past:
                original = to_past(original if original.endswith(".") else original + ".")
                line = to_past(line)
            extra = ""
            if arc_role:
                from domains.daewoon.twenty_year import arc_slot_line
                extra = arc_slot_line(slot, arc_role, past)
            copied[field] = " ".join(part for part in (original, line, extra) if part)
        elif past:
            for field, leaf in list(copied.items()):
                if isinstance(leaf, str):
                    copied[field] = to_past(leaf if leaf.endswith(".") else leaf + ".")
        out[key] = copied
    if past:
        for key, value in list(out.items()):
            if not isinstance(value, dict):
                continue
            for field, leaf in list(value.items()):
                if isinstance(leaf, str) and "시기였" not in leaf and "었던" not in leaf and "했던" not in leaf:
                    value[field] = to_past(leaf if leaf.endswith(".") else leaf + ".")
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
    past: bool = False,
) -> Optional[Dict[str, str]]:
    del stem_splits, adult
    if not theme:
        return theme
    return {
        "pair_sipsin": theme.get("pair_sipsin", ""),
        "sentence": theme_sentence(rel, continued, past, band, yongsin_elem),
    }
