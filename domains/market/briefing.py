"""아침 시황 브리핑.

명리 엔진과 분리된다. 헤드라인과 지수 숫자만 모으고, 요청 경로에서는 문장을 룰로 조립한다.
LLM 요약은 scripts/generate_market_brief.py 에서만 만들고, 그 결과가 있을 때만 룰 문장을 대체한다.
"""
import json
import logging
import re
import threading
from datetime import datetime, time as dtime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
DIRECTION_THRESHOLD_PCT = 0.5
_FETCH_TIMEOUT_SECONDS = 8
_REFRESH_SECONDS = 180
_PIN_AFTER = dtime(9, 25)
_OPEN_WINDOW_END = dtime(9, 20)

BRIEF_DIR = Path(__file__).resolve().parents[2] / "data" / "market_briefs"
_HEADLINE_URL = (
    "https://news.google.com/rss/search?q="
    "%EC%BD%94%EC%8A%A4%ED%94%BC+OR+%EC%BD%94%EC%8A%A4%EB%8B%A5+OR+%EB%B0%98%EB%8F%84%EC%B2%B4"
    "&hl=ko&gl=KR&ceid=KR:ko"
)
_KOSPI_TICKER = "^KS11"
_KOSDAQ_TICKER = "^KQ11"

ADVICE_NOTE = (
    "아침 재료와 개장 흐름이 보여도 장중까지 이어지는지 확인하면서, "
    "정해 둔 비중과 원칙대로 나누어 대응하세요."
)
_MISSING_POINT = "시장 데이터를 불러오지 못해 이번에는 아침 시황을 반영하지 않았습니다."

_THEME_WORDS = (
    "반도체", "삼성전자", "SK하이닉스", "HBM", "2차전지", "배터리",
    "바이오", "외국인", "환율", "금리", "실적",
)
_UNSAFE = (
    "전량 매수", "풀매수", "당장 매도", "모두 매도", "모두 팔",
    "지금 사세요", "지금 파세요", "레버리지로 따라",
)

_lock = threading.Lock()
_memory: Dict[str, Dict[str, Any]] = {}


def direction_of(change_percent: Optional[float]) -> Optional[str]:
    if change_percent is None:
        return None
    if change_percent >= DIRECTION_THRESHOLD_PCT:
        return "상승"
    if change_percent <= -DIRECTION_THRESHOLD_PCT:
        return "하락"
    return "보합"


def shorten_headline(title: str) -> str:
    text = re.sub(r"\s+-\s+.*$", "", (title or "").strip())
    text = re.sub(r"\s+", " ", text).strip(" \"'")
    if len(text) > 42:
        text = text[:41].rstrip() + "…"
    return text


def theme_of(titles: List[str]) -> Optional[str]:
    blob = " ".join(titles)
    for word in _THEME_WORDS:
        if word in blob:
            if word in ("삼성전자", "SK하이닉스", "HBM"):
                return "반도체"
            if word == "배터리":
                return "2차전지"
            return word
    return None


