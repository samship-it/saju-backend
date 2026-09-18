"""10년 대운(DECADE_DAEWOON) — 평생운세의 대운 카드 '자세히 보기'를 완전히 흡수한
전용 유료 모듈.

런타임 Gemini 호출 없음. 이미 존재하는 정적 DB(lifelong_stage_detail_db.json
14,000건, lifelong_domains_db.json 2,400건)와 실시간 계산(daewoon_step_facts)만
재사용해서 만든다 — 콘텐츠는 100% 기존 자산 재활용, 새로 생성한 건 없음(사용자
확인·승인: "기존 자세히 보기 콘텐츠를 이 모듈 스키마로 완전 흡수/통합").

5개 필드 매핑:
1) decade_landscape: 이 10년 간지 기준 풍경(domains/daewoon/landscape.py, 새 실시간
   합성 — day_master_elem은 기존 landscape.py의 SUBJECT_IMAGE 재사용, 배경만
   이 대운 간지의 천간 오행으로 새로 고름).
2) overall_summary: lookup_stage_detail().event_narrative 그대로.
3) turning_points: 같은 조회의 나머지 3필드(strategy/obstacle/turning_point)를
   [이 시기의 시작 / 핵심 전략 / 경계할 점] 3단계로 재구성. 새 문장 생성 없음 —
   기존 필드에 시간 흐름 프레이밍(라벨)만 입힌다.
4) domain_flows: lookup_domains() + lifelong.service._shape_domains() 를 '그
   대운 단계 그대로'(평생운세는 늘 current_step만 보여주지만, 여기서는 요청받은
   임의의 step 1~8 아무거나 조회 가능 — 같은 DB, 다른 축 사용법).
5) challenge: domains/daewoon/challenge.py, 지배 십신군 기준 새 고정 문구(3번과
   안 겹치는 5번째 관점).
"""
from typing import Any, Dict, Optional, Tuple

from core.saju_base import calculate_saju
from core.daewoon import daewoon_step_facts
from domains.daewoon.challenge import build_challenge
from domains.daewoon.landscape import build_decade_landscape
from domains.lifelong.content_db import lookup_domains, lookup_stage_detail
from domains.lifelong.service import (
    STAGE_LABELS,
    _current_step,
    _fallback_stage_detail,
    _ilju,
    _shape_domains,
)
from shared.public import person_summary

CONTENT_TYPE = "daewoon_period"


def analyze_daewoon_period(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    step: Optional[int] = None,
) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환. step 미지정 시 그 사람의 현재 나이로 계산한
    '지금 이 순간의 대운'을 기본값으로 쓴다(평생운세 카드를 거치지 않고 메뉴에서
    바로 들어온 경우)."""
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)
    ilju = _ilju(saju)
    day_master = saju.get("day_master", "")
    day_branch = saju.get("day_branch", "")
    month_ganji = saju.get("month_ganji", "")
    daewoon = saju.get("daewoon") or {}
    daewoon_num = daewoon.get("daewoon_num", 1)
    is_forward = daewoon.get("direction") == "순행"
    age = saju.get("age", 0) or 0

    facts = daewoon_step_facts(day_master, day_branch, month_ganji, is_forward, count=8)

    if step is None:
        step = _current_step(daewoon_num, age)
    step = max(1, min(8, int(step)))
    fact = next((f for f in facts if f["step"] == step), facts[0])
    start_age = daewoon_num + (step - 1) * 10

    is_fallback = False

    entry = lookup_stage_detail(ilju, fact["sipsin_group"], fact["branch_relation"], step)
    if entry is None:
        is_fallback = True
        entry = _fallback_stage_detail(fact["sipsin_group"], step)

    domains_entry = lookup_domains(ilju, fact["sipsin_group"], step)
    life_domains, domains_used_fallback = _shape_domains(domains_entry)
    if domains_used_fallback:
        is_fallback = True

    data = {
        "decade_landscape": build_decade_landscape(saju.get("day_master_elem", ""), fact["ganji"]),
        "overall_summary": entry.get("event_narrative", ""),
        # 3단계 전환점 — 기존 strategy/obstacle/turning_point 3필드를 시간 흐름
        # 프레이밍으로 재구성(새 문장 생성 없음, 사용자 확인·승인).
        "turning_points": [
            {"label": "이 시기의 시작", "text": entry.get("turning_point", "")},
            {"label": "이 시기를 관통하는 핵심 전략", "text": entry.get("strategy", "")},
            {"label": "경계할 점", "text": entry.get("obstacle", "")},
        ],
        "domain_flows": life_domains,
        "challenge": build_challenge(fact["sipsin_group"]),
        "step": step,
        "stage_label": STAGE_LABELS.get(step, ""),
        "age_range": [start_age, start_age + 9],
        "ganji": fact["ganji"],
    }

    return {
        "content_type": CONTENT_TYPE,
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, is_fallback
