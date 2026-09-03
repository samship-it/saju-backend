"""재회운 / 짝사랑운 / 결혼운 (RELATIONSHIP, 각 30P).

현재 날짜 기준으로 운을 계산. 상대방이 없으면 본인 원국만, 있으면 두 사람 원국 + 관계 운.
3개월 전략은 각 달마다 다른 '행동 전략'으로.
"""
import datetime
from typing import Dict, Any, Optional, Tuple

from config import KST
from core.saju_base import calculate_saju
from core.timeframe import next_3_months, marriage_10year_window
from shared.ai_client import call_gemini_json
from shared.persona_map import persona_prompt
from shared.saju_prompt import engine_block
from shared.fortune_cache import get_or_create
from shared.public import person_summary

_SYSTEM = (
    "당신은 2030 세대를 위한 연애운 화자입니다. 제공된 사주 데이터만 근거로 해석합니다. "
    "사주 용어 노출 금지. 유효한 JSON 만 출력합니다."
)


def _parse_date(s: Optional[str]) -> datetime.date:
    if s:
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    return datetime.datetime.now(KST).date()


def _saju_of(info: Dict[str, Any], t_date: datetime.date, partner_exists: bool):
    return calculate_saju(
        info["year"], info["month"], info["day"], info.get("hour"), info.get("minute", 0),
        gender=info.get("gender", "female"), is_lunar=info.get("is_lunar", False),
        target_date=t_date, partner_exists=partner_exists,
    )


_info = person_summary


# ---------------------------------------------------------------- 재회 / 짝사랑
def _love_flow(kind: str, self_info, partner_info, target_date):
    """kind: 'reunion' | 'crush'"""
    t_date = _parse_date(target_date)
    partner_exists = partner_info is not None
    s1 = _saju_of(self_info, t_date, partner_exists)
    s2 = _saju_of(partner_info, t_date, partner_exists) if partner_exists else None
    months = next_3_months(t_date)
    label = "재회운" if kind == "reunion" else "짝사랑운"

    def _fallback():
        base = {
            "overall": (
                f"지금은 {label}의 흐름이 크게 요동치기보다 천천히 방향을 잡아가는 시기입니다. "
                "과거의 인연이 다시 떠오르거나 연락이 스칠 가능성은 있지만, 그 신호에 즉시 반응하기보다 "
                "내 마음이 어떤 상태인지 먼저 정리하는 편이 유리합니다. 상대의 태도 변화를 관찰하되 "
                "먼저 크게 움직이지는 마세요. 새로운 인연과 비교했을 때, 지금의 감정이 미련인지 애정인지 "
                "구분하는 데 시간이 필요합니다. 연락 가능성이 조금씩 열리는 구간이 다가오니, 그때를 위해 "
                "지금은 나의 일상과 컨디션을 안정적으로 만들어 두는 게 최선입니다. 조급함만 내려놓으면 "
                "흐름은 당신에게 불리하지 않습니다."
            ),
        }
        if partner_exists:
            base["strategy_3months"] = [
                {"month": months[0]["label"], "strategy": "관찰 — 먼저 연락하기보다 상대의 신호와 주변 상황을 살피는 달"},
                {"month": months[1]["label"], "strategy": "접점 만들기 — 가벼운 안부나 공통 관심사로 자연스러운 접점을 만드는 달"},
                {"month": months[2]["label"], "strategy": "관계 확인 — 서로의 온도를 솔직하게 확인하고 다음 단계를 정하는 달"},
            ]
        return base

    def _gen():
        blocks = [persona_prompt(s1.get("day_master"), s1.get("day_branch")),
                  f"[운세 유형] {label}  |  기준일 {t_date}  |  상대방 존재: {partner_exists}",
                  "[본인]", engine_block(s1, domains=["love"])]
        if partner_exists:
            blocks += ["[상대방]", engine_block(s2, domains=["love"]),
                       f"[다음 3개월] {[m['label'] for m in months]}"]
        core_data = (
            "일지 + 배우자성 + 재성/관성 + 합충 + 대운/세운/월운/일운" if kind == "reunion"
            else "배우자성 + 일지 + 식상 + 관성/재성 + 도화 + 대운/세운/월운"
        )
        if partner_exists:
            schema = (
                '{\n  "overall": "총운 10~15줄. 두 사람의 원국 + 두 사람의 운 + 관계 운 종합",\n'
                '  "strategy_3months": [\n'
                '    {"month": "' + months[0]["label"] + '", "strategy": "이 달의 구체적 행동 전략"},\n'
                '    {"month": "' + months[1]["label"] + '", "strategy": "이전 달과 다른 행동 전략"},\n'
                '    {"month": "' + months[2]["label"] + '", "strategy": "또 다른 행동 전략"}\n  ]\n}'
            )
        else:
            schema = (
                '{\n  "overall": "총운 10~15줄. 과거 인연 재활성 여부 / 과거 정리 흐름 / 연락 가능성 높아지는 시기 / 새 인연과의 비교 포함"\n}'
            )
        prompt = "\n\n".join(blocks) + f"""

[핵심 데이터] {core_data}
[규칙] 총운은 반드시 10~15줄. 3개월 전략은 '좋음/보통'이 아니라 각 달마다 다른 행동 전략. 사주 용어 금지.

[출력 JSON — 이 구조만]
{schema}"""
        ai, is_fb = call_gemini_json(prompt, _fallback(), system_instruction=_SYSTEM)
        data = _fallback() if is_fb else ai
        out = {
            "content_type": label,
            "target_date": t_date.strftime("%Y-%m-%d"),
            "partner_exists": partner_exists,
            "person1": _info(s1),
            "overall": str(data.get("overall", "")),
        }
        if partner_exists:
            out["person2"] = _info(s2)
            strat = data.get("strategy_3months") or _fallback()["strategy_3months"]
            out["strategy_3months"] = [
                {"month": str(x.get("month", months[i]["label"])), "strategy": str(x.get("strategy", ""))}
                for i, x in enumerate(strat[:3])
            ]
        return out, is_fb

    payload = {
        "kind": kind, "date": t_date.strftime("%Y-%m-%d"),
        "self": {k: self_info.get(k) for k in ("year", "month", "day", "hour", "minute", "gender", "is_lunar")},
        "partner": None if not partner_exists else {k: partner_info.get(k) for k in ("year", "month", "day", "hour", "minute", "gender", "is_lunar")},
    }
    return get_or_create(f"relationship_{kind}", payload, _gen)[:2]


