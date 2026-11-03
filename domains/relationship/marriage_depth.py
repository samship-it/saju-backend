"""혼자 보는 결혼운 뒤에 붙는 세 문단.

점수는 marriage_10year_window 결과를 그대로 읽고, 다시 매기지 않는다.
원국에서 쓰는 사실은 배우자 글자의 위치, 그 글자의 정·편 차이,
함께 사는 생활을 읽는 글자(일지)의 기질, 지지의 해, 용신 두 글자와의 겹침뿐이다.
시주를 모르면 시각 기둥은 문장에 넣지 않는다.
"""
from typing import Any, Dict, List, Optional, Sequence

from core.constants import GAN_ELEM, JI_ELEM
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
_BRANCH_POS = {
    "year": "태어난 해의 기둥에서 아래쪽 글자",
    "month": "태어난 달의 기둥에서 아래쪽 글자",
    "day": "태어난 날의 기둥에서 아래쪽 글자",
    "hour": "태어난 시각의 기둥에서 아래쪽 글자",
}
_TONE = {
    "정관": "책임과 명분을 맞춰 가는 쪽",
    "편관": "압박이 먼저 닿고 속도가 빠른 쪽",
    "정재": "살림과 현실 조건을 안정적으로 맞춰 가는 쪽",
    "편재": "바깥일과 변동이 먼저 오는 쪽",
}
_LIFE = {
    "비겁": (
        "거기에는 본인과 같은 기질이 있습니다.",
        "생활의 리듬을 스스로 지키려는 힘이 있습니다.",
        "내가 정한 속도가 상대의 방식보다 먼저 나오기 쉽습니다.",
    ),
    "식상": (
        "거기에는 풀어내고 만들어 내는 기질이 있습니다.",
        "하고 싶은 말을 생활 안으로 끌어오는 힘이 있습니다.",
        "내 표현이 상대의 속도보다 먼저 나오기 쉽습니다.",
    ),
    "재성": (
        "거기에는 현실 조건과 살림을 챙기는 기질이 있습니다.",
        "생활을 구체적인 조건으로 정리하려는 힘이 있습니다.",
        "조건부터 맞추려다 상대의 감정을 뒤로 두기 쉽습니다.",
    ),
    "관성": (
        "거기에는 책임과 명분을 세우는 기질이 있습니다.",
        "생활을 약속과 책임으로 정리하려는 힘이 있습니다.",
        "명분을 먼저 세우다 상대가 숨 쉴 틈을 좁히기 쉽습니다.",
    ),
    "인성": (
        "거기에는 받아들이고 배우려는 기질이 있습니다.",
        "생활을 이해와 돌봄으로 지키려는 힘이 있습니다.",
        "맞추는 데 익숙해져 내 쪽 의사를 늦게 꺼내기 쉽습니다.",
    ),
}
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
        "life_group": group if group in _LIFE else "",
        "day_branch": saju.get("day_branch") or "",
        "yongsin": list((saju.get("strength") or {}).get("yongsin") or [])[:2],
        "has_dohwa": bool((saju.get("sinsal") or {}).get("has_dohwa")),
        "day_master": saju.get("day_master") or "",
        "spouse_group": spouse.get("spouse_star_group") or "",
    }


def _disposition(facts: Dict[str, Any]) -> str:
    positions: List[str] = facts["positions"]
    sentences: List[str] = []
    if not positions:
        sentences.append(
            "결혼 상대를 가리키는 글자는 지금 읽는 기둥에는 없습니다. "
            "없다고 해서 결혼이 어렵다는 뜻은 아닙니다."
        )
    else:
        same = _same_element(facts)
        opener = f"결혼 상대를 가리키는 글자가 {_place(len(positions))}에 있습니다."
        if same and len(positions) > 1:
            opener += " 그 글자들은 같은 성질입니다."
        elif len({_elem(facts, pos) for pos in positions}) > 1:
            opener += " 그 글자들의 성질은 서로 다릅니다."
        sentences.append(opener)
        sentences.extend(_tone_sentences(facts))

    life = _life_fact(facts)
    if life:
        sentences.append(life)
    copied = _copied_glyph(facts)
    if copied:
        sentences.append(copied)
    if _yongsin_overlap(facts):
        noun = "그 글자가" if len(positions) == 1 else "그 글자들이"
        sentences.append(
            f"{noun} 가리키는 성질은, 연도 점수가 나에게 유리한 조건으로 더하는 성질과 겹칩니다."
        )
    for line in _hae_lines(facts, hedge=False):
        sentences.append(line)

    reading = _disposition_reading(facts)
    if reading:
        sentences.append("이렇게 읽힐 수 있습니다. " + reading)
    return " ".join(sentences)


