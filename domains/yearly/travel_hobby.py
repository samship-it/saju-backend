"""여행운 + 취미운 통합.

정적 DB 두 칸을 여섯 섹션에 한 번씩만 넣는다.
이동이 센 해는 여행 문장이 전체 흐름을 맡고, 만드는 일이 센 해는 취미 문장이 맡는다.
혼자/함께는 여기서 한 번만 정하고, 반대되는 문단은 붙이지 않는다.
"""
from typing import Any, Dict, List, Optional

from core.constants import CHUNG, SAMHAP, YUKHAP
from core.sipsin import sipsin_group

_YEOKMA = {"寅", "申", "巳", "亥"}

# 전체 흐름 첫 문장. 키는 (이동이 센가, 취미가 센가).
_OPENING = {
    (True, True): (
        "올해는 몸을 움직여 떠나는 일과, 손에 잡히는 취미가 같이 살아나는 해예요. "
        "멀리 나갔다 돌아와 뭔가를 만드는 흐름이 잘 맞습니다."
    ),
    (True, False): (
        "올해는 자리를 지키기보다 장소를 바꾸며 숨통이 트이는 해예요. "
        "취미는 그 길 위에서 짧게 붙잡는 편이 편합니다."
    ),
    (False, True): (
        "올해는 멀리 떠나기보다, 가까운 자리에서 몸을 쓰고 만드는 일이 더 크게 열리는 해예요. "
        "여행은 그 취미를 환기하는 짧은 외출로 충분합니다."
    ),
    (False, False): (
        "올해는 큰 여행도 새로운 취미도 서두르지 않아도 되는 해예요. "
        "익숙한 길을 조금 벗어나는 정도면 충분합니다."
    ),
}

_COMPANY = {
    "solo": "올해는 혼자 움직이는 쪽이 더 잘 맞아요. 사람을 맞추느라 일정이 늘어지면 금방 지칩니다.",
    "together": "올해는 함께 나갈 때 흥이 살아나요. 혼자 버티기보다 한두 사람과 호흡을 맞추는 편이 편합니다.",
    "either": "혼자 몰입하는 시간과 함께 나가는 시간이 둘 다 필요해요. 지칠 때는 혼자, 심심할 때는 함께가 맞습니다.",
}

_FALLBACK_TRAVEL = {
    "one_line": "익숙한 길에서 한 걸음만 벗어나도 숨이 트이는 해",
    "keywords": ["환기"],
    "concept_object": "지도",
    "overall_flow": "올해 이동은 크게 벌리기보다 짧게 다녀오며 기분을 바꾸는 흐름이에요. 먼 일정보다 몸과 마음이 회복되는 거리를 고르면 충분합니다.",
    "travel_style": "도시를 천천히 걷거나, 물가나 숲에서 쉬는 짧은 여행이 잘 맞아요.",
    "travel_luck": "일정 끝을 비워 두면 예상 못 한 골목과 사람이 찾아옵니다.",
    "recommended_spots": "가까운 물가, 바람이 통하는 언덕, 처음 가 보는 동네 골목이 잘 맞아요.",
}
_FALLBACK_HOBBY = {
    "one_line": "손에 잡히는 것 하나가 한 해를 가볍게 만드는 해",
    "keywords": ["몰입"],
    "concept_object": "그림",
    "overall_flow": "올해 취미는 여러 개를 벌리기보다 이미 손이 가는 것 하나를 깊게 하는 흐름이에요. 거창한 시작보다 꾸준히 돌아오는 시간이 남습니다.",
    "active_activities": "걷기, 손그림, 사진, 간단한 악기처럼 바로 시작할 수 있는 활동이 잘 맞아요.",
    "solo_vs_group": "지칠 때는 혼자, 심심할 때는 한두 사람과 함께하는 편이 편해요.",
    "benefits": "꾸준히 돌아온 취미는 마음을 식혀 주고, 다음 계절의 계획을 가볍게 만들어 줍니다.",
}


