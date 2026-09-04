"""오늘의 운세 (DAILY_FORTUNE) — 무료 기본 운세.

런타임 Gemini 호출 없음. 사전 생성된 정적 DB(`domains/daily/data/daily_db.json`)에서
(내 일주 × 오늘 일진) 키로 즉시 조회한다. DB 생성은 `scripts/generate_content_db.py` 참고.
조합이 DB 에 없으면 사주와 무관한 고정 폴백을 반환한다(is_fallback=True).
"""
from typing import Dict, Any, Tuple

from core.constants import score_to_emoji, score_to_band
from shared.text_format import paragraphize
from domains.daily.content_db import lookup

CONTENT_TYPE = "daily_fortune"


def _fallback(saju: Dict[str, Any]) -> dict:
    return {
        "overall_score": 60,
        "money_score": 58,
        "love_score": 60,
        "work_study_score": 62,
        "summary": {
            "overall": (
                "오늘은 큰 굴곡 없이 흐르는 하루예요. 마음이 앞서기보다 지금 손에 쥔 일을 "
                "차분히 정리할 때 흐름이 매끄러워집니다. 무리한 확장보다 이미 벌여둔 일을 "
                "매듭짓는 쪽이 유리하고, 사람들과의 대화에서도 한 박자 늦춰 듣는 태도가 도움이 됩니다. "
                "저녁에는 오늘 한 선택을 짧게 돌아보는 시간을 가져보세요."
            ),
            "money": (
                "돈과 관련해서는 새로 벌이기보다 새는 곳을 막는 날입니다. 구독·자동결제처럼 "
                "무심코 빠져나가던 지출을 점검하면 생각보다 여유가 생깁니다. 큰 결제나 투자 판단은 "
                "하루 미루고, 정보를 한 번 더 확인한 뒤 움직이세요. 작은 절약이 이번 주 흐름을 바꿉니다."
            ),
            "love_single": (
                "새로운 사람보다 이미 아는 관계에서 편안함을 느끼는 하루예요. 급하게 밀어붙이기보다 "
                "가벼운 안부와 공감으로 거리를 좁히는 편이 낫습니다. 오늘 나눈 사소한 대화가 나중에 "
                "의미 있는 연결로 이어질 수 있으니 표현을 아끼지 마세요."
            ),
            "love_couple": (
                "연인과는 큰 이벤트보다 일상의 결을 맞추는 날입니다. 상대의 말을 끝까지 듣고 "
                "감정을 먼저 확인해 주면 갈등이 생길 여지가 줄어듭니다. 서운함이 있다면 쌓아두지 말고 "
                "부드럽게 꺼내 보세요. 오늘의 배려가 관계의 안정감을 키웁니다."
            ),
            "work_study": (
                "일과 공부는 새로 벌이기보다 마무리에 강한 날입니다. 밀린 정리, 검토, 복습에 시간을 "
                "쓰면 성취감이 큽니다. 주변의 지적이나 피드백에 흔들리지 말고 내 페이스를 지키세요. "
                "연령대와 상황에 맞춰, 지금 단계에서 꼭 필요한 한 가지에 집중하는 것이 효율적입니다."
            ),
        },
        "keywords": ["정리", "점검", "소통"],
        "recommended_action": (
            "오늘 안에 끝낼 수 있는 작은 일 하나를 골라 완결 지어 보세요. 그리고 최근 새어나가던 "
            "지출 항목을 딱 하나만 정리하면 하루의 흐름이 정돈됩니다."
        ),
    }


def _shape(ai: dict) -> dict:
    def s(v, d=60):
        try:
            return max(0, min(100, int(round(float(v)))))
        except Exception:
            return d

    summ = ai.get("summary") or {}
    kws = ai.get("keywords") or []
    kws = [str(k) for k in kws][:3]
    while len(kws) < 3:
        kws.append("")
    overall = s(ai.get("overall_score"))
    return {
        "overall_score": overall,
        "money_score": s(ai.get("money_score")),
        "love_score": s(ai.get("love_score")),
        "work_study_score": s(ai.get("work_study_score")),
        "score_emoji": score_to_emoji(overall),
        "score_band": score_to_band(overall),
        "summary": {
            "overall": paragraphize(str(summ.get("overall", ""))),
            "money": paragraphize(str(summ.get("money", ""))),
            "love_single": paragraphize(str(summ.get("love_single", ""))),
            "love_couple": paragraphize(str(summ.get("love_couple", ""))),
            "work_study": paragraphize(str(summ.get("work_study", ""))),
        },
        "keywords": kws,
        "recommended_action": str(ai.get("recommended_action", "")),
    }


def generate_daily_fortune(saju_data: Dict[str, Any]) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환.

    (내 일주 × 오늘 일진) 조합으로 사전 생성 DB 에서 조회한다. Gemini 호출 없음.
    """
    day_ganji = saju_data.get("day_ganji") or ""
    iljin_ganji = (saju_data.get("today_ganji") or {}).get("day") or ""

    entry = lookup(day_ganji, iljin_ganji)
    if not entry:
        return _shape(_fallback(saju_data)), True
    return _shape(entry), False