def _spouse_fortune(facts: Dict[str, Any], rows: Sequence[Dict[str, Any]]) -> str:
    positions: List[str] = facts["positions"]
    sentences: List[str] = []
    if not positions:
        where = "태어난 해의 기둥과 태어난 달의 기둥, 태어난 날의 기둥"
        if facts["time_known"]:
            where += ", 태어난 시각의 기둥"
        sentences.append(f"결혼 상대를 가리키는 글자는 {where}에서 확인되지 않습니다.")
        sentences.append("없다고 해서 결혼이 어렵다는 뜻은 아닙니다.")
        lit = [r["year"] for r in rows if "배우자성 세운" in (r.get("reasons") or [])]
        if lit:
            sentences.append(f"그 표시가 켜지는 해는 {_years(lit)}입니다.")
        else:
            sentences.append("이 10년 안에는 그 표시가 켜지는 해가 없습니다.")
    else:
        labels = [_POS[pos] for pos in positions]
        if len(labels) == 1:
            sentences.append(f"결혼 상대를 가리키는 글자는 {labels[0]}에 있습니다.")
        else:
            sentences.append(
                f"결혼 상대를 가리키는 글자는 {_join(labels)}, 이 {_place(len(labels))}입니다."
            )
        if "day_ji" in positions:
            sentences.append("함께 사는 생활을 읽는 글자에도 있습니다. 그 글자는 태어난 날의 기둥에서 아래쪽입니다.")
        else:
            tail = "함께 사는 생활을 읽는 글자, 곧 태어난 날의 기둥에서 아래쪽에는 없습니다."
            if facts["life_group"] == "비겁":
                tail += " 거기에는 본인과 같은 기질이 있습니다."
            sentences.append(tail)
        if facts["time_known"]:
            hour_hit = [pos for pos in ("hour_gan", "hour_ji") if pos in positions]
            if not hour_hit:
                sentences.append("태어난 시각의 기둥 위쪽과 아래쪽에는 없습니다.")
            elif len(hour_hit) == 2:
                sentences.append("태어난 시각의 기둥 위쪽과 아래쪽에도 있습니다.")
            else:
                sentences.append(f"{_POS[hour_hit[0]]}에도 있습니다.")
        if "day_ji" not in positions:
            if facts["female"]:
                sentences.append(
                    "함께 사는 생활의 감각과 결혼 상대 조건이 한 글자에 붙어 있지 않습니다. "
                    "가깝다는 느낌과, 책임과 명분이 맞는지를 따로 보게 됩니다."
                )
            else:
                sentences.append(
                    "함께 사는 생활의 감각과 결혼 상대 조건이 한 글자에 붙어 있지 않습니다. "
                    "가깝다는 느낌과, 살림과 현실 조건이 맞는지를 따로 보게 됩니다."
                )
        sentences.append(
            "어느 기둥에 있는지는 어디서 만나는지를 알려 주지 않습니다. "
            "가족 안에서나 일터에서 만난다는 뜻으로 쓰지 않습니다."
        )
    return " ".join(sentences)


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


def _tone_sentences(facts: Dict[str, Any]) -> List[str]:
    grouped: Dict[str, List[str]] = {}
    order: List[str] = []
    for pos in facts["positions"]:
        tone = _TONE.get(facts["sipsin"].get(pos, ""))
        if not tone:
            continue
        if tone not in grouped:
            grouped[tone] = []
            order.append(tone)
        grouped[tone].append(_POS[pos])
    lines = []
    for tone in order:
        labels = grouped[tone]
        lines.append(f"{_join(labels)}{_un(labels[-1])} {tone}입니다.")
    return lines


def _life_fact(facts: Dict[str, Any]) -> str:
    if not facts["day_branch"]:
        return ""
    head = "함께 사는 생활을 읽는 글자는 태어난 날의 기둥에서 아래쪽입니다."
    if "day_ji" in facts["positions"]:
        return head + " 그 글자가 결혼 상대를 가리킵니다."
    life = _LIFE.get(facts["life_group"])
    if not life:
        return head
    return head + " " + life[0]


def _copied_glyph(facts: Dict[str, Any]) -> str:
    day = facts["day_branch"]
    if not day:
        return ""
    pillars = (facts["saju"].get("birth_ganji") or {})
    labels = []
    for slot, label in (("year", "태어난 해의 기둥에서 아래쪽"), ("month", "태어난 달의 기둥에서 아래쪽")):
        gz = pillars.get(slot) or ""
        if len(gz) > 1 and gz[1] == day:
            labels.append(label)
    if facts["time_known"]:
        gz = pillars.get("time") or ""
        if len(gz) > 1 and gz != "미정" and gz[1] == day:
            labels.append("태어난 시각의 기둥에서 아래쪽")
    if not labels:
        return ""
    return f"{_join(labels)}에도 같은 글자가 있어, 그 기질이 한 칸에만 있지 않습니다."


