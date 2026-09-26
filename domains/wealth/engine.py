"""오늘의 재테크 사주 — 룰베이스 조립 엔진 (순수 함수, I/O 없음).

입력은 명리 코어가 계산한 값(일간·오늘 십신·원국 세력)과 시장 모듈이 넘겨준 '직전 거래일 방향' 뿐이다.
시장 데이터를 직접 조회하지 않는다(시장 로직과 명리 엔진 분리 원칙).

결정성: 같은 (target_date, 조합) 이면 항상 같은 문장. 변형 선택에 hashlib 를 쓰므로 프로세스·워커가 달라도 동일.
"""
import hashlib
from typing import Any, Dict, List, Optional, Sequence

from core.constants import CHUNG, HAE, PA, SAMHAP, SANGHYEONG, YUKHAP
from domains.wealth import fragments as F

DIRECTION_THRESHOLD_PCT = 0.5  # |등락률| ≥ 0.5% → 상승/하락, 그 사이는 보합 (최근 2년 코스피 기준 44/28/28%)

# 원국 유형 판정 기준 (무작위 800 원국 기준 분포: 비겁19·재성18·식상18·관인31·균형14%)
_BIGEOP_SHARE = 0.40   # 비겁은 일간 자신이 포함돼 비중이 높게 나오므로 기준을 따로 높게 둔다
_DOMINANT_SHARE = 0.27

# 칩 점수: 오늘 기운 + 원국 유형 + 시장 방향
_S_SCORE = {"편재": 2, "겁재": 2, "상관": 1, "식신": 1, "비견": 1,
            "편관": 0, "정재": 0, "정관": -1, "편인": -1, "정인": -2}
_T_SCORE = {"재성": 1, "비겁": 1, "식상": 0, "균형": 0, "관인": -1}
_M_SCORE = {"상승": 1, "보합": 0, "하락": -1}

# 성향 충돌 판정: 공격형 원국 × 신중한 날, 신중형 원국 × 과감한 날
_ACTIVE_TYPES = {"비겁", "재성", "식상"}
_CAUTIOUS_TYPES = {"관인"}


def classify_direction(change_percent: Optional[float]) -> str:
    if change_percent is None:
        return "보합"
    if change_percent >= DIRECTION_THRESHOLD_PCT:
        return "상승"
    if change_percent <= -DIRECTION_THRESHOLD_PCT:
        return "하락"
    return "보합"


def classify_wealth_type(group_power: Dict[str, float]) -> str:
    """원국 십신 그룹 세력(derived.group_power) → 비겁/재성/식상/관인/균형."""
    total = sum(v for v in (group_power or {}).values() if v) or 0
    if total <= 0:
        return "균형"
    share = {k: (group_power.get(k) or 0) / total for k in ("비겁", "식상", "재성", "관성", "인성")}
    if share["비겁"] >= _BIGEOP_SHARE:
        return "비겁"
    rest = {"재성": share["재성"], "식상": share["식상"], "관인": max(share["관성"], share["인성"])}
    top = max(rest, key=rest.get)
    return top if rest[top] >= _DOMINANT_SHARE else "균형"


def classify_day_relation(natal_day_branch: Optional[str], today_branch: Optional[str]) -> str:
    """오늘 일진 지지와 내 원국 일지의 관계 → 충/합/마찰/동일/무관 (충 > 합 > 마찰 우선)."""
    if not natal_day_branch or not today_branch:
        return "무관"
    if natal_day_branch == today_branch:
        return "동일"
    key = frozenset((natal_day_branch, today_branch))
    if key in CHUNG:
        return "충"
    if key in YUKHAP or any(natal_day_branch in g and today_branch in g for g in SAMHAP):
        return "합"
    if key in PA or key in HAE or key in SANGHYEONG:
        return "마찰"
    return "무관"


def is_conflict(sipsin: str, wtype: str) -> bool:
    s = _S_SCORE.get(sipsin, 0)
    return (wtype in _ACTIVE_TYPES and s <= -1) or (wtype in _CAUTIOUS_TYPES and s >= 1)


def behavior(sipsin: str, wtype: str, direction: str) -> Dict[str, str]:
    score = _S_SCORE[sipsin] + _T_SCORE[wtype] + _M_SCORE[direction]
    aggressiveness = "높음" if score >= 3 else ("보통" if score >= 0 else "낮음")
    # 추격매수 '높음'은 상승장 + 추격 성향(겁재·편재·비견 또는 비겁형) + 적극성 점수 2 이상일 때만
    if direction == "상승" and (sipsin in ("겁재", "편재", "비견") or wtype == "비겁") and score >= 2:
        chase = "높음"
    elif direction == "하락" or sipsin in ("정인", "정관", "정재") or score < 0:
        chase = "낮음"
    else:
        chase = "보통"
    return {
        "tendency": "적극성" if score >= 2 else "관망",
        "aggressiveness": aggressiveness,
        "chase_risk": chase,
    }


