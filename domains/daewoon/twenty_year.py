"""20년 연속 십성 묶음의 문장 DB.

키는 십성 대분류와 앞·뒤 10년의 형충회합이다. 누구의 지금 나이인지는
요청 때 나이를 넣어 시제만 바꾼다. 본문에는 십신명·운 이름을 넣지 않는다.
배지 문구만 그룹 이름을 쓴다.
"""
import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

from domains.daewoon.axis import to_past

ARC_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "twenty_year_arc_db.json")

# 사용자 본문용 장면. 그룹 이름 자체는 넣지 않는다.
_GROUP_SCENE = {
    "관성": "책임과 평가, 소속의 기준",
    "인성": "배움과 보호, 생각을 쌓는 일",
    "재성": "돈과 성과, 현실에서 거두는 결과",
    "식상": "표현과 솜씨, 만들어 내는 일",
    "비겁": "나의 힘과 동료, 나란히 서는 경쟁",
}

_FRONT = {
    "충": "{ages}는 자리와 소속이 흔들리는 가운데 기준을 익히며 단련을 시작하는 구간입니다.",
    "합": "{ages}는 사람과 역할이 한곳으로 모이는 가운데 그 자리를 배우며 시작하는 구간입니다.",
    "형": "{ages}는 기준과 마음 사이에 마찰이 있는 가운데 그 긴장을 견디며 단련을 시작하는 구간입니다.",
    "파해": "{ages}는 계획과 현실이 어긋나는 가운데 길을 찾으며 단련을 시작하는 구간입니다.",
    "반복": "{ages}는 익숙한 모양이 다시 오는 가운데 기본을 다지며 단련을 시작하는 구간입니다.",
    "무관": "{ages}는 속도만 달라지는 가운데 자기 방식을 만들며 단련을 시작하는 구간입니다.",
}

_BACK = {
    "충": "{ages}는 흔들리던 자리가 갈라지며 앞 10년의 단련이 어느 쪽으로 안착할지 결실이 갈리는 구간입니다.",
    "합": "{ages}는 모아 둔 역할이 권한으로 모이며 앞 10년의 단련이 자리에 안착하는 구간입니다.",
    "형": "{ages}는 마찰을 지나 기준이 정해지며 앞 10년의 단련이 자기 방식으로 안착하는 구간입니다.",
    "파해": "{ages}는 어긋나던 계획이 현실에 맞게 정리되며 앞 10년의 단련이 결실로 매듭지어지는 구간입니다.",
    "반복": "{ages}는 같은 주제가 한 번 더 돌아와 앞 10년에 익힌 것을 매듭짓고 안착하는 구간입니다.",
    "무관": "{ages}는 큰 전환 없이 쌓인 무게가 드러나며 앞 10년의 단련이 결실로 안착하는 구간입니다.",
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
    "_prompt_v": "2026-10-19-twenty-arc",
    "groups": _GROUP_SCENE,
    "overview": (
        "이 20년은 {scene}이 한 호흡으로 이어지는 큰 풍경입니다. "
        "앞 10년은 그 주제를 단련하며 시작하는 쪽입니다. "
        "뒤 10년은 같은 주제 위에서 자리를 잡아 결실을 매듭짓는 쪽입니다."
    ),
    "front": _FRONT,
    "back": _BACK,
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


def build_twenty_year_story(
    group: str,
    front_rel: str,
    back_rel: str,
    front_ages: Tuple[int, int],
    back_ages: Tuple[int, int],
    front_past: bool,
    back_past: bool,
) -> Dict[str, Any]:
    """20년 총평 + 전반 10년의 단련 + 후반 10년의 안착. 10년 문장을 두 번 붙이지 않는다."""
    db = load_arc_db()
    scene = db["groups"].get(group) or db["groups"]["비겁"]
    overview = db["overview"].format(scene=scene)
    front = db["front"].get(front_rel) or db["front"]["무관"]
    back = db["back"].get(back_rel) or db["back"]["무관"]
    front_text = front.format(ages=_age_label(*front_ages))
    back_text = back.format(ages=_age_label(*back_ages))
    return {
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
    return " ".join(part for part in (story.get("overview"), story.get("front"), story.get("back")) if part)
