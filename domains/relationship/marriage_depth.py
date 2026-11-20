"""혼자 보는 결혼운 뒤에 붙는 세 문단.

점수는 marriage_10year_window 결과를 그대로 읽고, 다시 매기지 않는다.
성향과 배우자 운은 배우자성의 정·편, 일지 기질, 오행 강약을 내부 근거로만 쓰고
기둥·글자 위치·용어는 문장에 넣지 않는다.
시주를 모르면 시각 기둥은 시기 문장에도 넣지 않는다.
"""
from typing import Any, Dict, List, Optional, Sequence

from core.sipsin import calculate_sipsin, sipsin_group

_POS = {
    "year_gan": "태어난 해의 기둥에서 위쪽 글자",
    "year_ji": "태어난 해의 기둥에서 아래쪽 글자",
    "month_gan": "태어난 달의 기둥에서 위쪽 글자",
    "month_ji": "태어난 달의 기둥에서 아래쪽 글자",
    "day_ji": "태어난 날의 기둥에서 아래쪽 글자",
    "hour_gan": "태어난 시각의 기둥에서 위쪽 글자",
    "hour_ji": "태어난 시각의 기둥에서 아래쪽 글자",
}
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
_FLAG = {
    "배우자성 세운": "인연이 들어오는 표시",
    "일지 육합": "손발이 맞는 표시",
    "일지 삼합": "폭이 넓어지는 표시",
    "일지 충": "환경이 바뀌는 표시",
    "도화 세운": "새 만남이 많아지는 표시",
    "용신 세운": "나에게 유리한 조건",
}
_FLAG_ORDER = (
    "배우자성 세운", "일지 육합", "일지 삼합", "일지 충", "도화 세운", "용신 세운",
)
_WEIGHT = {
    "배우자성 세운": 16,
    "일지 육합": 14,
    "일지 삼합": 12,
    "일지 충": -14,
    "도화 세운": 6,
    "용신 세운": 8,
}
_PILLAR_KEY = {"year": "year", "month": "month", "day": "day", "hour": "time"}


