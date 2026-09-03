"""사주 정밀 데이터를 Gemini 프롬프트 입력 블록으로 직렬화.

원칙: Python이 계산한 값만 넘긴다. AI는 이 값을 근거로만 점수/문구를 만든다.
"""
import json
from typing import Any, Dict, List, Optional


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def engine_block(saju: Dict[str, Any], domains: Optional[List[str]] = None) -> str:
    d = saju.get("derived", {}) or {}
    ds = d.get("domain_strength", {}) or {}
    if domains:
        ds = {k: v for k, v in ds.items() if k in domains}

    lines = [
        "[사주 정밀 데이터 — Python 만세력 엔진 산출값. 이 값만 근거로 사용]",
        f"- 일간/일지: {saju.get('day_master')}({saju.get('day_master_elem')}) / {saju.get('day_branch')}",
        f"- 원국 사주: 년 {saju.get('year_ganji')} · 월 {saju.get('month_ganji')} · 일 {saju.get('day_ganji')} · 시 {saju.get('time_ganji') or '미상'}",
        f"- 출생시간 확인 여부(birth_time_known): {saju.get('birth_time_known')}",
        f"- 오행 분포: {_j(saju.get('five_elements'))}",
        f"- 십신(원국): {_j(saju.get('sipsin'))}",
        f"- 십신 그룹 세력(지장간 가중): {_j(d.get('group_power'))}",
        f"- 일간 강약: {_j(saju.get('strength'))}",
        f"- 격국: {_j(saju.get('gyeokguk'))}",
        f"- 12운성: {_j(saju.get('twelve_unseong'))}",
        f"- 신살: {_j(saju.get('sinsal', {}).get('found'))}",
        f"- 배우자성: {_j(saju.get('spouse_star'))}",
        f"- 합충형파해(원국): {_j(saju.get('branch_relations', {}).get('counts'))}",
        f"- 대운(현재): {_j(saju.get('current_daewoon'))}",
        f"- 세운({saju.get('target_year')}): {_j(saju.get('sewoon_sipsin'))}",
        f"- 일운({saju.get('target_date')}): 일진 {saju.get('today_ganji', {}).get('day')}, 일간대비 십신 {_j(saju.get('ilwoon_sipsin'))}",
        f"- 활성 요소(active_elements): {_j(d.get('active_elements'))}",
        f"- 분야별 작용 강도 지표: {_j(ds)}",
        f"- score_components: {_j(d.get('score_components'))}",
        f"- 나이/생애단계: 만 {saju.get('age')}세 / {saju.get('life_stage')}",
        f"- 상대방 존재(partner_exists): {saju.get('partner_exists')}",
    ]
    return "\n".join(lines)


SCORING_RULES = (
    "[점수화 규칙]\n"
    "- 위 '작용 강도 지표'의 긍정/부정 방향과 강도를 종합해 분야별 0~100 정수 점수를 산출한다.\n"
    "- 사주 데이터를 새로 계산하거나 근거 없이 점수를 만들지 말 것. 제공된 강도 데이터만 근거로 사용.\n"
    "- 강도를 중간값으로 뭉개지 말 것. 매우 강하면 90 이상, 매우 약하면 40 이하도 허용.\n"
    "- 점수와 문구의 방향은 일치. 높은 점수에도 현실적 주의사항, 낮은 점수에도 활용 가능한 행동을 담는다.\n"
    "- 모든 해석 문구는 최소 5줄 이상. 사주 용어 노출 금지."
)
