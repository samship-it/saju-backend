"""10년 대운(DAEWOON) — 평생운세와 별개의 독립 유료 모듈.

런타임 Gemini 호출 없음. 이미 존재하는 정적 DB(lifelong_stage_detail_db.json
14,000건)와 실시간 계산(daewoon_step_facts·get_seewoon_list)만 재사용한다.

target_age(선택한 대운 나이)를 받아 그 나이를 포함하는 대운 단계를 찾는다
(_step_covering_age, domains/lifelong/life_periods.py 재사용 — 미지정 시 현재
실제 나이 기준).

domain_analysis는 target_age로 두 번 분기한다:
- 20세 미만(CHILD_AGE_THRESHOLD): [학업/성장]·[용돈/경제관념]·[교우/친구관계]·
  [부모/가정환경] 4개 영역으로 완전히 대체(build_child_domains, content.py) —
  "직장"·"자산 관리"·"배우자"·"연애" 등 성인 전용 단어는 절대 쓰지 않는다.
- 20세 이상(성인기): 기존 career_or_study/wealth_flow/relationship/family
  구조를 그대로 쓴다. 그 안에서 career_or_study 자체의 문구 모양(성인 vs
  청소년)은 ADULT_AGE_THRESHOLD(25)로 별도 분기 — CHILD_AGE_THRESHOLD와는
  다른 축이다.

content.py 콘텐츠 매칭은 이제 5분류(sipsin_group)가 아니라 십신 10종(sipsin,
daewoon_step_facts가 이미 계산해 두는 값)을 기준으로 한다 — 정재/편재처럼 같은
그룹 안의 두 십신이 동일한 문구를 내는 문제를 없애기 위함. lookup_stage_detail/
_fallback_stage_detail(lifelong 모듈의 정적 DB 조회)만 예외적으로 계속
sipsin_group(5분류)을 쓴다 — 그 DB 자체가 5분류로 만들어져 있어 daewoon 쪽
사정으로 건드리지 않는다.

응답 스키마:
- daewoon_header: "{간지 한글}({간지 한자}) 대운"
- landscape_scene / saju_relation: domains/daewoon/landscape.py 재사용(십신 10종 기준)
- summary: lookup_stage_detail().event_narrative 재사용(총평, 5분류 DB)
- keywords / decade_tasks: 십신 10종 기준 고정 문구(content.py)
- domain_analysis: 위 연령 분기 참고 — 십신 10종 기준 실시간 합성(content.py)
- decade_theme: "이 10년의 풍경" 하단 안내 블록의 2·3단계(content.py
  build_decade_theme) — 1단계(오행/십신 정의)는 saju_relation이 맡는다.
  2단계는 십신 핵심 키워드·주요 변화 영역, 3단계는 음양 쌍 십신(정/편)
  기반으로 대운 영향이 약한 영역의 흐름을 안내한다.
- timeline_phases: 8단계 대운 전부 + 각 단계의 10년치 세운(연도·간지) 나열
  (get_seewoon_list) — 프론트가 세운 옆에 "OOOO년 총운 보러가기" 버튼을 건다.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.saju_base import calculate_saju
from core.daewoon import GAN as GAN_KO_LIST, GAN_H, JI as JI_KO_LIST, JI_H, daewoon_step_facts, get_seewoon_list
from domains.daewoon.content import (
    DECADE_TASKS,
    KEYWORDS,
    build_career_or_study,
    build_child_domains,
    build_decade_theme,
    build_family,
    build_relationship,
    build_transition_back_domains,
    build_transition_front_domains,
    build_wealth_flow,
)
from domains.daewoon.landscape import build_decade_landscape
from domains.lifelong.content_db import lookup_stage_detail
from domains.lifelong.life_periods import _step_covering_age
from domains.lifelong.service import _current_step, _fallback_stage_detail, _ilju
from shared.public import person_summary

CONTENT_TYPE = "daewoon_period"
ADULT_AGE_THRESHOLD = 25
# 20세 미만은 domain_analysis 구조 자체가 [학업/성장]·[용돈/경제관념]·[교우/친구관계]·
# [부모/가정환경]으로 완전히 바뀐다(build_child_domains). 20세 이상(성인기)은 기존
# career_or_study/wealth_flow/relationship/family 구조를 그대로 쓴다 — ADULT_AGE_THRESHOLD(25)는
# 그 안에서 career_or_study 필드 모양(성인 vs 청소년 문구)만 결정할 뿐, 이 게이트와는 무관하다.
CHILD_AGE_THRESHOLD = 20

# 과도기 대운 — 대운 "시작 나이"가 이 범위(15~19세)에 걸리면, 그 10년 안에서
# 성인 나이를 지나며 학생에서 사회초년생으로 바뀐다. 이 경우 CHILD_AGE_THRESHOLD(20)
# 대신 TRANSITION_SPLIT_AGE(22)로 그 10년 내부를 다시 한번 나눠 전반부(학생기)/
# 후반부(사회진출기)를 별도 문구로 해석한다(content.py의 build_transition_front_domains/
# build_transition_back_domains). 대운 "시작"이 아니라 target_age가 15~19인 것과는
# 다른 조건이다 — 예: 대운이 10세에 시작해 19세까지만 이어지는 경우는 과도기가 아니다
# (그 10년 안에 성인 나이로의 전환이 없으므로).
TRANSITION_START_MIN = 15
TRANSITION_START_MAX = 19
TRANSITION_SPLIT_AGE = 22

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
    sipsin = fact["sipsin"]  # 천간 기준 십신 10종 — content.py 매칭 키

    is_fallback = False
    entry = lookup_stage_detail(ilju, fact["sipsin_group"], fact["branch_relation"], step)
    if entry is None:
        is_fallback = True
        entry = _fallback_stage_detail(fact["sipsin_group"], step)

    is_transition_decade = TRANSITION_START_MIN <= start_age <= TRANSITION_START_MAX
    if is_transition_decade:
        if effective_age < TRANSITION_SPLIT_AGE:
            domain_analysis = build_transition_front_domains(sipsin)
        else:
            domain_analysis = build_transition_back_domains(sipsin, love_status, is_selected_current)
    elif effective_age < CHILD_AGE_THRESHOLD:
        domain_analysis = build_child_domains(sipsin)
    else:
        domain_analysis = {
            "career_or_study": build_career_or_study(sipsin, is_adult=effective_age >= ADULT_AGE_THRESHOLD),
            "wealth_flow": build_wealth_flow(sipsin),
            "relationship": build_relationship(sipsin, love_status, is_selected_current),
            "family": build_family(sipsin),
        }

    landscape = build_decade_landscape(saju.get("day_master_elem", ""), fact["ganji"], sipsin)

    data = {
        "daewoon_header": f"{_ganji_label(fact['ganji'])} 대운",
        "landscape_scene": landscape["scene"],
        "saju_relation": landscape["saju_relation"],
        "summary": entry.get("event_narrative", ""),
        "keywords": list(KEYWORDS.get(sipsin, KEYWORDS["비견"])),
        "domain_analysis": domain_analysis,
        "decade_theme": build_decade_theme(sipsin),
        "timeline_phases": _build_timeline_phases(facts, daewoon_num, year, step, current_step),
        "decade_tasks": list(DECADE_TASKS.get(sipsin, DECADE_TASKS["비견"])),
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
