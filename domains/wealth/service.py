"""오늘의 재테크 사주 (DAILY 재테크) — 룰베이스 정적 엔진.

런타임 AI 호출 없음. 흐름: 명리 코어(calculate_saju) → 원국 유형·오늘 십신 추출 → engine.build_report.
시장 데이터(확정된 나스닥 마감·원·달러 등락)는 domains.market 이 재테크 날짜(KST 09:00)마다
고정해 넘겨주고, 엔진은 그 값이 오늘 아침 국내 장에 미치는 태도만 고른다.
'주가가 오른다/내린다' 예측은 하지 않는다. 점수는 없다.
"""
import logging
from typing import Any, Dict, Tuple

from config import wealth_asof_date
from core.saju_base import calculate_saju
from domains.market.cron_market import get_market_snapshot
from domains.market.indicators import get_daily_market_direction
from domains.wealth.engine import (
    build_report, classify_day_relation, classify_wealth_type, morning_stance,
)
from shared.public import person_summary

logger = logging.getLogger(__name__)

CONTENT_TYPE = "daily_finance"


def _market_direction(target_date: str) -> Dict[str, Any]:
    info = get_daily_market_direction(target_date)
    stance = morning_stance(info.get("change_percent"), info.get("fx_change_percent"))
    return {**info, "direction": stance}


def analyze_daily_finance(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    target_date=None,
) -> Tuple[dict, bool]:
    # 날짜를 비우면 자정이 아니라 한국 증시 개장(09:00)에 재테크 하루가 바뀐다.
    if not target_date:
        target_date = wealth_asof_date()
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar, target_date=target_date)
    t_date = saju.get("target_date")
    ilwoon = saju.get("ilwoon_sipsin") or {}
    wealth_type = classify_wealth_type((saju.get("derived") or {}).get("group_power") or {})
    today_day_pillar = (saju.get("today_ganji") or {}).get("day") or ""
    today_branch = today_day_pillar[1] if len(today_day_pillar) >= 2 else None

    market = _market_direction(t_date)
    report = build_report(
        day_master=saju.get("day_master"),
        today_sipsin=ilwoon.get("gan"),
        today_ji_sipsin=ilwoon.get("ji"),
        day_relation=classify_day_relation(saju.get("day_branch"), today_branch),
        wealth_type=wealth_type,
        market=market,
        target_date=t_date,
    )

    # 응답 규격 유지: market.indices / is_live 는 기존 스냅샷 그대로
    snapshot = get_market_snapshot(t_date)
    data = {
        "market": {"indices": snapshot.get("indices"), "is_live": bool(snapshot.get("is_live"))},
        **report,
    }
    return {
        "content_type": CONTENT_TYPE,
        "target_date": t_date,
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, False