def read_axes(saju: Dict[str, Any], year_ganji: str) -> Dict[str, Any]:
    """이동·취미·동행을 점수로만 가른다. 이 점수는 문장에 나가지 않는다."""
    day_b = saju.get("day_branch") or ""
    year_b = year_ganji[1] if isinstance(year_ganji, str) and len(year_ganji) >= 2 else ""
    sinsal = saju.get("sinsal") if isinstance(saju.get("sinsal"), dict) else {}
    derived = saju.get("derived") if isinstance(saju.get("derived"), dict) else {}
    power = derived.get("group_power") if isinstance(derived.get("group_power"), dict) else {}
    sewoon = saju.get("sewoon_sipsin") if isinstance(saju.get("sewoon_sipsin"), dict) else {}

    def grp(key: str) -> str:
        return sipsin_group(str(sewoon.get(key) or ""))

    move = 0
    if sinsal.get("has_yeokma"):
        move += 2
    if day_b in _YEOKMA or year_b in _YEOKMA:
        move += 2
    if day_b and year_b and frozenset((day_b, year_b)) in CHUNG:
        move += 1

    play = 0
    try:
        sik = float(power.get("식상") or 0)
        peer = float(power.get("비겁") or 0)
    except (TypeError, ValueError):
        sik, peer = 0.0, 0.0
    if sik >= 1.5:
        play += 2
    if grp("gan") == "식상" or grp("ji") == "식상":
        play += 2

    together = 0
    if grp("gan") == "비겁" or grp("ji") == "비겁":
        together += 2
    if peer >= sik and peer >= 1.5:
        together += 1
    paired = frozenset((day_b, year_b))
    if day_b and year_b and (paired in YUKHAP or any(day_b in g and year_b in g for g in SAMHAP)):
        together += 2

    if move >= 3 and together == 0:
        company = "solo"
    elif together >= 2 and move >= 3:
        company = "either"
    elif together >= 2:
        company = "together"
    elif play >= 2 and together == 0:
        company = "solo"
    else:
        company = "either"

    return {
        "move_high": move >= 3,
        "play_high": play >= 2,
        "company": company,
    }


def _tags(keywords) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in keywords or []:
        word = str(raw).strip().lstrip("#").strip()
        if not word or word in seen:
            continue
        seen.add(word)
        out.append(f"#{word}")
    return out


def _lean(text: str) -> str:
    solo = text.count("혼자")
    together = text.count("함께") + text.count("같이") + text.count("동호회") + text.count("그룹")
    if solo > together:
        return "solo"
    if together > solo:
        return "together"
    return "either"


def _body(src: Optional[dict], fallback: dict) -> dict:
    base = dict(fallback)
    if isinstance(src, dict):
        base.update({k: src.get(k) if src.get(k) not in (None, "", []) else base.get(k) for k in fallback})
        if src.get("keywords"):
            base["keywords"] = src.get("keywords")
    return base


def assemble(
    travel: Optional[dict],
    hobby: Optional[dict],
    *,
    move_high: bool,
    play_high: bool,
    company: str,
    timing_months: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """여섯 섹션. travel/hobby 원문 필드는 서로 다른 칸에만 들어간다."""
    t = _body(travel, _FALLBACK_TRAVEL)
    h = _body(hobby, _FALLBACK_HOBBY)
    if company not in _COMPANY:
        company = "either"
    months = [str(m).strip() for m in (timing_months or []) if str(m).strip()]

    lead_travel = move_high or not play_high
    lead_kw = _tags(t["keywords"] if lead_travel else h["keywords"])
    other_kw = _tags(h["keywords"] if lead_travel else t["keywords"])
    keywords: List[str] = []
    for word in lead_kw + other_kw:
        if word not in keywords:
            keywords.append(word)
    keywords = keywords[:4] or ["#환기"]

    parts = [_OPENING[(move_high, play_high)]]
    if move_high and play_high:
        parts.append(str(t["overall_flow"]))
        parts.append("여가와 취미는 그 이동을 집에 와서 이어 갑니다.")
        parts.append(str(h["overall_flow"]))
    elif move_high:
        parts.append(str(t["overall_flow"]))
    elif play_high:
        parts.append(str(h["overall_flow"]))
    else:
        parts.append(str(t["overall_flow"]))

    style = [str(t["travel_style"])]
    if not move_high:
        style.insert(0, "긴 일정보다 짧게 다녀오는 여행이 더 잘 맞아요.")

    spot = [str(t["recommended_spots"])]
    if months:
        when = ", ".join(months[:3])
        if move_high:
            spot.append(f"움직이기 좋은 시기는 {when} 무렵이에요.")
        else:
            spot.append(f"서두르지 말고 {when} 무렵에 짧게 다녀오는 편이 좋아요.")

    activity = [str(h["active_activities"])]
    if not play_high:
        activity.insert(0, "새로운 종목을 많이 벌리기보다, 이미 손이 가는 것 하나만 깊게 해보세요.")

    company_parts = [_COMPANY[company]]
    detail = str(h.get("solo_vs_group") or "")
    lean = _lean(detail)
    if detail and (company == "either" or lean == "either" or lean == company):
        company_parts.append(detail)

    if lead_travel:
        reward = [str(t["travel_luck"]), "돌아와서 손에 남는 것은 이렇습니다.", str(h["benefits"])]
    else:
        reward = [str(h["benefits"]), "길을 나설 때 따라오는 수확은 이렇습니다.", str(t["travel_luck"])]

    return {
        "symbol": {
            "keywords": keywords,
            "object": str(t["concept_object"] if lead_travel else h["concept_object"]),
            "headline": str(t["one_line"] if lead_travel else h["one_line"]),
        },
        "section_1_overall_flow": _join(parts),
        "section_2_travel_style": _join(style),
        "section_3_recommended_spot": _join(spot),
        "section_4_matched_activity": _join(activity),
        "section_5_solo_vs_together": _join(company_parts),
        "section_6_final_reward": _join(reward),
    }


def _join(parts: List[str]) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())