def _disposition_reading(facts: Dict[str, Any]) -> str:
    parts: List[str] = []
    tones = []
    for pos in facts["positions"]:
        tone = _TONE.get(facts["sipsin"].get(pos, ""))
        if tone and tone not in tones:
            tones.append(tone)
    if facts["female"] and len(tones) == 2:
        parts.append(
            "결혼을 저울질할 때 이 사주가 더 보는 것은, 책임과 명분이 서는가와 "
            "속도가 빠른 압박을 감당할 수 있는가입니다."
        )
    elif facts["female"] and tones == ["책임과 명분을 맞춰 가는 쪽"]:
        parts.append("결혼을 저울질할 때 이 사주가 더 보는 것은, 책임과 명분이 서는가입니다.")
    elif facts["female"] and tones == ["압박이 먼저 닿고 속도가 빠른 쪽"]:
        parts.append("결혼을 저울질할 때 이 사주가 더 보는 것은, 속도가 빠른 압박을 감당할 수 있는가입니다.")
    elif (not facts["female"]) and tones == ["살림과 현실 조건을 안정적으로 맞춰 가는 쪽"]:
        parts.append("결혼을 저울질할 때 이 사주가 더 보는 것은, 살림과 현실 조건이 서는가입니다.")
    elif (not facts["female"]) and tones == ["바깥일과 변동이 먼저 오는 쪽"]:
        parts.append("결혼을 저울질할 때 이 사주가 더 보는 것은, 바깥일과 변동을 감당할 수 있는가입니다.")
    elif (not facts["female"]) and len(tones) == 2:
        parts.append(
            "결혼을 저울질할 때 이 사주가 더 보는 것은, 살림과 현실 조건이 서는가와 "
            "바깥일의 변동을 감당할 수 있는가입니다."
        )
    life = _LIFE.get(facts["life_group"])
    if life and "day_ji" not in facts["positions"]:
        parts.append(life[1])
        if _copied_glyph(facts) and facts["life_group"] == "비겁":
            parts.append("그 힘은 같은 글자가 앉은 칸까지 이어집니다.")
        parts.append(life[2])
    elif life and "day_ji" in facts["positions"]:
        parts.append(life[1])
        parts.append(life[2])
    for line in _hae_lines(facts, hedge=True):
        parts.append(line)
    return " ".join(parts)


def _hae_lines(facts: Dict[str, Any], hedge: bool) -> List[str]:
    relations = ((facts["saju"].get("branch_relations") or {}).get("relations") or {})
    lines = []
    for item in relations.get("해") or []:
        pair = str(item.get("pair") or "")
        slots = pair.split("-")
        if len(slots) != 2 or any(slot not in _BRANCH_POS for slot in slots):
            continue
        if (not facts["time_known"]) and "hour" in slots:
            continue
        if hedge:
            if slots == ["year", "hour"] or slots == ["hour", "year"]:
                lines.append(
                    "큰 일정과 둘만의 시간이 한 박자로 붙지 않을 수는 있습니다. "
                    "실제 가족 일정은 이 사주만으로 확인되지 않습니다."
                )
            else:
                lines.append("한 박자로 붙지 않을 수는 있으나, 실제 일정은 이 사주만으로 확인되지 않습니다.")
        else:
            lines.append(f"{_BRANCH_POS[slots[0]]}와 {_BRANCH_POS[slots[1]]}는 서로 거슬립니다.")
    return lines


def _yongsin_overlap(facts: Dict[str, Any]) -> bool:
    if not facts["positions"] or not facts["yongsin"]:
        return False
    elems = {_elem(facts, pos) for pos in facts["positions"]}
    elems.discard("")
    return bool(elems) and elems <= set(facts["yongsin"])


def _same_element(facts: Dict[str, Any]) -> bool:
    elems = {_elem(facts, pos) for pos in facts["positions"]}
    elems.discard("")
    return len(elems) == 1


def _elem(facts: Dict[str, Any], pos: str) -> str:
    glyph = _glyph(facts["saju"], pos)
    if not glyph:
        return ""
    table = GAN_ELEM if pos.endswith("gan") else JI_ELEM
    return table.get(glyph, "")


def _glyph(saju: Dict[str, Any], pos: str) -> str:
    slot = _PILLAR_KEY.get(pos.split("_")[0], "")
    gz = (saju.get("birth_ganji") or {}).get(slot) or ""
    if len(gz) < 2 or gz == "미정":
        return ""
    return gz[0] if pos.endswith("gan") else gz[1]


def _raw(reasons: Sequence[str]) -> int:
    return 50 + sum(_WEIGHT.get(code, 0) for code in reasons)


def _place(n: int) -> str:
    return {1: "한 곳", 2: "두 곳", 3: "세 곳", 4: "네 곳"}.get(n, f"{n}곳")


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


def _un(word: str) -> str:
    return "은" if _batchim(word) else "는"


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