def parse_rss_items(xml_text: str) -> List[Dict[str, Any]]:
    """RSS item → {'title', 'published'}. 깨진 XML 이면 빈 목록."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    items: List[Dict[str, Any]] = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        if len(title) < 8:
            continue
        published = None
        raw_date = node.findtext("pubDate")
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date).astimezone(KST)
            except (TypeError, ValueError, OverflowError):
                published = None
        items.append({"title": title, "published": published})
    return items


def select_headlines(
    items: List[Dict[str, Any]],
    target_date: str,
    *,
    limit: int = 2,
) -> List[str]:
    """개장 직전(08:00~09:10 KST) 헤드라인을 우선하고, 없으면 같은 날 최신 제목으로 채운다."""
    morning: List[str] = []
    same_day: List[str] = []
    undated: List[str] = []
    for item in items:
        title = shorten_headline(item.get("title") or "")
        if len(title) < 8:
            continue
        published = item.get("published")
        if published is None:
            undated.append(title)
            continue
        if published.date().isoformat() != target_date:
            continue
        same_day.append(title)
        clock = published.time()
        if dtime(8, 0) <= clock <= dtime(9, 10):
            morning.append(title)
    # 지수 숫자만 찍힌 제목은 등락률 나열이라 빼고, 섹터·이슈 제목을 먼저 고른다.
    pool = [title for title in (morning or same_day or undated) if not _TICK_HEADLINE.search(title)]
    themed = [title for title in pool if theme_of([title])]
    out: List[str] = []
    for title in themed or pool:
        if title not in out:
            out.append(title)
        if len(out) >= limit:
            break
    return out


_TICK_HEADLINE = re.compile(r"\d+(?:\.\d+)?\s*%|\d{4,}\.\d{2}")


def _topic(name: str) -> str:
    return f"{name}은" if name.endswith("닥") else f"{name}는"


def _leg(name: str, direction: str, at_open: bool) -> str:
    topic = _topic(name)
    if direction == "보합":
        return f"{topic} 보합권입니다"
    if at_open:
        return f"{topic} {direction}으로 출발했습니다"
    return f"{topic} {direction} 흐름입니다"


def _domestic_sentence(kospi: Optional[float], kosdaq: Optional[float], at_open: bool) -> str:
    left = direction_of(kospi)
    right = direction_of(kosdaq)
    if left is None and right is None:
        return ""
    if left is not None and right is not None and left == right:
        if left == "보합":
            return "코스피와 코스닥은 보합권입니다"
        if at_open:
            return f"코스피와 코스닥은 {left}으로 출발했습니다"
        return f"코스피와 코스닥은 {left} 흐름입니다"
    parts = []
    if left is not None:
        parts.append(_leg("코스피", left, at_open))
    if right is not None:
        parts.append(_leg("코스닥", right, at_open))
    return " ".join(part if part.endswith(".") else part + "." for part in parts).rstrip(".")


def _overnight_sentence(nasdaq: Optional[float], fx: Optional[float]) -> str:
    n = direction_of(nasdaq)
    f = direction_of(fx)
    nasdaq_text = {
        "상승": "밤사이 나스닥은 반등했고",
        "하락": "밤사이 나스닥은 하락했고",
        "보합": "밤사이 나스닥은 큰 방향 없이 마감했고",
    }
    fx_text = {
        "상승": "원·달러 환율은 올랐습니다",
        "하락": "원·달러 환율은 내렸습니다",
        "보합": "원·달러 환율은 큰 방향이 없었습니다",
    }
    if n == "보합" and f == "보합":
        return "밤사이 나스닥과 원·달러 환율은 큰 방향이 없었습니다."
    if n and f:
        return f"{nasdaq_text[n]}, {fx_text[f]}."
    if n == "상승":
        return "밤사이 나스닥은 반등했습니다."
    if n == "하락":
        return "밤사이 나스닥은 하락했습니다."
    if n == "보합":
        return "밤사이 나스닥은 큰 방향 없이 마감했습니다."
    if f:
        return fx_text[f] + "."
    return ""


def build_market_point(facts: Dict[str, Any]) -> str:
    """헤드라인·국내 개장·밤사이 나스닥/환율을 사실만 한두 문장으로 붙인다. 매매 지시는 넣지 않는다."""
    headlines = [shorten_headline(title) for title in (facts.get("headlines") or []) if title]
    headlines = [title for title in headlines if title]
    sentences: List[str] = []
    if headlines:
        sentences.append(f"오늘 아침 핵심 재료는 「{headlines[0]}」입니다.")
    elif facts.get("theme"):
        sentences.append(f"오늘 아침 핵심 재료는 {facts['theme']} 이슈입니다.")

    domestic = _domestic_sentence(
        facts.get("kospi_pct"), facts.get("kosdaq_pct"), bool(facts.get("at_open")),
    )
    if domestic:
        sentences.append(domestic if domestic.endswith(".") else domestic + ".")

    overnight = _overnight_sentence(facts.get("nasdaq_pct"), facts.get("fx_pct"))
    if overnight:
        sentences.append(overnight)

    if not sentences:
        return _MISSING_POINT
    return " ".join(sentences)


def compose_market_copy(facts: Dict[str, Any]) -> Dict[str, str]:
    return {"market_point": build_market_point(facts), "advice_note": ADVICE_NOTE}


def _unsafe(text: str) -> bool:
    return any(phrase in (text or "") for phrase in _UNSAFE)


def build_llm_prompt(facts: Dict[str, Any]) -> str:
    headlines = facts.get("headlines") or []
    headline_lines = "\n".join(f"- {title}" for title in headlines) or "- (수집된 헤드라인 없음)"

    def line(label: str, pct: Optional[float]) -> str:
        direction = direction_of(pct)
        if direction is None:
            return f"{label}: 확인되지 않음"
        return f"{label}: {direction} (등락률 {pct}%. 출력 문장에는 숫자를 쓰지 말 것)"

    return (
        "아래 입력만 근거로 오늘 아침 재테크 카드 두 문장을 JSON 으로 작성하세요.\n"
        "없는 섹터, 없는 급등락, 없는 정책은 만들지 마세요.\n"
        "market_point 는 헤드라인의 핵심 재료를 사실대로 한 문장으로 요약하고, "
        "확인된 나스닥·환율·코스피·코스닥 방향만 덧붙이세요. 매수·매도 지시는 넣지 마세요.\n"
        "advice_note 는 그 재료가 장중까지 이어질지 알 수 없다는 전제로, "
        "지속 여부를 확인하며 정해 둔 비중과 원칙대로 대응하라는 위험관리 문장 하나만 쓰세요. "
        "상승 지속이나 하락을 기회로 단정하지 마세요.\n"
        "십신, 용신, 신강, 신약, 일간, 오행 같은 사주 용어와 등락률 숫자는 출력하지 마세요.\n\n"
        f"헤드라인:\n{headline_lines}\n"
        f"{line('전일 나스닥', facts.get('nasdaq_pct'))}\n"
        f"{line('전일 원·달러 환율', facts.get('fx_pct'))}\n"
        f"{line('개장 코스피', facts.get('kospi_pct'))}\n"
        f"{line('개장 코스닥', facts.get('kosdaq_pct'))}\n"
    )


def generate_llm_brief(facts: Dict[str, Any]):
    """스크립트 전용. (문장, llm 사용 여부). 실패·위험 문장이면 룰 문장과 False."""
    from shared.ai_client import call_gemini_json

    fallback = compose_market_copy(facts)
    result, is_fallback = call_gemini_json(
        build_llm_prompt(facts),
        fallback,
        system_instruction=(
            "한국 아침 증시 브리핑 작성자. 입력에 있는 사실만 요약하고 투자 방향을 단정하지 않는다."
        ),
    )
    if is_fallback:
        return fallback, False
    point = str(result.get("market_point") or "").strip()
    note = str(result.get("advice_note") or "").strip()
    if not point or not note or _unsafe(point) or _unsafe(note) or "%" in point or "%" in note:
        return fallback, False
    return {"market_point": point, "advice_note": note}, True


def _brief_path(target_date: str) -> Path:
    return BRIEF_DIR / f"{target_date}.json"


def load_stored_brief(target_date: str) -> Optional[Dict[str, str]]:
    path = _brief_path(target_date)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    point = str(payload.get("market_point") or "").strip()
    note = str(payload.get("advice_note") or "").strip()
    if not point or not note or _unsafe(point) or _unsafe(note):
        return None
    return {"market_point": point, "advice_note": note}


def save_brief(target_date: str, copy: Dict[str, str], *, source: str, facts: Dict[str, Any]) -> None:
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "target_date": target_date,
        "source": source,
        "market_point": copy["market_point"],
        "advice_note": copy["advice_note"],
        "headlines": facts.get("headlines") or [],
    }
    path = _brief_path(target_date)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _at_open(now: datetime) -> bool:
    clock = now.time()
    return now.weekday() < 5 and dtime(9, 0) <= clock < _OPEN_WINDOW_END


def _should_pin(facts: Dict[str, Any], now: datetime) -> bool:
    if now.weekday() >= 5 or now.time() >= _PIN_AFTER:
        return True
    return facts.get("kospi_pct") is not None or facts.get("kosdaq_pct") is not None


def _fetch_rss() -> List[Dict[str, Any]]:
    request = Request(_HEADLINE_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=_FETCH_TIMEOUT_SECONDS) as response:
            xml_text = response.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        logger.warning(f"증시 헤드라인 조회 실패: {exc}")
        return []
    return parse_rss_items(xml_text)


def _domestic_pct(ticker: str, target_date: str) -> Optional[float]:
    from domains.market.indicators import _fetch_quote

    try:
        quote = _fetch_quote(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"국내 개장 등락 조회 실패 ({ticker}): {exc}")
        return None
    if quote.get("session_date") != target_date:
        return None
    pct = quote.get("change_percent")
    return float(pct) if isinstance(pct, (int, float)) else None


def collect_morning_facts(target_date: str, market: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    moment = datetime.now(KST) if now is None else now
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=KST)
    else:
        moment = moment.astimezone(KST)
    items = _fetch_rss()
    headlines = select_headlines(items, target_date)
    facts = {
        "headlines": headlines,
        "theme": theme_of(headlines),
        "nasdaq_pct": market.get("change_percent") if market.get("status") == "ok" else None,
        "fx_pct": market.get("fx_change_percent") if market.get("status") == "ok" else None,
        "kospi_pct": _domestic_pct(_KOSPI_TICKER, target_date),
        "kosdaq_pct": _domestic_pct(_KOSDAQ_TICKER, target_date),
        "at_open": _at_open(moment),
    }
    return facts


def _facts_from_overnight(market: Dict[str, Any]) -> Dict[str, Any]:
    ok = market.get("status") == "ok"
    return {
        "headlines": [],
        "theme": None,
        "nasdaq_pct": market.get("change_percent") if ok else None,
        "fx_pct": market.get("fx_change_percent") if ok else None,
        "kospi_pct": None,
        "kosdaq_pct": None,
        "at_open": False,
    }


def _is_current_wealth_day(target_date: str, now: datetime) -> bool:
    from config import wealth_asof_date

    return wealth_asof_date(now).isoformat() == target_date


def resolve_market_copy(
    market: Dict[str, Any],
    target_date: str,
    now: Optional[datetime] = None,
    *,
    monotonic: Optional[float] = None,
) -> Dict[str, str]:
    """저장된 아침 브리핑이 있으면 그것을, 없으면 룰 문장을 반환한다. LLM 은 호출하지 않는다."""
    import time as time_mod

    moment = datetime.now(KST) if now is None else now
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=KST)
    else:
        moment = moment.astimezone(KST)
    clock = time_mod.monotonic() if monotonic is None else monotonic

    stored = load_stored_brief(target_date)
    if stored:
        return stored
    if not _is_current_wealth_day(target_date, moment):
        return compose_market_copy(_facts_from_overnight(market))

    with _lock:
        hit = _memory.get(target_date)
        if hit and (hit.get("pinned") or clock < hit.get("expires_at", 0)):
            return hit["copy"]

        facts = collect_morning_facts(target_date, market, moment)
        copy = compose_market_copy(facts)
        pinned = _should_pin(facts, moment)
        if pinned:
            try:
                save_brief(target_date, copy, source="rules", facts=facts)
            except OSError as exc:
                logger.warning(f"아침 시황 저장 실패: {exc}")
        _memory[target_date] = {
            "copy": copy,
            "pinned": pinned,
            "expires_at": None if pinned else clock + _REFRESH_SECONDS,
        }
        return copy


def clear_brief_cache() -> None:
    with _lock:
        _memory.clear()
