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
    "관성": "이 20년은 바깥에서 오는 기준을 하나씩 통과하며 내 자리를 만들어 가는 흐름입니다. 한 번에 모든 인정을 받으려 하기보다, 사람 앞에서 한 약속을 끝까지 지키는 태도가 이 시기를 받쳐 주는 시기입니다.",
    "인성": "이 20년은 배우고 생각을 정리하며 나와 사람을 함께 키워 가는 흐름입니다. 결과부터 재촉하기보다, 이해할 시간을 허락하는 태도가 이후의 선택을 넓혀 주는 시기입니다.",
    "재성": "이 20년은 눈에 보이는 결과와 살림의 크기를 천천히 키워 가는 흐름입니다. 숫자만 쫓기보다, 들어온 것을 어디에 남길지 살피며 움직이는 태도가 생활을 안정시키는 시기입니다.",
    "식상": "이 20년은 속에 쌓아 둔 것을 밖으로 내놓으며 솜씨를 키워 가는 흐름입니다. 완벽해진 뒤에 보여 주기보다, 만들고 다듬으며 길을 여는 태도가 일의 다음을 만드는 시기입니다.",
    "비겁": "이 20년은 나의 힘과 곁의 사람을 기준으로 자리를 잡아 가는 흐름입니다. 남과 비교해 조급해지기보다, 내 몫을 지키면서도 함께 갈 사람을 가려 두는 태도가 필요한 시기입니다.",
}

# 십신 10종마다 그 10년만의 특징. 제목에만 이름을 쓰고 본문에는 넣지 않는다.
_SIPSIN_DECADE = {
    "편관": "{ages}는 기준이 높고 평가의 눈이 매서워서, 마음이 먼저 조여 오는 환경입니다. 그 압박을 견디며 작은 도전을 통과할 때마다 실력이 자라는 구간입니다. 남에게 보여 주기 위한 속도보다, 내가 감당할 수 있는 기준으로 한 걸음씩 가는 편이 오래 남는 흐름입니다.",
    "정관": "{ages}는 역할과 틀이 비교적 분명하게 놓여 있는 환경입니다. 그 틀에 몸을 맞추며 책임을 구체적으로 만들고, 내가 지켜야 할 자리를 사람 앞에 분명히 하는 구간입니다. 크게 튀기보다 약속을 쌓을수록 신뢰가 붙는 시기입니다.",
    "편인": "{ages}는 정해진 길 바깥에서 배우게 되는 환경입니다. 생각이 옆으로 뻗으며, 남들이 지나치는 자리에서 실마리를 붙잡는 구간입니다. 혼자만의 생각에 머물지 않고 한 줄로 정리해 사람과 나누면 길이 보이는 시기입니다.",
    "정인": "{ages}는 보호와 정석적인 배움이 받쳐 주는 환경입니다. 조급하게 결과를 재촉하기보다, 공부와 생각을 차분히 내 것으로 쌓아 올리는 구간입니다. 그 시간이 이후의 선택을 덜 흔들리게 하는 시기입니다.",
    "편재": "{ages}는 기회가 넓게 열리고 돈과 사람이 바쁘게 움직이는 환경입니다. 판을 옮기며 눈에 보이는 성과를 거두는 구간입니다. 열리는 문마다 들어가기보다, 남길 결과 하나를 정해 두면 살림이 커지는 시기입니다.",
    "정재": "{ages}는 들어오는 것과 나가는 것이 비교적 일정한 환경입니다. 살림을 단속하고 결과를 차곡차곡 쌓는 구간입니다. 당장의 크기보다 흐름을 일정하게 지키는 습관이 생활을 안정시키는 시기입니다.",
    "식신": "{ages}는 만들고 내놓는 일이 한결 편한 환경입니다. 솜씨를 꾸준히 갈고, 사람 앞에 작은 결과물을 남기는 구간입니다. 완벽을 기다리지 않고 쌓아 둔 흔적이 다음 일의 밑천이 되는 시기입니다.",
    "상관": "{ages}는 있는 틀을 깨고 나를 드러내게 되는 환경입니다. 표현이 앞서며 익숙한 방식과 마찰이 생기는 구간입니다. 드러내고 싶은 마음을 결과로 남기면, 그 마찰이 나만의 색깔로 남는 시기입니다.",
    "비견": "{ages}는 나와 비슷한 사람과 나란히 서게 되는 환경입니다. 내 몫을 지키면서도 동료와 속도를 맞추는 구간입니다. 비교에 힘을 빼기보다 함께 가는 방식을 정해 두면 자리가 안정되는 시기입니다.",
    "겁재": "{ages}는 몫을 나누고 경쟁이 붙기 쉬운 환경입니다. 내 자리를 지키려 힘을 쓰는 구간입니다. 모든 경쟁에 뛰어들기보다, 믿을 사람과 지켜야 할 몫을 가려 두면 이후의 힘이 남는 시기입니다.",
}

