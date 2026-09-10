"""재회운 / 짝사랑운 / 결혼운 (RELATIONSHIP, 각 30P).

날짜 의존 로직(다가오는 3개월, 결혼 10년 강도 창, 커플 최적 연도)은 런타임 엔진이 계산한다.
AI 서술부(총운·3개월 전략·커플 총평)는 사전 생성 정적 DB
(`domains/relationship/data/relationship_db.json`)에서 일주 간지로 조회만 한다.
런타임 Gemini 호출 없음. DB 생성은 `scripts/generate_content_db.py --domain relationship` 참고.
조합이 DB 에 없으면(일주 계산 실패 등) 사주와 무관한 고정 폴백을 반환한다(is_fallback=True).

3개월 전략은 DB 에 "1/2/3개월차" 순번으로 저장돼 있고, 여기서 엔진이 계산한 실제 월 라벨에 매핑한다.
"""
import datetime
from typing import Dict, Any, Optional

from config import KST
from core.saju_base import calculate_saju
from core.timeframe import next_3_months, marriage_10year_window
from shared.public import person_summary
from shared.text_format import paragraphize
from domains.relationship import content_db

_LABEL = {"reunion": "재회운", "crush": "짝사랑운"}

# 재회운 '상대에게 어필할 나의 매력' 정적 DB 미스 시 사주 무관 고정 폴백.
_REUNION_CHARM_FALLBACK = (
    "당신의 가장 큰 매력은 상대의 말과 감정을 허투루 흘려듣지 않고 오래 기억해 주는 태도예요. "
    "옛 인연은 함께였을 때의 편안했던 대화와 자신이 존중받는다고 느꼈던 순간을 가장 그리워하기 쉽습니다. "
    "다시 마주쳤을 때는 서둘러 관계를 되돌리려 하기보다, 예전처럼 담담하고 진솔하게 안부를 건네는 모습이 "
    "상대의 마음을 자연스럽게 다시 흔듭니다. 연락의 온도를 상대에 맞춰 천천히 올리고, 예전보다 한결 "
    "단단해진 모습을 보여줄수록 신뢰가 쌓여요. 다만 잘 보이려는 마음이 앞서 과하게 맞춰주면 부담이 될 수 있으니 "
    "내 페이스를 지키는 선을 잊지 마세요."
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
def _love_fallback(kind: str, months, partner_exists: bool) -> dict:
    label = _LABEL[kind]
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


def _love_flow(kind: str, self_info, partner_info, target_date):
    """kind: 'reunion' | 'crush'. 날짜 의존부는 엔진, 서술부는 정적 DB 조회."""
    t_date = _parse_date(target_date)
    partner_exists = partner_info is not None
    s1 = _saju_of(self_info, t_date, partner_exists)
    s2 = _saju_of(partner_info, t_date, partner_exists) if partner_exists else None
    months = next_3_months(t_date)

    g1 = s1.get("day_ganji") or ""
    g2 = (s2.get("day_ganji") or "") if partner_exists else None
    entry = content_db.lookup(g1, g2, kind)
    is_fallback = entry is None
    data = _love_fallback(kind, months, partner_exists) if is_fallback else entry

    out = {
        "content_type": _LABEL[kind],
        "target_date": t_date.strftime("%Y-%m-%d"),
        "partner_exists": partner_exists,
        "combo_key": content_db.make_key(g1, g2, kind),
        "person1": _info(s1),
        "overall": paragraphize(str(data.get("overall", ""))),
    }
    if kind == "reunion":
        charm = content_db.charm_lookup(g1)
        out["your_charm"] = paragraphize(charm) if charm else _REUNION_CHARM_FALLBACK
    if partner_exists:
        out["person2"] = _info(s2)
        strat = content_db.strategy_list(entry) if entry is not None else []
        if len(strat) >= 3:
            # DB 는 "1/2/3개월차" 순번 → 엔진이 계산한 실제 월 라벨에 매핑
            out["strategy_3months"] = [
                {"month": months[i]["label"], "strategy": paragraphize(strat[i])}
                for i in range(3)
            ]
        else:
            out["strategy_3months"] = _love_fallback(kind, months, True)["strategy_3months"]
    return out, is_fallback


def analyze_reunion(self_info, partner_info=None, target_date=None):
    return _love_flow("reunion", self_info, partner_info, target_date)


def analyze_crush(self_info, partner_info=None, target_date=None):
    return _love_flow("crush", self_info, partner_info, target_date)


# ---------------------------------------------------------------- 결혼운
def _marriage_fallback(w1, w2, partner_exists: bool) -> dict:
    d = {
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
        d["couple_overall"] = (
            "두 사람 각자의 결혼 흐름과 관계 운을 함께 보면, 위에 표시된 해에 서로의 준비 상태와 "
            "관계의 안정감이 가장 잘 맞습니다. 그 시기를 목표로 구체적인 계획을 함께 세워보세요."
        )
    return d


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

    g1 = s1.get("day_ganji") or ""
    g2 = (s2.get("day_ganji") or "") if partner_exists else None
    entry = content_db.lookup(g1, g2, "marriage")
    is_fallback = entry is None
    data = _marriage_fallback(w1, w2, partner_exists) if is_fallback else entry

    # 점수는 AI 가 아니라 엔진의 10년 강도(BEST 1위)에서 결정 — 결정적(deterministic).
    score = w1["best"][0]["strength"] if w1["best"] else 60

    out = {
        "content_type": "결혼운",
        "target_year": ty,
        "window": w1["window"],
        "partner_exists": partner_exists,
        "combo_key": content_db.make_key(g1, g2, "marriage"),
        "person1": _info(s1),
        "overall_score": max(0, min(100, int(round(float(score))))),
        "best_period_label": w1["best_period_label"],
        "best_years": w1["best"],
        "year_strengths": w1["years"],
        "overall": paragraphize(str(data.get("overall", ""))),
    }
    if partner_exists:
        out["person2"] = _info(s2)
        out["partner_best_years"] = w2["best"]
        out["couple_best_year"] = _couple_best_year(w1, w2)
        couple_overall = data.get("couple_overall") or _marriage_fallback(w1, w2, True)["couple_overall"]
        out["couple_overall"] = paragraphize(str(couple_overall))
    return out, is_fallback


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
