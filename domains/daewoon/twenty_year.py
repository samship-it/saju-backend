"""20년 연속 십성 묶음의 문장 DB.

공통 흐름은 십성 대분류, 각 10년 본문은 그 구간의 십신 10종이다.
섹션 제목에만 편관운·정관운 같은 이름을 쓴다. 본문에는 그 이름을 넣지 않는다.
"""
import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from domains.daewoon.axis import to_past

ARC_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "twenty_year_arc_db.json")

# 두 10년을 아우르는 태도. 각 10년의 특징 문장과 겹치지 않게 둔다.
_GROUP_FLOW = {
    "관성": "이 20년은 바깥의 기준과 평가를 통과하며 자기 자리를 만들어 가는 흐름입니다. 삶의 태도는 맡은 책임을 피하지 않는 쪽입니다.",
    "인성": "이 20년은 배우고 생각을 쌓으며 사람을 키워 가는 흐름입니다. 삶의 태도는 서두르기보다 이해하고 받아들이는 쪽입니다.",
    "재성": "이 20년은 현실의 결과와 살림의 크기를 키워 가는 흐름입니다. 삶의 태도는 눈에 보이는 성과를 기준으로 움직이는 쪽입니다.",
    "식상": "이 20년은 속에 있는 것을 밖으로 내놓으며 솜씨를 키워 가는 흐름입니다. 삶의 태도는 만들고 드러내는 쪽입니다.",
    "비겁": "이 20년은 나의 힘과 곁의 사람을 기준으로 자리를 잡아 가는 흐름입니다. 삶의 태도는 자기 몫을 분명히 하는 쪽입니다.",
}

# 십신 10종마다 그 10년만의 특징. 제목에만 이름을 쓰고 본문에는 넣지 않는다.
_SIPSIN_DECADE = {
    "편관": "{ages}는 기준이 세고 평가가 매서운 환경입니다. 압박과 도전을 통과하면서 실력이 자라는 구간입니다.",
    "정관": "{ages}는 틀과 역할이 안정된 환경입니다. 제도에 적응하며 책임을 구체화하는 구간입니다.",
    "편인": "{ages}는 정규 길 바깥에서 배우게 되는 환경입니다. 생각이 옆으로 뻗고 남다른 방식으로 실마리를 잡는 구간입니다.",
    "정인": "{ages}는 보호와 정석 학습이 받쳐 주는 환경입니다. 자격과 생각을 차분히 쌓아 올리는 구간입니다.",
    "편재": "{ages}는 기회가 넓게 열리고 돈이 움직이는 환경입니다. 판을 옮기며 성과를 거두는 구간입니다.",
    "정재": "{ages}는 들어오는 돈과 나가는 돈이 일정한 환경입니다. 살림을 단속하고 결과를 차곡차곡 쌓는 구간입니다.",
    "식신": "{ages}는 만들고 내놓는 일이 편한 환경입니다. 솜씨를 꾸준히 갈고 결과물을 남기는 구간입니다.",
    "상관": "{ages}는 틀을 깨고 드러내는 환경입니다. 자기 표현이 앞서고 기존 방식과 마찰을 빚는 구간입니다.",
    "비견": "{ages}는 나와 비슷한 사람과 나란히 서는 환경입니다. 자기 몫을 지키며 동료와 속도를 맞추는 구간입니다.",
    "겁재": "{ages}는 몫을 나누고 경쟁이 붙는 환경입니다. 내 자리를 뺏기지 않으려 힘을 쓰는 구간입니다.",
}

_REL_NOTE = {
    "충": "그 사이 자리와 소속이 크게 흔들립니다.",
    "합": "그 사이 사람과 역할이 한곳으로 모입니다.",
    "형": "그 사이 기준과 마음 사이에 마찰이 있습니다.",
    "파해": "그 사이 계획과 현실이 어긋납니다.",
    "반복": "그 사이 익숙한 모양이 한 번 더 돌아옵니다.",
    "무관": "그 사이 환경의 결은 크게 뒤집히지 않고 속도만 달라집니다.",
}

