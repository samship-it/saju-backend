"""궁합 — 두 원국 계산 → 관계 엔진 → 세부/종합 점수 + 8단계 한줄평 + AI 해석.

점수·한줄평·관계 요소는 런타임 엔진(`calculate_compatibility_interactions`)이 두 사람의
전체 사주로 계산한다(결정적, API 호출 없음). AI 서술부(report 7필드)는 사전 생성 정적 DB
(`domains/compatibility/data/compatibility_db.json`)에서 일주쌍 키로 조회만 한다.
런타임 Gemini 호출 없음. DB 생성은 `scripts/generate_content_db.py --domain compatibility` 참고.
일주쌍이 DB 에 없으면(일주 계산 실패 등) 사주와 무관한 고정 폴백을 반환한다(is_fallback=True).
"""
from typing import Dict, Any, Tuple

from core.saju_base import calculate_saju
from core.constants import compat_band
from shared.text_format import paragraphize
from shared.public import person_summary
from domains.compatibility.engine import calculate_compatibility_interactions
from domains.compatibility import content_db

_FIELDS = content_db.FIELDS


def _fallback() -> dict:
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

    g1 = s1.get("day_ganji") or ""
    g2 = s2.get("day_ganji") or ""
    entry = content_db.lookup(g1, g2)
    is_fallback = entry is None
    raw = _fallback() if is_fallback else entry
    report = {k: paragraphize(str(raw.get(k, ""))) for k in _FIELDS}

    return {
        "content_type": "궁합",
        "relation_type": relation_type,
        "combo_key": content_db.make_key(g1, g2),
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
    }, is_fallback
