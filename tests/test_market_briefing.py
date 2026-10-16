"""아침 시황 브리핑 — 헤드라인·개장 등락이 시장 포인트를 바꾸고, 요청 경로는 LLM 을 호출하지 않는다."""
from datetime import datetime
from zoneinfo import ZoneInfo

import domains.market.briefing as briefing
from domains.wealth.engine import build_report

KST = ZoneInfo("Asia/Seoul")
TARGET = "2026-10-16"


def _facts(**overrides):
    base = {
        "headlines": [],
        "theme": None,
        "nasdaq_pct": 0.1,
        "fx_pct": 0.1,
        "kospi_pct": None,
        "kosdaq_pct": None,
        "at_open": True,
    }
    base.update(overrides)
    return base


def test_flat_overnight_does_not_claim_there_is_no_catalyst_when_domestic_moves():
    copy = briefing.compose_market_copy(_facts(
        headlines=["과매도 반도체, 강세 출발 - 한국경제"],
        kospi_pct=1.8,
        kosdaq_pct=2.1,
        theme="반도체",
    ))
    text = copy["market_point"]
    assert "과매도 반도체, 강세 출발" in text
    assert "코스피와 코스닥은 상승으로 출발" in text
    mixed = briefing.build_market_point(_facts(kospi_pct=1.4, kosdaq_pct=-0.9))
    assert "코스닥은 하락으로 출발" in mixed and "코스닥는" not in mixed
    assert "재료를 새로 만들기 어렵" not in text
    assert "관망" not in text
    assert "%" not in text
    assert "매수" not in copy["advice_note"] and "매도" not in copy["advice_note"]
    assert "장중까지 이어지는지" in copy["advice_note"]


def test_flat_market_states_the_absence_without_a_trade_order():
    text = briefing.build_market_point(_facts())
    assert "큰 방향이 없었" in text
    assert "관망" not in text
    assert "코스피" not in text


def test_select_headlines_prefers_preopen_window():
    def item(title, hour, minute=0):
        return {
            "title": title,
            "published": datetime(2026, 10, 16, hour, minute, tzinfo=KST),
        }

    chosen = briefing.select_headlines([
        item("전날 마감 시황 정리", 7, 10),
        item("반도체 강세에 코스피 상승 출발", 8, 42),
        item("장중 속보 코스닥 급등", 11, 0),
    ], TARGET)
    assert chosen == ["반도체 강세에 코스피 상승 출발"]


def test_tick_headlines_are_not_used_as_the_catalyst():
    def item(title, hour, minute=0):
        return {
            "title": title,
            "published": datetime(2026, 10, 16, hour, minute, tzinfo=KST),
        }

    chosen = briefing.select_headlines([
        item("코스피 1.80% 상승한 5653.99에 출발", 8, 40),
        item("반도체 수주 소식에 위험자산 선호", 8, 50),
    ], TARGET)
    assert chosen == ["반도체 수주 소식에 위험자산 선호"]
    assert briefing.select_headlines([item("코스피 1.80% 상승한 5653.99에 출발", 8, 40)], TARGET) == []


def test_parse_rss_items_reads_titles():
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item><title>코스피 반도체 주도 상승 - 서울경제</title>
        <pubDate>Fri, 16 Oct 2026 00:30:00 GMT</pubDate></item>
      <item><title>짧음</title></item>
    </channel></rss>
    """
    items = briefing.parse_rss_items(xml)
    assert len(items) == 1
    assert items[0]["title"].startswith("코스피")
    assert items[0]["published"].astimezone(KST).hour == 9


def test_resolve_uses_stored_brief_without_network(monkeypatch, tmp_path):
    monkeypatch.setattr(briefing, "BRIEF_DIR", tmp_path)
    briefing.save_brief(
        TARGET,
        {"market_point": "오늘 아침 핵심 재료는 반도체 반등입니다.", "advice_note": briefing.ADVICE_NOTE},
        source="llm",
        facts={"headlines": ["반도체 반등"]},
    )
    monkeypatch.setattr(briefing, "collect_morning_facts", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    copy = briefing.resolve_market_copy(
        {"status": "ok", "change_percent": 0.1, "fx_change_percent": 0.1},
        TARGET,
        now=datetime(2026, 10, 16, 9, 30, tzinfo=KST),
    )
    assert copy["market_point"] == "오늘 아침 핵심 재료는 반도체 반등입니다."


def test_historical_date_skips_live_headlines(monkeypatch):
    monkeypatch.setattr(briefing, "collect_morning_facts", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    copy = briefing.resolve_market_copy(
        {"status": "ok", "change_percent": -1.2, "fx_change_percent": 0.2},
        "2026-09-26",
        now=datetime(2026, 10, 16, 11, 0, tzinfo=KST),
    )
    assert "나스닥은 하락" in copy["market_point"]
    assert "코스피" not in copy["market_point"]


def test_llm_failure_does_not_replace_rules(monkeypatch):
    monkeypatch.setattr(
        "shared.ai_client.call_gemini_json",
        lambda *a, **k: ({"market_point": "지금 사세요", "advice_note": "전량 매수"}, False),
    )
    copy, used = briefing.generate_llm_brief(_facts(headlines=["반도체 강세 출발"]))
    assert used is False
    assert "지금 사세요" not in copy["market_point"]
    assert "반도체" in copy["market_point"]


def test_engine_uses_brief_without_dropping_saju_text():
    market = {
        "status": "ok", "direction": "보합", "change_percent": 0.1, "fx_change_percent": 0.1,
        "session_date": "2026-10-15",
    }
    plain = build_report(
        day_master="甲", today_sipsin="편재", today_ji_sipsin="정재", day_relation="무관",
        wealth_type="재성", market=market, target_date=TARGET,
    )
    briefed = build_report(
        day_master="甲", today_sipsin="편재", today_ji_sipsin="정재", day_relation="무관",
        wealth_type="재성",
        market={**market, "point_text": "오늘 아침 핵심 재료는 반도체입니다.", "advice_note": briefing.ADVICE_NOTE},
        target_date=TARGET,
    )
    assert briefed["market_point"] == "오늘 아침 핵심 재료는 반도체입니다."
    assert briefed["investment_fortune"].startswith(plain["investment_fortune"])
    assert briefed["investment_fortune"].endswith(briefing.ADVICE_NOTE)
    assert "나스닥이 하락한 여파" not in briefed["market_point"]