def analyze_reunion(self_info, partner_info=None, target_date=None):
    return _love_flow("reunion", self_info, partner_info, target_date)


def analyze_crush(self_info, partner_info=None, target_date=None):
    return _love_flow("crush", self_info, partner_info, target_date)


# ---------------------------------------------------------------- 결혼운
def analyze_marriage(self_info, partner_info=None, target_year: Optional[int] = None, target_date=None):
    t_date = _parse_date(target_date)
    ty = int(target_year) if target_year else t_date.year
    partner_exists = partner_info is not None
    s1 = _saju_of(self_info, t_date, partner_exists)
    w1 = marriage_10year_window(s1, ty)
    s2 = w2 = None
    if partner_exists:
        s2 = _saju_of(partner_info, t_date, partner_exists)
        w2 = marriage_10year_window(s2, ty)

    def _fallback():
        d = {
            "overall_score": w1["best"][0]["strength"] if w1["best"] else 60,
            "overall": (
                f"내부적으로 {w1['window'][0]}년부터 {w1['window'][1]}년까지의 결혼 관련 흐름을 살펴보면, "
                f"{w1['best_period_label']} 구간에서 인연을 매듭짓기 좋은 기운이 가장 뚜렷합니다. "
                "이 시기에는 관계를 확정하려는 마음과 주변 환경이 함께 맞아떨어지는 편이라, "
                "그전까지 관계의 기반을 단단히 다져두면 자연스럽게 결정으로 이어집니다. "
                "반대로 흐름이 약한 해에는 무리하게 서두르기보다 관계의 질을 쌓는 데 집중하세요. "
                "결혼은 타이밍만큼이나 준비가 중요하니, 좋은 시기에 맞춰 미리 대화를 시작해 두는 게 좋습니다."
            ),
        }
        if partner_exists:
            d["couple_best_year"] = _couple_best_year(w1, w2)
            d["couple_overall"] = (
                "두 사람 각자의 결혼 흐름과 관계 운을 함께 보면, 위에 표시된 해에 서로의 준비 상태와 "
                "관계의 안정감이 가장 잘 맞습니다. 그 시기를 목표로 구체적인 계획을 함께 세워보세요."
            )
        return d

    def _gen():
        blocks = [persona_prompt(s1.get("day_master"), s1.get("day_branch")),
                  f"[운세 유형] 결혼운 (결혼시기운)  |  기준연도 {ty}  |  상대방 존재: {partner_exists}",
                  "[본인]", engine_block(s1, domains=["love"]),
                  f"[본인 10년 결혼 강도] {w1['years']}",
                  f"[본인 BEST] {w1['best']}  →  화면 표기: 가장 좋은 시기 {w1['best_period_label']}"]
        if partner_exists:
            blocks += ["[상대방]", engine_block(s2, domains=["love"]),
                       f"[상대방 10년 결혼 강도] {w2['years']}",
                       f"[커플 최적 연도(엔진 계산)] {_couple_best_year(w1, w2)}"]
        if partner_exists:
            schema = (
                '{\n  "overall_score": <0-100 정수, 본인 BEST 강도와 방향 일치>,\n'
                '  "overall": "본인 결혼시기 총평 (왜 그 시기가 좋은지)",\n'
                '  "couple_best_year": <정수 연도>,\n'
                '  "couple_overall": "A 결혼운 + B 결혼운 + 두 사람 관계운이 왜 그 시기에 맞는지 설명"\n}'
            )
        else:
            schema = (
                '{\n  "overall_score": <0-100 정수, BEST 강도와 방향 일치>,\n'
                '  "overall": "화면에는 10년이 아니라 \'가장 좋은 시기\'만 보여준다. 왜 그 시기가 좋은지를 총운으로 설명 (7줄 이상)"\n}'
            )
        prompt = "\n\n".join(blocks) + f"""

[핵심 데이터] 배우자성 + 일지 + 대운 + 세운 + 합충 + 장기 변화
[규칙] 사주 용어 금지. overall_score 는 제공된 BEST 강도와 방향을 맞출 것.

[출력 JSON — 이 구조만]
{schema}"""
        ai, is_fb = call_gemini_json(prompt, _fallback(), system_instruction=_SYSTEM)
        data = _fallback() if is_fb else ai
        try:
            score = max(0, min(100, int(round(float(data.get("overall_score", 60))))))
        except Exception:
            score = 60
        out = {
            "content_type": "결혼운",
            "target_year": ty,
            "window": w1["window"],
            "partner_exists": partner_exists,
            "person1": _info(s1),
            "overall_score": score,
            "best_period_label": w1["best_period_label"],
            "best_years": w1["best"],
            "year_strengths": w1["years"],
            "overall": str(data.get("overall", "")),
        }
        if partner_exists:
            out["person2"] = _info(s2)
            out["partner_best_years"] = w2["best"]
            out["couple_best_year"] = int(data.get("couple_best_year") or _couple_best_year(w1, w2))
            out["couple_overall"] = str(data.get("couple_overall", ""))
        return out, is_fb

    payload = {
        "ty": ty,
        "self": {k: self_info.get(k) for k in ("year", "month", "day", "hour", "minute", "gender", "is_lunar")},
        "partner": None if not partner_exists else {k: partner_info.get(k) for k in ("year", "month", "day", "hour", "minute", "gender", "is_lunar")},
    }
    return get_or_create("relationship_marriage", payload, _gen)[:2]


def _couple_best_year(w1, w2) -> int:
    by_year = {}
    for r in w1["years"]:
        by_year[r["year"]] = r["strength"]
    best_y, best_v = w1["years"][0]["year"], -1
    for r in w2["years"]:
        combined = (by_year.get(r["year"], 50) + r["strength"]) / 2
        if combined > best_v:
            best_v, best_y = combined, r["year"]
    return best_y
