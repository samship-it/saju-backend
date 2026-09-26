"""재테크 룰베이스 엔진 — 전 조합 문장 품질 + 칩 규칙 + 시장 방향 하루 고정 + API 규격."""
import itertools
import re
import time

from fastapi.testclient import TestClient

import main
from domains.market import indicators
from domains.market.indicators import _fetch_prev_session_change as _real_fetch_prev_session_change  # conftest 스텁 전 원본
from domains.wealth import fragments as F
from domains.wealth.engine import (
    _ending, behavior, build_report, classify_day_relation, classify_direction,
    classify_wealth_type, is_conflict,
)
from domains.wealth.service import analyze_daily_finance

client = TestClient(main.app)

RELATIONS = ("충", "합", "마찰", "동일", "무관")
PCT = {"상승": 0.9, "하락": -1.12, "보합": 0.21}
# '지지'는 일반어("지지 않는")와 겹쳐 제외
TERMS = list(F.SIPSIN) + ["일간", "오행", "용신", "기신", "원국", "천간", "비겁", "재성", "식상", "관인"]
TARGET = "2026-09-26"


def _split(text):
    return re.split(r"(?<=[.!?])\s+", text.strip())


def _report(d, s, j, r, t, m, date=TARGET):
    return build_report(
        day_master=d, today_sipsin=s, today_ji_sipsin=j, day_relation=r, wealth_type=t,
        market={"status": "ok", "change_percent": PCT[m], "session_date": "2026-09-23", "direction": m},
        target_date=date,
    )


def _all_combos():
    # 주축 1,500 × 지지 십신 10 은 전수, 관계 5종은 (충/무관) 전수 + 나머지는 j==s 일 때만 — 총 34,500 조합
    for d, s, j, t, m in itertools.product(F.DAY_MASTERS, F.SIPSIN, F.SIPSIN, F.WEALTH_TYPES, F.DIRECTIONS):
        for r in (("충", "무관") if j != s else RELATIONS):
            yield d, s, j, r, t, m


def test_every_combination_reads_cleanly():
    """어미 연속 중복 없음 · 둘째 문장부터 '오늘'로 시작 안 함 · 단락당 '오늘' ≤ 2 · 사주 용어 노출 없음."""
    problems = []
    for combo in _all_combos():
        rep = _report(*combo)
        for field in ("investment_fortune", "consumption_fortune", "money_flow"):
            text = rep[field]
            sents = _split(text)
            assert len(sents) >= 5, (combo, field)
            for a, b in zip(sents, sents[1:]):
                if _ending(a) == _ending(b):
                    problems.append((combo, field, "same-ending", b[-20:]))
            for s in sents[1:]:
                if s.startswith("오늘"):
                    problems.append((combo, field, "today-start", s[:20]))
            if text.count("오늘") > 2:
                problems.append((combo, field, "today-count"))
        blob = " ".join(v for v in rep.values() if isinstance(v, str))
        for w in TERMS:
            if w in blob:
                problems.append((combo, "term", w))
        if len(problems) > 20:
            break
    assert not problems, problems[:20]


def test_fragment_variants_end_differently():
    """한 칸의 A/B안은 서로 다른 어절로 끝나야 교체로 어미 중복을 피할 수 있다."""
    tables = [F.I1, F.I2, F.I2_BRIDGE, F.I3, F.I4, F.I5, F.C1, F.C2, F.C3, F.C4, F.C5,
              F.F1, F.F_REL, F.F2, F.F3, F.F4, F.F5]
    for table in tables:
        for key, variants in table.items():
            assert len(variants) == 2, key
            assert _ending(variants[0]) != _ending(variants[1]), key


def test_fragment_coverage_is_complete():
    assert len(F.I1) == len(F.CAUTION) == 30
    assert len(F.I2) == 15
    for table in (F.I3, F.C3, F.F4):
        assert set(table) == set(F.DAY_MASTERS)
    for table in (F.I4, F.C1, F.C5, F.F1, F.F2, F.SPENDING):
        assert set(table) == set(F.SIPSIN)


def test_deterministic_and_date_varies():
    a = _report("庚", "상관", "정재", "무관", "비겁", "상승")
    assert a == _report("庚", "상관", "정재", "무관", "비겁", "상승")
    others = [_report("庚", "상관", "정재", "무관", "비겁", "상승", date=f"2026-10-{d:02d}") for d in range(1, 11)]
    assert any(o["investment_fortune"] != a["investment_fortune"] for o in others)


def test_single_axis_changes_text():
    base = _report("庚", "상관", "정재", "무관", "비겁", "상승")
    for alt in (("庚", "상관", "정재", "무관", "비겁", "하락"), ("庚", "상관", "정재", "무관", "관인", "상승"),
                ("丙", "상관", "정재", "무관", "비겁", "상승"), ("庚", "정인", "정재", "무관", "비겁", "상승")):
        assert _report(*alt)["investment_fortune"] != base["investment_fortune"], alt
    assert _report("庚", "상관", "편관", "무관", "비겁", "상승")["money_flow"] != base["money_flow"]
    assert _report("庚", "상관", "정재", "충", "비겁", "상승")["money_flow"] != base["money_flow"]


def test_conflict_uses_bridge_sentence():
    assert is_conflict("정인", "비겁") and is_conflict("편재", "관인")
    assert not is_conflict("편재", "비겁") and not is_conflict("정인", "균형")
    rep = _report("庚", "정인", "정재", "무관", "비겁", "상승")
    assert any(b in rep["investment_fortune"] for b in F.I2_BRIDGE["비겁"])