# 본문에는 십성 이름을 넣지 않는다. 제목과 배지만 그 이름을 쓴다.
_ACTION = {
    "관성": "이 20년에는 사람 앞에서 맡은 역할과 지켜야 할 약속을 차근차근 정리해 두는 시기입니다. 모든 평가를 한 번에 통과하려 하기보다, 내가 감당할 자리부터 분명히 하면 이후의 자리가 덜 흔들리는 시기입니다.",
    "인성": "이 20년에는 성과를 재촉하기보다 배움과 생각을 내 것으로 남기는 시간을 확보하는 시기입니다. 오래 남는 공부와 사람과의 신뢰를 모아 두면, 이후의 선택이 한결 넓어지는 시기입니다.",
    "재성": "이 20년에는 들어온 결과와 돈을 어디에 남길지 먼저 정해 두는 시기입니다. 눈에 보이는 성과만 쫓기보다 살림의 기반을 차근차근 모아 두면, 이후의 생활이 덜 흔들리는 시기입니다.",
    "식상": "이 20년에는 속에 있는 솜씨를 사람들 앞에 작은 결과로 남겨 두는 시기입니다. 완벽해진 뒤에 보여 주려 기다리기보다 만들고 다듬은 흔적을 모아 두면, 이후의 일이 자연스럽게 이어지는 시기입니다.",
    "비겁": "이 20년에는 내 몫을 분명히 하면서도 함께 갈 사람을 가려 두는 시기입니다. 비교와 경쟁에 힘을 다 쓰기보다 믿을 만한 동료와 내 자리를 모아 두면, 이후의 방향이 분명해지는 시기입니다.",
}

_REL_NOTE = {
    "충": "그 사이 자리와 소속이 크게 흔들립니다.",
    "합": "그 사이 사람과 역할이 한곳으로 모입니다.",
    "형": "그 사이 기준과 마음 사이에 마찰이 있습니다.",
    "파해": "그 사이 계획과 현실이 어긋납니다.",
    "반복": "그 사이 익숙한 모양이 한 번 더 돌아오는 흐름입니다.",
    "무관": "그 사이 환경의 결은 크게 뒤집히지 않고 속도만 달라집니다.",
}

# 카테고리 카드에 덧붙는 한 줄. 학업·교우·가정이 같은 문장을 공유하지 않는다.
_SLOTS = {
    "front": {
        "study": "이 구간의 학업은 배우는 방식을 익히며 시작하는 일입니다.",
        "friendship": "이 구간의 교우는 사람 사이에서 관계를 시작하는 일입니다.",
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
    "_prompt_v": "2026-10-20-twenty-voice",
    "groups": _GROUP_FLOW,
    "decades": _SIPSIN_DECADE,
    "relations": _REL_NOTE,
    "actions": _ACTION,
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


def core_continues(front_rel: str, back_rel: str, front_domains: Tuple[str, ...], back_domains: Tuple[str, ...]) -> bool:
    """환경(형충)과 핵심 영역이 같으면 20년 핵심 영역 하나다."""
    return front_rel == back_rel and tuple(front_domains) == tuple(back_domains)


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
    action = (db.get("actions") or {}).get(group) or db["actions"]["비겁"]
    return {
        "section_common": "20년의 공통 흐름",
        "section_front": _decade_title("첫 번째 10년", front_sipsin),
        "section_back": _decade_title("두 번째 10년", back_sipsin),
        "overview": _maybe_past(overview, back_past),
        "front": _maybe_past(front_text, front_past),
        "back": _maybe_past(back_text, back_past),
        "action_title": "이 20년을 잘 보내기 위한 행동 지침",
        "action_guide": _maybe_past(action, back_past),
        "tasks_title": "20년간 중요했던 일" if back_past else "이 20년에 중요한 일",
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
