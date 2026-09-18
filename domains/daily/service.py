"""오늘의 운세 (DAILY_FORTUNE) — 무료 기본 운세.

런타임 Gemini 호출 없음. 사전 생성된 정적 DB(`domains/daily/data/daily_db.json`)에서
(내 일주 × 오늘 일진) 키로 즉시 조회한다. DB 생성은 `scripts/generate_content_db.py` 참고.
조합이 DB 에 없으면 사주와 무관한 고정 폴백을 반환한다(is_fallback=True).

애정/직업 상태 분기(love_status/job_status)는 domains/daily/status_variants.py 참고 —
DB 축을 새로 늘리지 않고, 이미 계산돼 있는 trigger_bucket(woon_modifier)에 얹은 작은
고정 표로 처리한다. 상태값이 없거나 모르는 값이면 기존 일반 텍스트로 폴백한다.
"""
from typing import Dict, Any, Optional, Tuple

from core.constants import score_to_emoji, score_to_band
from shared.text_format import paragraphize
from domains.daily.content_db import lookup
from domains.daily.social_template import build_social_summary
from domains.daily.status_variants import JOB_STATUSES, LOVE_STATUSES, resolve_job_levelup, resolve_married_love
from domains.daily.woon_modifier import compute_woon_modifier

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


def _shape(ai: dict, saju_data: Dict[str, Any], modifier: Dict[str, Any]) -> dict:
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
        # 한줄평은 이제 static DB 원문이 아니라 woon_modifier가 대운/세운/일운/신살/영역별
        # delta를 전부 종합해 만든 문장을 100% 사용한다(HEADLINE_TABLE, AI 미관여).
        "headline": modifier["headline"],
        "summary": {
            "overall": paragraphize(str(summ.get("overall", ""))),
            "money": paragraphize(str(summ.get("money", ""))),
            "love_single": paragraphize(str(summ.get("love_single", ""))),
            "love_couple": paragraphize(str(summ.get("love_couple", ""))),
            "work_study": paragraphize(str(summ.get("work_study", ""))),
            # Social Network(사회운) - daily_db.json 정적 DB에는 없는 필드. woon_modifier가
            # 계산한 trigger_group/trigger_bucket으로 generate_daily_fortune()에서 채운다.
            # headline과는 서로 다른 문구 세트(HEADLINE_TABLE vs SOCIAL_TEMPLATES)를 쓰므로
            # 같은 신호를 가리켜도 문장이 겹치지 않는다.
            "social": "",
        },
        "keywords": kws,
        "recommended_action": str(ai.get("recommended_action", "")),
    }


# 각 점수를 어떤 델타로 조정할지 - overall만 3레이어 전체 합(score_delta)을 쓰고,
# money/love/work_study는 그 점수와 관련된 십신군만 반영한 도메인별 델타를 쓴다
# (예전엔 score_delta 하나를 4개에 균등 복사했었음 - woon_state가 가리키는 영역과
# 무관하게 다 같이 움직이는 문제가 있었다).
_SCORE_DELTA_KEY = {
    "overall_score": "score_delta",
    "money_score": "money_delta",
    "love_score": "love_delta",
    "work_study_score": "work_study_delta",
}


def _apply_woon_modifier(entry: Dict[str, Any], modifier: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(entry)
    for key, delta_key in _SCORE_DELTA_KEY.items():
        base = out.get(key, 60)
        try:
            base = int(round(float(base)))
        except (TypeError, ValueError):
            base = 60
        out[key] = max(0, min(100, base + modifier[delta_key]))
    return out


def _resolve_love_text(summ: Dict[str, str], love_status: Optional[str], trigger_bucket: Optional[str]) -> str:
    """love_status 별 1:1 문구. 모르는 값/미지정이면 기존 방식(single+couple 병기)으로 폴백."""
    single = summ.get("love_single", "")
    couple = summ.get("love_couple", "")
    if love_status == "solo":
        return single
    if love_status == "in_relationship":
        return couple
    if love_status == "married":
        return resolve_married_love(trigger_bucket)
    return "\n\n".join(t for t in (single, couple) if t)


def generate_daily_fortune(
    saju_data: Dict[str, Any],
    love_status: Optional[str] = None,
    job_status: Optional[str] = None,
) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환.

    (내 일주 × 오늘 일진) 조합으로 사전 생성 DB 에서 조회한다. Gemini 호출 없음.
    대운/세운/일운 보정은 core/daewoon·core/sipsin 순수 함수로 요청 시점에 계산해
    점수 가감치(-40~+40)와 짧은 상태 코멘트를 얹는다(daily_db.json 3,600건은 불변).

    love_status/job_status(둘 다 선택, domains/daily/status_variants.py 참고)를 주면
    summary.love/summary.job_levelup 을 그 상태에 맞춘 문구로 채운다. 안 주거나 모르는
    값이면 기존 일반 텍스트(단/커플 병기, work_study)로 안전하게 폴백한다.
    """
    day_ganji = saju_data.get("day_ganji") or ""
    iljin_ganji = (saju_data.get("today_ganji") or {}).get("day") or ""

    entry = lookup(day_ganji, iljin_ganji)
    is_fallback = False
    if not entry:
        entry, is_fallback = _fallback(saju_data), True

    modifier = compute_woon_modifier(saju_data)
    adjusted = _apply_woon_modifier(entry, modifier)

    shaped = _shape(adjusted, saju_data, modifier)
    shaped["summary"]["social"] = paragraphize(
        build_social_summary(modifier["trigger_group"], modifier["trigger_bucket"])
    )
    shaped["woon_score_delta"] = modifier["score_delta"]
    shaped["sinsal_hits"] = [{"layer": h["layer"], "name": h["name"]} for h in modifier["sinsal_hits"]]
    # "Today Energy Movement" 섹션 전용 — 오늘 일진 지지가 이 사람 원국(용신/기신)에
    # 어떤 십신·관계인지를 반영한 한 줄(오늘/ilwoon 레이어만, headline과 다를 수 있음).
    shaped["today_energy"] = modifier["today_energy"]

    # 상태 분기(love_status/job_status) — 기존 love_single/love_couple/work_study 필드는
    # 그대로 두고, 상태에 맞춰 해석된 문구를 별도 필드로 추가한다(기존 클라이언트 호환 유지).
    love_status = love_status if love_status in LOVE_STATUSES else None
    job_status = job_status if job_status in JOB_STATUSES else None
    shaped["love_status"] = love_status
    shaped["job_status"] = job_status
    shaped["summary"]["love"] = paragraphize(
        _resolve_love_text(shaped["summary"], love_status, modifier["trigger_bucket"])
    )
    job_text = resolve_job_levelup(job_status, modifier["trigger_bucket"])
    shaped["summary"]["job_levelup"] = paragraphize(job_text or shaped["summary"]["work_study"])

    return shaped, is_fallback