def test_chase_high_requires_active_score():
    # 2단계 F 사례: 정인 + 비겁형 + 상승 → 관망인데 추격매수 높음이던 모순
    b = behavior("정인", "비겁", "상승")
    assert b["tendency"] == "관망" and b["chase_risk"] != "높음"
    assert behavior("편재", "재성", "상승")["chase_risk"] == "높음"
    for s, t, m in itertools.product(F.SIPSIN, F.WEALTH_TYPES, F.DIRECTIONS):
        b = behavior(s, t, m)
        if b["chase_risk"] == "높음":
            assert b["tendency"] == "적극성", (s, t, m)


def test_classifiers():
    assert classify_direction(0.5) == "상승" and classify_direction(-0.5) == "하락"
    assert classify_direction(0.49) == "보합" and classify_direction(None) == "보합"
    assert classify_wealth_type({"비겁": 4, "식상": 1, "재성": 1, "관성": 1, "인성": 1}) == "비겁"
    assert classify_wealth_type({"비겁": 2, "식상": 1, "재성": 3, "관성": 1, "인성": 1}) == "재성"
    assert classify_wealth_type({"비겁": 2, "식상": 2, "재성": 2, "관성": 2, "인성": 2}) == "균형"
    assert classify_wealth_type({}) == "균형"
    assert classify_day_relation("子", "午") == "충"
    assert classify_day_relation("子", "丑") == "합"   # 육합
    assert classify_day_relation("申", "子") == "합"   # 삼합 반합
    assert classify_day_relation("子", "酉") == "마찰"  # 파
    assert classify_day_relation("子", "子") == "동일"
    assert classify_day_relation("子", "寅") == "무관"


def test_market_unknown_falls_back_to_neutral():
    rep = build_report(day_master="甲", today_sipsin="편재", today_ji_sipsin="정재", day_relation="무관",
                       wealth_type="재성", market={"status": "error", "change_percent": None, "session_date": None},
                       target_date=TARGET)
    assert rep["market_point"] == F.MARKET_POINT_UNKNOWN
    assert "직전 장이 오르" not in rep["investment_fortune"]
    assert "직전 장이 밀리" not in rep["investment_fortune"]


def test_market_direction_fixed_for_the_day(monkeypatch):
    calls = []

    def fake(target_date):
        calls.append(target_date)
        return {"session_date": "2026-09-23", "change_percent": 0.9 if len(calls) == 1 else -3.0}

    monkeypatch.setattr(indicators, "_fetch_prev_session_change", fake)
    first = indicators.get_daily_market_direction(TARGET, now=0)
    later = indicators.get_daily_market_direction(TARGET, now=12 * 3600)  # 같은 날 12시간 뒤
    assert first == later and len(calls) == 1


def test_market_direction_error_retries_after_short_ttl(monkeypatch):
    def boom(target_date):
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(indicators, "_fetch_prev_session_change", boom)
    assert indicators.get_daily_market_direction(TARGET, now=0)["status"] == "error"
    monkeypatch.setattr(indicators, "_fetch_prev_session_change",
                        lambda d: {"session_date": "2026-09-23", "change_percent": 0.9})
    assert indicators.get_daily_market_direction(TARGET, now=10)["status"] == "error"   # TTL 안
    assert indicators.get_daily_market_direction(TARGET, now=301)["status"] == "ok"     # TTL 후 재시도


def test_prev_session_excludes_target_day(monkeypatch):
    import pandas as pd
    import yfinance as yf

    idx = pd.to_datetime(["2026-09-22", "2026-09-23", "2026-09-28"]).tz_localize("Asia/Seoul")

    class FakeTicker:
        def __init__(self, t):
            pass

        def history(self, **kw):
            return pd.DataFrame({"Close": [100.0, 101.0, 90.0]}, index=idx)

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    # 9/28 당일 봉(장중일 수 있음)은 제외 → 9/23 종가 기준 +1.00%
    assert _real_fetch_prev_session_change("2026-09-28") == {"session_date": "2026-09-23", "change_percent": 1.0}


def test_api_response_shape_unchanged_and_fast():
    body = {"year": 1990, "month": 5, "day": 15, "hour": 14, "minute": 30, "gender": "female", "target_date": TARGET}
    client.post("/api/v1/wealth/analysis", json=body)  # 워밍업
    t = time.perf_counter()
    r = client.post("/api/v1/wealth/analysis", json=body)
    elapsed = time.perf_counter() - t
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"status", "is_fallback", "content_type", "target_date", "birth_time_known",
                      "day_master", "saju_info", "data"}
    assert j["is_fallback"] is False and j["content_type"] == "daily_finance"
    d = j["data"]
    assert set(d) == {"market", "market_point", "investment_fortune", "consumption_fortune",
                      "money_flow", "caution_point", "investment_behavior"}
    assert set(d["market"]) == {"indices", "is_live"}
    assert set(d["investment_behavior"]) == {"tendency", "aggressiveness", "chase_risk", "spending_tendency"}
    assert "9월 23일(수)" in d["market_point"]
    assert elapsed < 0.2  # CI 여유치. 로컬 실측 p50≈16ms


def test_same_person_same_day_is_stable():
    a, _ = analyze_daily_finance(1990, 5, 15, 14, 30, target_date=TARGET)
    b, _ = analyze_daily_finance(1990, 5, 15, 14, 30, target_date=TARGET)
    assert a == b
