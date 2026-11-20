"""혼자 보는 결혼운의 성향과 배우자 운.

배우자성의 정·편, 일지 기질, 오행 강약을 내부 근거로만 쓰고
기둥·글자 위치·용어는 문장에 넣지 않는다.
시주를 모르면 시각 기둥의 배우자성은 보지 않는다.
"""
from typing import Any, Dict, List, Sequence

from core.sipsin import sipsin_group

_POS_ORDER = (
    "year_gan", "year_ji", "month_gan", "month_ji", "day_ji", "hour_gan", "hour_ji",
)
_TONE_ORDER = ("정관", "편관", "정재", "편재")
_DECIDE_BOTH = {
    ("정관", "편관"): (
        "결혼을 결정할 때 상대에 대한 감정뿐 아니라 책임감과 현실적인 조건도 중요하게 생각합니다."
    ),
    ("정재", "편재"): (
        "결혼을 결정할 때 마음만이 아니라, 살림이 안정되고 각자의 일도 이어질 수 있는지를 중요하게 생각합니다."
    ),
}
_DECIDE_ONE = {
    "정관": "결혼을 결정할 때 감정이 좋은지만이 아니라, 약속을 지키고 책임을 질 수 있는지를 중요하게 생각합니다.",
    "편관": "결혼을 결정할 때 지금 편한지만이 아니라, 힘든 일이 생겨도 같이 버틸 수 있는지를 중요하게 생각합니다.",
    "정재": "결혼을 결정할 때 마음만이 아니라, 살림과 생활이 안정적인지를 중요하게 생각합니다.",
    "편재": "결혼을 결정할 때 마음만이 아니라, 각자 일을 하면서도 같이 살 수 있는지를 중요하게 생각합니다.",
}
_DECIDE_NONE = "결혼을 결정할 때 설레는 감정만이 아니라, 매일의 생활이 서로에게 편한지를 중요하게 생각합니다."
_WITH = {
    "비겁": "배우자와 서로의 방식대로 생활하면서도 같이 지내기를 바랍니다.",
    "식상": "배우자에게 하고 싶은 말을 숨기지 않고, 그 이야기를 나누며 가까워집니다.",
    "재성": "배우자와 생활의 현실적인 부분을 먼저 맞추고, 그 안에서 마음을 나누기를 바랍니다.",
    "관성": "배우자와 서로의 역할이 분명한 관계를 더 편하게 느낍니다.",
    "인성": "배우자의 마음을 먼저 살피고, 자신의 마음은 천천히 전합니다.",
}
_WITH_ROLE = "배우자와 서로 맡은 역할을 존중하고 안정적인 생활을 꾸려가기를 바랍니다."
_PALACE_WITH = {
    "정관": "같이 사는 생활에서 서로의 역할이 분명할 때 관계도 편해집니다.",
    "편관": "같이 사는 생활에서 힘든 일을 같이 견딜 수 있을 때 관계도 편해집니다.",
    "정재": "같이 사는 생활이 안정적일 때 마음도 따라옵니다.",
    "편재": "같이 사는 생활이 맞으면 마음도 따라오고, 맞지 않으면 관계도 멀어지기 쉽습니다.",
}
_WEAK = {
    "비겁": "다만 자신의 생각과 방식이 분명해 상대와 의견이 다를 때 타협하는 데 시간이 걸릴 수 있습니다.",
    "식상": "다만 하고 싶은 말이 앞서 상대가 생각할 시간을 놓칠 수 있습니다.",
    "재성": "다만 현실적인 조건을 맞추느라 상대의 서운함을 나중에야 알아볼 수 있습니다.",
    "관성": "다만 역할을 지키려다 상대가 편하게 쉴 시간을 주지 못할 수 있습니다.",
    "인성": "다만 상대에게 맞추느라 자신의 불편을 너무 늦게 말할 수 있습니다.",
}
_STRONG = {
    "목": "하고 싶은 일의 방향을 분명하게 정하는 편",
    "화": "자신의 감정과 생각을 분명하게 표현하는 편",
    "토": "한번 시작한 생활을 쉽게 그만두지 않는 편",
    "금": "해야 할 일을 기준에 맞춰 정리하는 편",
    "수": "상대의 상황과 기분을 먼저 살피는 편",
}
_COMPLEMENT = {
    "목": "앞으로의 계획을 같이 정하는",
    "화": "감정을 숨기지 않고 표현하는",
    "토": "생활을 꾸준히 챙겨 주는",
    "금": "현실적인 문제를 차분하게 해결하는",
    "수": "말이 막힐 때 상대의 마음을 먼저 헤아리는",
}
_TOGETHER = {
    "비겁": "서로의 생활 방식과 독립성을 존중하는 사람이라면 좋은 관계를 만들어 갈 수 있습니다.",
    "식상": "내가 꺼낸 이야기를 끝까지 들어 주는 사람이라면 같이 지내기 좋습니다.",
    "재성": "생활의 조건만 보지 않고 상대의 마음도 살피는 사람이라면 같이 지내기 좋습니다.",
    "관성": "역할이 달라도 다정하게 대해 주는 사람이라면 같이 지내기 좋습니다.",
    "인성": "나의 의견도 물어 보는 사람이라면 같이 지내기 좋습니다.",
}
_TOGETHER_TRUST = (
    "생각에 그치지 않고 행동으로 신뢰를 보여주며, "
    "서로의 생활 방식과 독립성을 존중하는 사람이라면 좋은 관계를 만들어 갈 수 있습니다."
)
_ELEM_ORDER = ("목", "화", "토", "금", "수")


