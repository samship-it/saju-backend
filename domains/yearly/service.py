"""YEARLY_FORTUNE — 연도별 총운 + 8분야 (총 9개). target_year 는 동적(기본 올해).

특정 연도 하드코딩 금지. 2026→2027→2028 자동. 학업은 age/life_stage 로 분기.
"""
import datetime
from typing import Dict, Any, Optional, Tuple, List

from config import KST
from core.saju_base import calculate_saju, sipsin_of_ganji
from core.daewoon import get_wolwoon_list
from core.constants import GAN_ELEM, JI_ELEM, YUKHAP, CHUNG, SAMHAP
from core.sipsin import sipsin_group
from shared.ai_client import call_gemini_json
from shared.persona_map import persona_prompt
from shared.saju_prompt import engine_block, SCORING_RULES
from shared.fortune_cache import get_or_create
from shared.public import person_summary
from shared.text_format import paragraphize

CATEGORIES = {
    "overall": "총운",
    "wealth": "재물운",
    "love": "애정운",
    "business": "사업운",
    "career_change": "직장·이직운",
    "study": "학업운",
    "health": "건강운",
    "travel": "여행운",
    "hobby": "취미운",
}

_SYSTEM = (
    "당신은 2030 세대를 위한 사주 앱 화자입니다. 제공된 사주/운 데이터만 근거로 한 해를 하나의 스토리처럼 풀어냅니다. "
    "사주 용어 노출 금지. 유효한 JSON 만 출력합니다."
)


def _monthly_strength(saju: Dict[str, Any], target_year: int) -> List[Dict[str, Any]]:
    dm = saju.get("day_master", "")
    day_branch = saju.get("day_branch", "")
    yongsin = set((saju.get("strength") or {}).get("yongsin") or [])
    rows = []
    for w in get_wolwoon_list(target_year):
        gz = w["ganji"]
        gan, ji = gz[0], gz[1]
        score = 50.0
        s_gan = sipsin_group(sipsin_of_ganji(dm, gz).get("gan", ""))
        s_ji = sipsin_group(sipsin_of_ganji(dm, gz).get("ji", ""))
        for grp in (s_gan, s_ji):
            if grp in ("재성", "인성"):
                score += 6
            elif grp in ("식상",):
                score += 4
            elif grp in ("관성",):
                score += 2
            elif grp in ("비겁",):
                score += 1
        key = frozenset((day_branch, ji))
        if key in YUKHAP:
            score += 8
        elif any(day_branch in g and ji in g for g in SAMHAP):
            score += 6
        elif key in CHUNG:
            score -= 10
        if GAN_ELEM.get(gan) in yongsin or JI_ELEM.get(ji) in yongsin:
            score += 8
        rows.append({
            "month_index": w["month_index"],
            "solar_month_approx": w["solar_month_approx"],
            "ganji": gz,
            "strength": max(0, min(100, round(score))),
        })
    return rows


def _best_caution(monthly: List[Dict[str, Any]]):
    ranked = sorted(monthly, key=lambda r: r["strength"], reverse=True)
    best = [f"{r['solar_month_approx']}월" for r in ranked[:3]]
    caution = [f"{r['solar_month_approx']}월" for r in ranked[-3:]]
    return best, caution


_CORE_DATA = {
    "overall": "원국 + 대운 + 해당 세운 + 12개월 월운 강도",
    "wealth": "정재/편재 + 식상 + 비겁 + 일간 강약 + 재성 합충",
    "love": "세운 + 일지 + 배우자성 + 관성/재성 + 합충 + 도화/홍염",
    "business": "식상 + 재성 + 비겁 + 관성",
    "career_change": "관성 + 인성 + 식상 + 일간 강약 + 대운/세운",
    "study": "관성 + 인성 + 식상 + 일간 강약 + 대운/세운",
    "health": "해당 연도의 생활관리 관련 작용",
    "travel": "식상 + 역마 + 충 + 이동",
    "hobby": "오행 + 십신 + 역마 + 해당 연도 활성 요소",
}


def _fallback(category: str, year: int, saju: Dict[str, Any], monthly, best, caution) -> dict:
    yy = str(year)[2:]
    d = {
        "analysis": (
            f"{year}년은 급격한 도약보다 방향을 다시 잡고 기반을 다지는 흐름이 강합니다. "
            "상반기에는 벌여둔 일을 정리하고, 하반기로 갈수록 새로운 시도에 힘이 붙습니다. "
            "무리한 확장보다 이미 가진 것을 단단하게 만드는 선택이 유리하고, 사람 관계에서는 "
            "먼저 듣는 태도가 기회를 열어줍니다. 조급함만 내려놓으면 한 해의 방향은 나쁘지 않습니다. "
            "올해의 성취는 속도가 아니라 꾸준함에서 나옵니다."
        ),
    }
    if category == "overall":
        d.update({
            "one_line": f"{year}년, 멈춰 있던 일을 다시 움직이기 좋은 해",
            "keywords": ["방향 재정비", "기반 다지기", "꾸준함"],
            "best_months": best,
            "caution_months": caution,
        })
    if category == "travel":
        d["recommendation"] = {
            "domestic": "가까운 바다·강 주변으로 짧게 다녀오기 좋습니다.",
            "overseas": "장거리 여행은 하반기가 유리합니다.",
            "timing": ", ".join(best) + " 무렵",
            "style": "새로운 장소에서 몸을 움직이는 액티브한 여행",
            "reason": "움직일수록 흐름이 열리는 해라, 정체된 기분을 이동으로 환기하면 도움이 됩니다.",
        }
    if category == "hobby":
        d["recommendation"] = ["수영·다이빙 등 물과 움직임이 있는 활동", "새로운 장소를 경험하는 취미", "손을 쓰는 창작 활동"]
    d["content_type"] = f"{yy}년 {CATEGORIES[category]}"
    return d