# ───────────────────────── 변형 선택 ─────────────────────────
def _seed(*parts: Any) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def _ending(sentence: str) -> str:
    """종결 어절(마지막 단어). 연속 문장이 같은 어절로 끝나면 중복으로 본다."""
    return sentence.rstrip(" .!?").split(" ")[-1]


def _assemble(slots: Sequence[Sequence[str]], seed_base: str) -> str:
    """칸마다 해시로 선호 변형을 정하되, 직전 문장과 같은 어미이거나 '오늘'이 이미 나왔으면 다른 변형으로 교체."""
    out: List[str] = []
    today_used = False
    for i, variants in enumerate(slots):
        order = list(variants)
        if len(order) > 1 and _seed(seed_base, i) % 2:
            order.reverse()

        def penalty(s: str) -> int:
            p = 0
            if out and _ending(s) == _ending(out[-1]):
                p += 4
            if i > 0 and s.startswith("오늘"):
                p += 2
            if today_used and "오늘" in s:
                p += 1
            return p

        chosen = min(order, key=penalty)  # min 은 동점이면 앞(해시 선호)을 유지
        out.append(chosen)
        today_used = today_used or "오늘" in chosen
    return " ".join(out)


def _pick(variants: Sequence[str], *seed_parts: Any) -> str:
    return variants[_seed(*seed_parts) % len(variants)]


# ───────────────────────── 조립 ─────────────────────────
def _format_session_date(session_date: str) -> str:
    import datetime as _dt
    d = _dt.date.fromisoformat(session_date)
    return f"{d.month}월 {d.day}일({'월화수목금토일'[d.weekday()]})"


def _market_point(market: Dict[str, Any], direction: str, target_date: str) -> str:
    pct = market.get("change_percent")
    session = market.get("session_date")
    if market.get("status") != "ok" or pct is None or not session:
        return F.MARKET_POINT_UNKNOWN
    p = f"{pct:+.2f}%" if direction == "보합" else f"{abs(pct):.2f}%"
    tpl = _pick(F.MARKET_POINT[direction], target_date, "mp", direction)
    return tpl.format(d=_format_session_date(session), p=p)


def build_report(
    *,
    day_master: str,
    today_sipsin: str,
    today_ji_sipsin: Optional[str],
    day_relation: str,
    wealth_type: str,
    market: Dict[str, Any],
    target_date: str,
) -> Dict[str, Any]:
    """재테크 응답의 data 부분(market 제외)을 조립한다.

    market: {'status': 'ok'|'error', 'direction', 'change_percent', 'session_date'} — 시장 모듈이 하루 1회 고정한 값.
    """
    s, t, d = today_sipsin, wealth_type, day_master
    j = today_ji_sipsin if today_ji_sipsin in F.F1 else s
    m = market.get("direction") if market.get("status") == "ok" else "보합"
    if m not in F.DIRECTIONS:
        m = "보합"
    r = day_relation if day_relation in F.F_REL else "무관"
    key = f"{target_date}|{d}|{s}|{j}|{r}|{t}|{m}"

    i2 = F.I2_BRIDGE[t] if is_conflict(s, t) else F.I2[(t, m)]
    investment = _assemble([F.I1[(s, m)], i2, F.I3[d], F.I4[s], F.I5[t]], key + "|inv")
    consumption = _assemble([F.C1[s], F.C2[t], F.C3[d], F.C4[m], F.C5[s]], key + "|con")
    flow_slots = [F.F1[j], F.F2[s]] + ([F.F_REL[r]] if r in F.F_REL else []) + [F.F3[t], F.F4[d], F.F5[m]]
    money_flow = _assemble(flow_slots, key + "|flow")

    chips = behavior(s, t, m)
    chips["spending_tendency"] = _pick(F.SPENDING[s], key, "spend")

    return {
        "market_point": _market_point(market, m, target_date),
        "investment_fortune": investment,
        "consumption_fortune": consumption,
        "money_flow": money_flow,
        "caution_point": _pick(F.CAUTION[(s, m)], key, "caution"),
        "investment_behavior": chips,
    }
