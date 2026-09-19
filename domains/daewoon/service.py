"""10년 대운(DAEWOON) — 평생운세와 별개의 독립 유료 모듈.

런타임 Gemini 호출 없음. 이미 존재하는 정적 DB(lifelong_stage_detail_db.json
14,000건)와 실시간 계산(daewoon_step_facts·get_seewoon_list)만 재사용한다.

target_age(선택한 대운 나이)를 받아 그 나이를 포함하는 대운 단계를 찾는다
(_step_covering_age, domains/lifelong/life_periods.py 재사용 — 미지정 시 현재
실제 나이 기준). 연령대별 분기(청소년기 25세 미만 / 성인기 25세 이상)는
target_age 자체를 기준으로 한다.

응답 스키마:
- daewoon_header: "{간지 한글}({간지 한자}) 대운"
- landscape_scene: domains/daewoon/landscape.py 재사용
- summary: lookup_stage_detail().event_narrative 재사용(총평)
- keywords: 지배 십신군 기준 고정 3개(content.py)
- domain_analysis: career_or_study(연령대 분기)/wealth_flow/relationship/family
  — 전부 지배 십신군 기준 실시간 합성(content.py)
- timeline_phases: 8단계 대운 전부 + 각 단계의 10년치 세운(연도·간지) 나열
  (get_seewoon_list) — 프론트가 세운 옆에 "OOOO년 총운 보러가기" 버튼을 건다.
- decade_tasks: 지배 십신군 기준 고정 3개(Action Plan)
"""
from typing import Any, Dict, List, Optional, Tuple

from core.saju_base import calculate_saju
from core.daewoon import GAN as GAN_KO_LIST, GAN_H, JI as JI_KO_LIST, JI_H, daewoon_step_facts, get_seewoon_list
from domains.daewoon.content import (
    DECADE_TASKS,
    KEYWORDS,
    build_career_or_study,
    build_family,
    build_relationship,
    build_wealth_flow,
)
from domains.daewoon.landscape import build_decade_landscape
from domains.lifelong.content_db import lookup_stage_detail
from domains.lifelong.life_periods import _step_covering_age
from domains.lifelong.service import _current_step, _fallback_stage_detail, _ilju
from shared.public import person_summary

CONTENT_TYPE = "daewoon_period"
ADULT_AGE_THRESHOLD = 25

GAN_KO: Dict[str, str] = dict(zip(GAN_H, GAN_KO_LIST))
JI_KO: Dict[str, str] = dict(zip(JI_H, JI_KO_LIST))


def _ganji_label(ganji: str) -> str:
    if not ganji or len(ganji) < 2:
        return ganji
    gan_ko = GAN_KO.get(ganji[0], "")
    ji_ko = JI_KO.get(ganji[1], "")
    return f"{gan_ko}{ji_ko}({ganji})" if gan_ko and ji_ko else ganji


def _build_timeline_phases(
    facts: List[Dict[str, Any]], daewoon_num: int, birth_year: int, selected_step: int, current_step: int,
) -> List[Dict[str, Any]]:
    phases = []
    for f in facts:
        step = f["step"]
        start_age = daewoon_num + (step - 1) * 10
        decade_start_year = birth_year + start_age
        years = [
            {"year": y["year"], "age": start_age + i, "ganji": y["ganji"]}
            for i, y in enumerate(get_seewoon_list(decade_start_year, 10))
        ]
        phases.append({
            "step": step,
            "age_range": [start_age, start_age + 9],
            "ganji": f["ganji"],
            "ganji_label": _ganji_label(f["ganji"]),
            "is_selected": step == selected_step,
            "is_current": step == current_step,
            "years": years,
        })
    return phases


def analyze_daewoon_period(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    target_age: Optional[int] = None,
    target: str = "me",
    love_status: Optional[str] = None,
) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환. target_age 미지정 시 실제 현재 나이 기준 대운으로
    계산한다. target('me'|'partner')는 어떤 birth 데이터를 쓸지는 호출부(프론트)가 이미
    결정해서 넘기므로 여기서는 응답에 그대로 echo만 한다(계산 로직에 영향 없음)."""
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
    current_step = _current_step(daewoon_num, age)

    effective_age = target_age if target_age is not None else age
    step = _step_covering_age(facts, daewoon_num, effective_age)
    fact = next((f for f in facts if f["step"] == step), facts[0])
    start_age = daewoon_num + (step - 1) * 10
    is_selected_current = step == current_step
    group = fact["sipsin_group"]

    is_fallback = False
    entry = lookup_stage_detail(ilju, fact["sipsin_group"], fact["branch_relation"], step)
    if entry is None:
        is_fallback = True
        entry = _fallback_stage_detail(fact["sipsin_group"], step)

    domain_analysis = {
        "career_or_study": build_career_or_study(group, is_adult=effective_age >= ADULT_AGE_THRESHOLD),
        "wealth_flow": build_wealth_flow(group),
        "relationship": build_relationship(group, love_status, is_selected_current),
        "family": build_family(group),
    }

    data = {
        "daewoon_header": f"{_ganji_label(fact['ganji'])} 대운",
        "landscape_scene": build_decade_landscape(saju.get("day_master_elem", ""), fact["ganji"])["scene"],
        "summary": entry.get("event_narrative", ""),
        "keywords": list(KEYWORDS.get(group, KEYWORDS["비겁"])),
        "domain_analysis": domain_analysis,
        "timeline_phases": _build_timeline_phases(facts, daewoon_num, year, step, current_step),
        "decade_tasks": list(DECADE_TASKS.get(group, DECADE_TASKS["비겁"])),
        "step": step,
        "age_range": [start_age, start_age + 9],
        "target_age": effective_age,
        "target": target if target in ("me", "partner") else "me",
        "is_current_decade": is_selected_current,
    }

    return {
        "content_type": CONTENT_TYPE,
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, is_fallback