def build_marriage_depth(saju: Dict[str, Any], years: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """솔로 결혼운에만 붙인다. 키가 비면 그 항목은 응답에 넣지 않는다."""
    facts = _facts(saju)
    rows = [r for r in years if isinstance(r, dict) and r.get("year")]
    out = {
        "marriage_disposition": _disposition(facts),
        "spouse_fortune": _spouse_fortune(facts, rows),
        "timing_depth": _timing(facts, rows),
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
        "saju": saju,
        "time_known": time_known,
        "female": (spouse.get("spouse_star_group") == "관성"),
        "positions": positions,
        "sipsin": sipsin,
        "life_group": group if group in _WITH else "",
        "day_branch": saju.get("day_branch") or "",
        "yongsin": list((saju.get("strength") or {}).get("yongsin") or [])[:2],
        "has_dohwa": bool((saju.get("sinsal") or {}).get("has_dohwa")),
        "day_master": saju.get("day_master") or "",
        "spouse_group": spouse.get("spouse_star_group") or "",
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


def _spouse_fortune(facts: Dict[str, Any], rows: Sequence[Dict[str, Any]]) -> str:
    del rows
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


def _timing(facts: Dict[str, Any], rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    ranked = sorted(rows, key=lambda row: (-int(row.get("strength") or 0), int(row["year"])))
    top = ranked[:3]
    top_years = {row["year"] for row in top}
    sentences = [
        "점수는 기존 계산 그대로입니다. 다시 매기지 않았습니다.",
        "점수가 낮은 해는 결혼이 안 되는 해가 아니고, 점수가 가장 높은 해도 그 해에 결혼이 확정된다는 뜻은 아닙니다.",
    ]
    for index, row in enumerate(top):
        sentences.extend(_year_block(
            facts, row, rows,
            ranked[index + 1] if index + 1 < len(ranked) else None,
            deep=True, lead=index == 0,
        ))
    rest = [row for row in rows if row["year"] not in top_years]
    sentences.extend(_rest(facts, rest, rows))
    return " ".join(sentences)


def _year_block(facts, row, rows, nxt, deep: bool, lead: bool = False) -> List[str]:
    year = int(row["year"])
    score = int(row.get("strength") or 0)
    reasons = list(row.get("reasons") or [])
    block = [f"{year}년은 {score}점입니다. {_reading(reasons, rows, score)}"]
    if lead and len(reasons) >= 3 and sum(1 for item in rows if list(item.get("reasons") or []) == reasons) == 1:
        label = {3: "세 표시", 4: "네 표시"}.get(len(reasons), f"{len(reasons)}개 표시")
        block.append(f"이 {label}가 한 해에 모인 것은 이 10년에서 {year}년뿐입니다.")
    if deep and nxt is not None:
        gap = _gap_sentence(row, nxt)
        if gap:
            block.append(gap)
    if _both_spouse(facts, row):
        block.append(
            f"{year}년은 위쪽 글자와 아래쪽 글자가 모두 결혼 상대를 가리킵니다. "
            f"기존 점수는 그 표시를 한 번만 더합니다. 그래서 {score}점입니다."
        )
    if "도화 세운" in reasons and not facts["has_dohwa"]:
        block.append("새 만남이 많아지는 표시는 사주에 항상 붙어 있지 않고, 이 해에 켜집니다.")
    if deep:
        block.extend(_natal_links(facts, row))
    return block


def _rest(facts, rows: Sequence[Dict[str, Any]], all_rows: Sequence[Dict[str, Any]]) -> List[str]:
    said: Dict[tuple, int] = {}
    out = []
    for row in rows:
        year = int(row["year"])
        score = int(row.get("strength") or 0)
        reasons = list(row.get("reasons") or [])
        key = (score, tuple(reasons))
        if key in said:
            out.append(f"{year}년은 {said[key]}년과 같은 {score}점이고, 표시도 같습니다.")
            continue
        said[key] = year
        out.append(f"{year}년은 {score}점입니다. {_reading(reasons, all_rows, score)}")
        if "도화 세운" in reasons and not facts["has_dohwa"]:
            out.append("새 만남이 많아지는 표시는 사주에 항상 붙어 있지 않고, 이 해에 켜집니다.")
    return out


def _reading(reasons: Sequence[str], rows: Sequence[Dict[str, Any]], score: Optional[int] = None) -> str:
    found = set(reasons)
    if not found:
        return "이 계산이 보는 결혼 표시가 없습니다. 그 해를 나쁜 해로 본 것은 아닙니다."
    names = [_FLAG[code] for code in _FLAG_ORDER if code in found]
    if len(names) == 1:
        line = f"{names[0]}만 있습니다."
    else:
        line = f"{_join(names)}{_subject(names[-1])} 함께 있습니다."
    extra = []
    if found == {"용신 세운"}:
        extra.append("만남, 발전, 결정 어느 쪽으로도 기울지 않습니다.")
    elif found == {"도화 세운"}:
        extra.append("매듭이나 결정의 근거는 이 점수에 없습니다.")
    elif "일지 충" in found and "배우자성 세운" in found:
        versus = _versus_favorable_only(reasons, rows, score)
        if versus:
            extra.append(versus)
        extra.append("그 해의 변화나 이동을 결혼 결정으로 읽지는 않습니다.")
    elif "일지 삼합" in found and "배우자성 세운" not in found:
        extra.append("인연이 들어오는 표시는 없습니다. 폭이 넓어지는 해에 가깝고, 그 해에 결혼이 확정된다고 읽지는 않습니다.")
    elif "일지 육합" in found and "배우자성 세운" not in found:
        extra.append("인연이 들어오는 표시는 없습니다.")
    elif "배우자성 세운" in found and ("일지 육합" in found or "일지 삼합" in found) and "일지 충" not in found and "도화 세운" not in found:
        extra.append(
            "새 만남만의 해로 읽히지 않습니다. "
            "새 인연이 형태를 갖추거나, 이미 있는 인연이 배우자 모습으로 구체화되는 쪽에 가깝습니다. "
            "어느 쪽인지는 그 해의 실제 인연이 정합니다."
        )
    elif "배우자성 세운" in found and "일지 육합" not in found and "일지 삼합" not in found and "일지 충" not in found:
        extra.append("인연의 문이 열리는 해이고, 손발이 맞거나 폭이 넓어지는 표시는 없습니다.")
    return " ".join([line, *extra])


def _versus_favorable_only(reasons: Sequence[str], rows: Sequence[Dict[str, Any]], score: Optional[int]) -> str:
    if score is None or set(reasons) != {"배우자성 세운", "일지 충", "용신 세운"}:
        return ""
    if _raw(reasons) != score:
        return ""
    peers = [row for row in rows if list(row.get("reasons") or []) == ["용신 세운"]]
    if not peers:
        return ""
    peer_score = int(peers[0].get("strength") or 0)
    if any(int(row.get("strength") or 0) != peer_score for row in peers) or peer_score == score:
        return ""
    diff = score - peer_score
    direction = "높습니다" if diff > 0 else "낮습니다"
    return (
        f"환경이 바뀌는 표시가 인연 표시의 점수를 대부분 깎아, "
        f"유리한 조건만 있는 {_years([int(row['year']) for row in peers])}의 {peer_score}점보다 "
        f"{abs(diff)}점 {direction}."
    )


def _gap_sentence(higher: Dict[str, Any], lower: Dict[str, Any]) -> str:
    high_reasons = list(higher.get("reasons") or [])
    low_reasons = list(lower.get("reasons") or [])
    if _raw(high_reasons) != int(higher.get("strength") or 0):
        return ""
    if _raw(low_reasons) != int(lower.get("strength") or 0):
        return ""
    gap = int(higher.get("strength") or 0) - int(lower.get("strength") or 0)
    only_high = [code for code in _FLAG_ORDER if code in high_reasons and code not in low_reasons]
    only_low = [code for code in _FLAG_ORDER if code in low_reasons and code not in high_reasons]
    delta = sum(_WEIGHT[code] for code in only_high) - sum(_WEIGHT[code] for code in only_low)
    if gap <= 0 or delta != gap:
        return ""
    high_names = _join([_FLAG[code] for code in only_high])
    low_names = _join([_FLAG[code] for code in only_low])
    if only_high and not only_low:
        return (
            f"{gap}점 차이는, {high_names}{_subject(high_names)} "
            f"{int(higher['year'])}년에만 있는 것과 같습니다."
        )
    if only_high and only_low:
        return (
            f"{gap}점 차이는, {int(higher['year'])}년에는 {high_names}{_subject(high_names)} 있고 "
            f"{int(lower['year'])}년에는 {low_names}{_subject(low_names)} 있는 것과 같습니다."
        )
    return ""


def _natal_links(facts: Dict[str, Any], row: Dict[str, Any]) -> List[str]:
    ganji = str(row.get("ganji") or "")
    if len(ganji) < 2:
        return []
    gan, ji = ganji[0], ganji[1]
    year = int(row["year"])
    reasons = list(row.get("reasons") or [])
    lines = []
    for pos in facts["positions"]:
        if pos.endswith("gan") and _glyph(facts["saju"], pos) == gan:
            lines.append(f"{year}년의 위쪽 글자는 {_POS[pos]}와 같습니다.")
            break
    matched_branch = False
    for pos in facts["positions"]:
        if pos.endswith("ji") and _glyph(facts["saju"], pos) == ji:
            lines.append(f"{year}년의 아래쪽 글자는 {_POS[pos]}와 같습니다.")
            matched_branch = True
            break
    hap = _hap_line(year, reasons)
    if hap:
        lines.append(hap)
    elif matched_branch:
        lines.append("그 글자는 함께 사는 생활을 읽는 글자와 맞물리거나 부딪히지 않습니다.")
    if facts["life_group"] == "비겁" and any(code in reasons for code in ("일지 육합", "일지 삼합", "일지 충")):
        if "일지 충" in reasons:
            lines.append(
                "이 부딪힘은 결혼 상대를 가리키는 글자끼리의 일이 아니라, "
                "본인의 생활 글자와 그 해가 부딪히는 쪽입니다."
            )
        elif "일지 삼합" in reasons:
            lines.append(
                "이 이어짐은 결혼 상대를 가리키는 글자끼리의 결합이 아니라, "
                "본인의 생활 글자와 그 해가 폭으로 이어지는 쪽입니다."
            )
        else:
            lines.append(
                "이 맞물림은 결혼 상대를 가리키는 글자끼리의 결합이 아니라, "
                "본인의 생활 글자와 그 해가 손발을 맞추는 쪽입니다."
            )
    return lines


def _hap_line(year: int, reasons: Sequence[str]) -> str:
    if "일지 육합" in reasons:
        return f"{year}년의 아래쪽 글자는 함께 사는 생활을 읽는 글자와 손발이 맞습니다."
    if "일지 삼합" in reasons:
        return f"{year}년의 아래쪽 글자는 함께 사는 생활을 읽는 글자와 폭으로 이어집니다."
    if "일지 충" in reasons:
        return f"{year}년의 아래쪽 글자는 함께 사는 생활을 읽는 글자와 부딪힙니다."
    return ""


def _both_spouse(facts: Dict[str, Any], row: Dict[str, Any]) -> bool:
    group = facts["spouse_group"]
    ganji = str(row.get("ganji") or "")
    master = facts["day_master"]
    if not group or len(ganji) < 2 or not master:
        return False
    gan_group = sipsin_group(calculate_sipsin(master, ganji[0], is_gan=True))
    ji_group = sipsin_group(calculate_sipsin(master, ganji[1], is_gan=False))
    return gan_group == group and ji_group == group



def _glyph(saju: Dict[str, Any], pos: str) -> str:
    slot = _PILLAR_KEY.get(pos.split("_")[0], "")
    gz = (saju.get("birth_ganji") or {}).get(slot) or ""
    if len(gz) < 2 or gz == "미정":
        return ""
    return gz[0] if pos.endswith("gan") else gz[1]


def _raw(reasons: Sequence[str]) -> int:
    return 50 + sum(_WEIGHT.get(code, 0) for code in reasons)


def _years(years: Sequence[int]) -> str:
    labels = [f"{year}년" for year in years]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]}과 {labels[1]}"
    return ", ".join(labels[:-1]) + f"과 {labels[-1]}"


def _batchim(word: str) -> bool:
    if not word:
        return False
    code = ord(word[-1])
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


def _subject(word: str) -> str:
    return "이" if _batchim(word) else "가"


def _wa(word: str) -> str:
    return "과" if _batchim(word) else "와"


def _join(words: Sequence[str]) -> str:
    items = [word for word in words if word]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]}{_wa(items[0])} {items[1]}"
    return ", ".join(items[:-1]) + f"{_wa(items[-2])} {items[-1]}"