def generate_yearly(
    category: str,
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    target_year: Optional[int] = None,
) -> Tuple[dict, bool]:
    if category not in CATEGORIES:
        raise ValueError(f"unknown category: {category}")

    ty = int(target_year) if target_year else datetime.datetime.now(KST).date().year
    t_date = datetime.date(ty, 1, 1)
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar, target_date=t_date)
    monthly = _monthly_strength(saju, ty)
    best, caution = _best_caution(monthly)
    yy = str(ty)[2:]

    def _gen():
        extra_schema = ""
        if category == "overall":
            extra_schema = (
                '  "one_line": "올해 한줄 (짧고 센스 있게)",\n'
                '  "keywords": ["총운에서 추출한 핵심 키워드 3개", "", ""],\n'
                '  "best_months": ' + str(best) + ',\n'
                '  "caution_months": ' + str(caution) + ',\n'
            )
        elif category == "travel":
            extra_schema = (
                '  "recommendation": {"domestic": "국내 추천", "overseas": "해외 추천", "timing": "시기", "style": "여행 스타일", "reason": "이유"},\n'
            )
        elif category == "hobby":
            extra_schema = '  "recommendation": ["올해 활성화되는 취미 1", "2", "3"],\n'

        study_note = ""
        if category == "study":
            study_note = f"\n[생애단계] 만 {saju.get('age')}세 / {saju.get('life_stage')} — 이 단계에 맞는 현실적인 도전과 조언으로 번역할 것."

        prompt = f"""{persona_prompt(saju.get('day_master'), saju.get('day_branch'))}

[운세 유형] {ty}년 {CATEGORIES[category]}
[핵심 데이터] {_CORE_DATA[category]}
[12개월 월운 강도] {monthly}
[BEST 달] {best}  [주의 달] {caution}{study_note}

{engine_block(saju, domains=[category if category in ('wealth','love','business','career_change','study','health','travel','hobby') else 'overall'])}

{SCORING_RULES if category == 'overall' else ''}
[작성 규칙]
- analysis 는 아래 4개 흐름을 순서대로 담되, 각 흐름을 하나의 문단으로 쓰고 문단 사이를 실제 줄바꿈 두 번으로 구분한다.
  ① 올해 전체 흐름과 분위기
  ② 상반기(1~6월) 구체적 흐름
  ③ 하반기(7~12월) 구체적 흐름
  ④ 이 분야에서 올해 꼭 기억할 조언
- BEST 달·주의 달을 문장 안에서 자연스럽게 언급하고, 왜 그 시기인지 한 줄씩 근거를 준다.
- 추상적 격언 대신 2030 세대가 실제로 겪는 상황(이직, 이사, 소개팅, 대출, 시험 등)으로 예를 든다.
- 사주 용어 금지. 전체 12줄 이상.

[출력 JSON — 이 구조만]
{{
{extra_schema}  "analysis": "{CATEGORIES[category]} 상세 분석 (위 작성 규칙의 문단 구성을 지킬 것. 총운은 가장 길고 깊게)"
}}"""
        ai, is_fb = call_gemini_json(
            prompt, _fallback(category, ty, saju, monthly, best, caution), system_instruction=_SYSTEM,
        )
        data = _fallback(category, ty, saju, monthly, best, caution) if is_fb else ai

        out = {
            "content_type": f"{yy}년 {CATEGORIES[category]}",
            "category": category,
            "target_year": ty,
            "day_master": saju.get("day_master"),
            "birth_time_known": saju.get("birth_time_known"),
            "saju_info": person_summary(saju),
            "analysis": paragraphize(str(data.get("analysis", ""))),
        }
        if category == "overall":
            kws = [str(k) for k in (data.get("keywords") or [])][:3]
            while len(kws) < 3:
                kws.append("")
            out.update({
                "one_line": str(data.get("one_line", "")),
                "keywords": kws,
                "monthly": monthly,
                "best_months": data.get("best_months") or best,
                "caution_months": data.get("caution_months") or caution,
            })
        if category == "study":
            out["life_stage"] = saju.get("life_stage")
            out["age"] = saju.get("age")
        if category in ("travel", "hobby"):
            out["recommendation"] = data.get("recommendation")
        return out, is_fb

    payload = {
        "cat": category, "ty": ty,
        "birth": {"y": year, "m": month, "d": day, "h": hour, "min": minute, "g": gender, "lunar": is_lunar},
    }
    data, is_fb, _ = get_or_create(f"yearly_{category}", payload, _gen)
    return data, is_fb