# 카테고리 카드에 덧붙는 한 줄. 학업·교우·가정이 같은 문장을 공유하지 않는다.
_SLOTS = {
    "front": {
        "study": "이 구간의 학업은 배우는 방식을 익히며 시작하는 일입니다.",
        "friendship": "이 구간의 교우는 무리를 겪으며 관계를 시작하는 일입니다.",
        "home": "이 구간의 가정은 부모의 기준 안에서 생활의 틀을 시작하는 일입니다.",
        "allowance": "이 구간의 살림은 돈이 들고 나는 감각을 익히며 시작하는 일입니다.",
        "career": "이 구간의 일은 맡은 자리를 배우며 단련을 시작하는 일입니다.",
        "wealth": "이 구간의 돈은 버는 길을 열며 시작하는 일입니다.",
        "relationship": "이 구간의 인연은 마음의 거리를 배우며 시작하는 일입니다.",
        "family": "이 구간의 가족은 맡는 몫을 익히며 시작하는 일입니다.",
    },
    "back": {
        "study": "이 구간의 학업은 익혀 둔 공부가 자격과 결과로 안착하는 일입니다.",
        "friendship": "이 구간의 교우는 이어 온 관계가 자기 무리로 안착하는 일입니다.",
        "home": "이 구간의 가정은 앞 시기의 분위기가 집안의 자리로 안착하는 일입니다.",
        "allowance": "이 구간의 살림은 드나들던 돈이 관리하는 습관으로 안착하는 일입니다.",
        "career": "이 구간의 일은 익힌 역할이 권한과 성과로 안착하는 일입니다.",
        "wealth": "이 구간의 돈은 열어 둔 수입이 모으는 결과로 안착하는 일입니다.",
        "relationship": "이 구간의 인연은 배운 거리가 약속과 관계로 안착하는 일입니다.",
        "family": "이 구간의 가족은 익힌 몫이 돌보는 자리로 안착하는 일입니다.",
    },
}

ARC_DB: Dict[str, Any] = {
    "_prompt_v": "2026-10-19-twenty-sections",
    "groups": _GROUP_FLOW,
    "decades": _SIPSIN_DECADE,
    "relations": _REL_NOTE,
    "slots": _SLOTS,
}


@lru_cache(maxsize=1)
def load_arc_db() -> Dict[str, Any]:
    with open(ARC_DB_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def reload_arc_db() -> Dict[str, Any]:
    load_arc_db.cache_clear()
    return load_arc_db()


def _age_label(start: int, end: int) -> str:
    return f"{start}~{end}세"


def _maybe_past(text: str, past: bool) -> str:
    if not past:
        return text
    body = text if text.endswith(".") else text + "."
    return to_past(body)


def _decade_title(order: str, sipsin: str) -> str:
    name = (sipsin or "").strip()
    return f"{order} ({name}운)" if name else order


def _decade_body(db: Dict[str, Any], sipsin: str, rel: str, ages: Tuple[int, int]) -> str:
    template = (db.get("decades") or {}).get(sipsin) or db["decades"]["비견"]
    note = (db.get("relations") or {}).get(rel) or db["relations"]["무관"]
    return f"{template.format(ages=_age_label(*ages))} {note}"


def build_twenty_year_story(
    group: str,
    front_sipsin: str,
    back_sipsin: str,
    front_rel: str,
    back_rel: str,
    front_ages: Tuple[int, int],
    back_ages: Tuple[int, int],
    front_past: bool,
    back_past: bool,
) -> Dict[str, Any]:
    """공통 흐름 + 첫 10년의 십신 특징 + 둘째 10년의 십신 특징."""
    db = load_arc_db()
    overview = (db.get("groups") or {}).get(group) or db["groups"]["비겁"]
    front_text = _decade_body(db, front_sipsin, front_rel, front_ages)
    back_text = _decade_body(db, back_sipsin, back_rel, back_ages)
    return {
        "section_common": "20년의 공통 흐름",
        "section_front": _decade_title("첫 번째 10년", front_sipsin),
        "section_back": _decade_title("두 번째 10년", back_sipsin),
        "overview": _maybe_past(overview, back_past),
        "front": _maybe_past(front_text, front_past),
        "back": _maybe_past(back_text, back_past),
        "age_range": [front_ages[0], back_ages[1]],
        "front_age_range": [front_ages[0], front_ages[1]],
        "back_age_range": [back_ages[0], back_ages[1]],
    }


def arc_slot_line(slot: str, role: Optional[str], past: bool) -> str:
    if role not in ("front", "back"):
        return ""
    db = load_arc_db()
    text = (db["slots"].get(role) or {}).get(slot) or ""
    if not text:
        return ""
    return _maybe_past(text, past)


def joined_story(story: Dict[str, Any]) -> str:
    parts = (
        story.get("section_common"), story.get("overview"),
        story.get("section_front"), story.get("front"),
        story.get("section_back"), story.get("back"),
    )
    return " ".join(part for part in parts if part)
