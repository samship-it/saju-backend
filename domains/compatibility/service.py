"""궁합 — 두 원국 계산 → 관계 엔진 → 세부/종합 점수 → 8단계 한줄평(자연어 레이어에서 선택) + AI 해석."""
from typing import Dict, Any, Tuple

from core.saju_base import calculate_saju
from core.constants import compat_band
from domains.compatibility.engine import calculate_compatibility_interactions
from shared.ai_client import call_gemini_json
from shared.persona_map import persona_prompt
from shared.fortune_cache import get_or_create
from shared.public import person_summary

_SYSTEM = (
    "당신은 2030 세대를 위한 궁합 화자입니다. 제공된 세부 점수와 관계 요소만 근거로 해석합니다. "
    "점수와 한줄평은 이미 정해져 있으니 바꾸지 말고, 그 방향에 맞춰 각 영역을 구체적으로 설명합니다. "
    "사주 용어 노출 금지. 유효한 JSON 만 출력합니다."
)

_FIELDS = ["overall", "love", "communication", "conflict", "conflict_resolution", "economy", "relationship_advice"]


def _fallback(interactions: Dict[str, Any]) -> dict:
    return {
        "overall": "서로의 결이 달라 보여도, 그 다름이 오히려 서로를 채워주는 조합입니다. 대화로 이견을 좁힐수록 시너지가 커집니다. 급하게 결론 내기보다 시간을 두고 맞춰가면 관계가 단단해집니다. 각자의 페이스를 존중하는 게 첫 번째 규칙이에요. 함께 있을 때 편안함을 느낀다면 그 자체가 좋은 신호입니다.",
        "love": "감정 표현의 방식이 서로 달라서 초반에 오해가 생길 수 있어요. 한 사람은 말로, 다른 사람은 행동으로 애정을 보이는 식입니다. 상대의 언어를 배우려는 태도가 애정운을 끌어올립니다. 스킨십이나 표현을 미루지 말고 자주 확인해 주세요.",
        "communication": "대화의 템포를 맞추는 연습이 필요합니다. 한쪽이 결론부터, 다른 쪽이 과정부터 말하는 스타일이라 답답함이 생길 수 있어요. 끝까지 듣고 요약해 되묻는 습관이 소통을 크게 개선합니다.",
        "conflict": "부딪히는 지점은 주로 일 처리 방식과 우선순위입니다. 감정이 상했을 때 즉시 말하기보다, 한 박자 쉬고 대화하면 갈등이 커지지 않습니다.",
        "conflict_resolution": "갈등이 생기면 '누가 맞냐'가 아니라 '무엇을 원하냐'로 질문을 바꿔보세요. 상대가 가진 보완 기질(차분함 또는 추진력)을 인정하는 순간 해결이 빨라집니다.",
        "economy": "돈에 대한 감각이 달라서 초반 조율이 필요합니다. 공동 지출과 개인 지출의 경계를 명확히 하고, 큰 결정은 함께 검토하는 규칙을 두면 안정적입니다.",
        "relationship_advice": "서로의 장점을 존중하고 단점을 감싸줄 때 최고의 파트너십이 됩니다. 정기적으로 관계를 점검하는 대화 시간을 만들어보세요.",
    }


_saju_info = person_summary


def analyze_compatibility_report(
    p1_info: Dict[str, Any],
    p2_info: Dict[str, Any],
    relation_type: str = "romantic",
) -> Tuple[dict, bool]:
    s1 = calculate_saju(
        p1_info["year"], p1_info["month"], p1_info["day"],
        p1_info.get("hour"), p1_info.get("minute", 0),
        gender=p1_info.get("gender", "female"), is_lunar=p1_info.get("is_lunar", False),
    )
    s2 = calculate_saju(
        p2_info["year"], p2_info["month"], p2_info["day"],
        p2_info.get("hour"), p2_info.get("minute", 0),
        gender=p2_info.get("gender", "male"), is_lunar=p2_info.get("is_lunar", False),
    )
    interactions = calculate_compatibility_interactions(s1, s2)
    total = interactions["total_score"]
    band = compat_band(total)

    def _gen():
        prompt = f"""[본인 화자]
{persona_prompt(s1.get('day_master'), s1.get('day_branch'))}

[관계 유형] {relation_type}
[본인 일주] {s1.get('day_master')}{s1.get('day_branch')} / [상대 일주] {s2.get('day_master')}{s2.get('day_branch')}
[출생시간 확인] 본인 {s1.get('birth_time_known')} / 상대 {s2.get('birth_time_known')}

[Python 산출 세부 점수 — 이 점수 방향을 지킬 것]
- 종합 {total} → 관계타입 "{band['relation_type']}", 한줄평 "{band['one_liner']}"
- 전체 {interactions['sub_scores']['overall']} / 애정 {interactions['sub_scores']['love']} / 소통 {interactions['sub_scores']['communication']} / 갈등 {interactions['sub_scores']['conflict']} / 경제 {interactions['sub_scores']['economy']}
- 일간 관계: {interactions['day_master_relation']} (합 {interactions['day_master_hap']}, 충 {interactions['day_master_chung']})
- 일지(배우자궁) 관계: {interactions['day_ji_relation']}
- 관계 요소 카운트: {interactions['counts']}
- 긍정 요소: {interactions['positive_factors']}
- 부정 요소: {interactions['negative_factors']}

[규칙] 각 영역 5줄 이상, 구체적으로. 사주 용어 금지. 점수/한줄평은 바꾸지 말 것.

[출력 JSON — 이 구조만]
{{
  "overall": "전체 궁합 설명",
  "love": "애정 궁합 (일지+배우자성+합충+도화 반영)",
  "communication": "소통 궁합 (식상+인성+일간 관계 반영)",
  "conflict": "갈등 요소 (충+형+비겁+상관 반영)",
  "conflict_resolution": "갈등 해결법 (갈등 요소 + 상대의 보완 요소 반영)",
  "economy": "경제 궁합 (재성+비겁+양쪽 재물 구조 반영)",
  "relationship_advice": "관계 조언 (가장 강한 긍정/부정 요소 반영)"
}}"""
        ai, is_fb = call_gemini_json(prompt, _fallback(interactions), system_instruction=_SYSTEM)
        data = _fallback(interactions) if is_fb else ai
        report = {k: str(data.get(k, "")) for k in _FIELDS}
        return {
            "content_type": "궁합",
            "relation_type": relation_type,
            "person1": _saju_info(s1),
            "person2": _saju_info(s2),
            "scores": {
                "total": total,
                **interactions["sub_scores"],
            },
            "relation_type_label": band["relation_type"],
            "one_liner": band["one_liner"],
            "score_band": band["band"],
            "engine_factors": {
                "positive": interactions["positive_factors"],
                "negative": interactions["negative_factors"],
                "day_master_relation": interactions["day_master_relation"],
                "day_ji_relation": interactions["day_ji_relation"],
                "counts": interactions["counts"],
            },
            "report": report,
        }, is_fb

    payload = {
        "p1": {k: p1_info.get(k) for k in ("year", "month", "day", "hour", "minute", "gender", "is_lunar")},
        "p2": {k: p2_info.get(k) for k in ("year", "month", "day", "hour", "minute", "gender", "is_lunar")},
        "rel": relation_type,
    }
    data, is_fb, _ = get_or_create("compatibility", payload, _gen)
    return data, is_fb