def build_marriage_depth(saju: Dict[str, Any]) -> Dict[str, str]:
    """솔로 결혼운에만 붙인다. 키가 비면 그 항목은 응답에 넣지 않는다."""
    facts = _facts(saju)
    out = {
        "marriage_disposition": _disposition(facts),
        "spouse_fortune": _spouse_fortune(facts),
    }
    return {key: text for key, text in out.items() if text.strip()}


def _facts(saju: Dict[str, Any]) -> Dict[str, Any]:
    spouse = saju.get("spouse_star") or {}
    sipsin = saju.get("sipsin") or {}
    time_known = bool(saju.get("birth_time_known"))
    positions = [
        pos for pos in _POS_ORDER
        if pos in (spouse.get("found_positions") or [])
        and (time_known or not pos.startswith("hour"))
        and pos in sipsin
    ]
    group = sipsin_group(sipsin.get("day_ji", ""))
    return {
        "life_group": group if group in _WITH else "",
        "yongsin": list((saju.get("strength") or {}).get("yongsin") or [])[:2],
        "tones": _tones(sipsin, positions),
        "elem_power": dict((saju.get("strength") or {}).get("elem_power") or {}),
        "on_palace": "day_ji" in positions,
    }


def _tones(sipsin: Dict[str, Any], positions: Sequence[str]) -> List[str]:
    found = {sipsin.get(pos, "") for pos in positions}
    return [name for name in _TONE_ORDER if name in found]


def _disposition(facts: Dict[str, Any]) -> str:
    tones: List[str] = facts["tones"]
    life = facts["life_group"]
    pair = tuple(tones[:2])
    if pair in _DECIDE_BOTH:
        decide = _DECIDE_BOTH[pair]
    elif tones:
        decide = _DECIDE_ONE[tones[0]]
    else:
        decide = _DECIDE_NONE
    if facts["on_palace"] and tones:
        together = _PALACE_WITH[tones[0]]
    elif "정관" in tones and life == "비겁":
        together = _WITH_ROLE
    else:
        together = _WITH.get(life, "배우자와 매일의 생활이 서로에게 편한 관계를 바랍니다.")
    weak = _WEAK.get(life, "다만 기준이 늦게 정해져 결정을 미루기 쉽습니다.")
    return " ".join((decide, together, weak))


def _spouse_fortune(facts: Dict[str, Any]) -> str:
    power = {elem: float(facts["elem_power"].get(elem, 0)) for elem in _ELEM_ORDER}
    yong = set(facts["yongsin"])
    ranked = sorted(power, key=lambda elem: (power[elem], 0 if elem in yong else 1, elem))
    primary = ranked[0]
    strong = max(power, key=lambda elem: (power[elem], elem))
    secondary = ""
    if power[ranked[1]] - power[primary] <= 0.5 and ranked[1] != strong:
        secondary = ranked[1]
    gap = {primary, secondary} if secondary else {primary}
    if gap == {"목", "금"}:
        lack = "관계를 안정적으로 이끌고 현실적인 문제를 차분하게 해결하는"
    else:
        lack = _COMPLEMENT[primary]
    if power[strong] - power[primary] >= 0.8:
        opening = f"{_STRONG[strong]}이므로, 상대에게는 {lack} 성향이 잘 어울립니다."
    else:
        opening = f"상대에게는 {lack} 성향이 잘 어울립니다."
    sentences = [opening]
    if secondary and gap != {"목", "금"}:
        sentences.append(f"{_COMPLEMENT[secondary]} 사람이라면 같이 살 때 도움이 됩니다.")
    if gap == {"목", "금"} and not _trust_pair(facts):
        sentences.append("감정의 표현은 내가 맡고, 계획과 현실적인 정리는 상대가 맡아 주면 잘 맞습니다.")
    else:
        sentences.append(_together_line(facts))
    return " ".join(sentences)


def _trust_pair(facts: Dict[str, Any]) -> bool:
    return "정관" in facts["tones"] and facts["life_group"] == "비겁" and not facts["on_palace"]


def _together_line(facts: Dict[str, Any]) -> str:
    if _trust_pair(facts):
        return _TOGETHER_TRUST
    return _TOGETHER.get(
        facts["life_group"],
        "같이 사는 생활을 현실적으로 함께 만드는 사람이라면 같이 지내기 좋습니다.",
    )
