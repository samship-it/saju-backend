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
from core.constants import CHUNG
from core.timeframe import next_3_months, marriage_10year_window
from shared.public import person_summary
from shared.text_format import paragraphize
from domains.relationship import content_db

_LABEL = {"reunion": "재회운", "crush": "짝사랑운"}

# '상대에게 어필할 나의 매력' 정적 DB 미스 시 사주 무관 고정 폴백 (유형별).
_CHARM_FALLBACK = {
    "reunion": (
        "당신의 가장 큰 매력은 상대의 말과 감정을 허투루 흘려듣지 않고 오래 기억해 주는 태도예요. "
        "옛 인연은 함께였을 때의 편안했던 대화와 자신이 존중받는다고 느꼈던 순간을 가장 그리워하기 쉽습니다. "
        "다시 마주쳤을 때는 서둘러 관계를 되돌리려 하기보다, 예전처럼 담담하고 진솔하게 안부를 건네는 모습이 "
        "상대의 마음을 자연스럽게 다시 흔듭니다. 연락의 온도를 상대에 맞춰 천천히 올리고, 예전보다 한결 "
        "단단해진 모습을 보여줄수록 신뢰가 쌓여요. 다만 잘 보이려는 마음이 앞서 과하게 맞춰주면 부담이 될 수 있으니 "
        "내 페이스를 지키는 선을 잊지 마세요."
    ),
    "crush": (
        "당신의 가장 큰 매력은 상대의 이야기에 진심으로 귀 기울이고 그 사람의 결을 세심하게 살피는 태도예요. "
        "함께 있을 때 상대는 자신이 있는 그대로 존중받는다는 편안함을 느끼기 쉽습니다. "
        "다가갈 때는 마음을 한 번에 쏟기보다, 자연스러운 대화와 작은 관심을 꾸준히 건네며 천천히 거리를 좁혀 보세요. "
        "상대가 편하게 여기는 화제나 취향을 기억해 두었다가 가볍게 이어가면 호감이 깊어집니다. "
        "다만 상대의 반응을 확인하기 전에 마음을 앞세워 몰아붙이면 부담이 될 수 있으니, 상대의 속도를 존중하며 "
        "여유 있는 모습을 유지하는 것이 좋아요."
    ),
}


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
    if kind in ("reunion", "crush"):
        charm = content_db.charm_lookup(g1, kind)
        out["your_charm"] = paragraphize(charm) if charm else _CHARM_FALLBACK[kind]
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
# couple 추가 필드 정적 DB 미스 시 사주 무관 고정 폴백.
_MARRIAGE_CHECK_FALLBACK = [
    {"topic": "생활의 속도",
     "detail": "두 사람이 일상을 꾸리는 속도와 계획성이 다를 수 있어요. 집안일 분담, 약속 잡는 방식, "
               "쉬는 날을 보내는 리듬을 결혼 전에 구체적으로 맞춰두면 사소한 마찰이 크게 줄어듭니다."},
    {"topic": "경제권",
     "detail": "돈을 모으고 쓰는 기준이 다르면 오래 부딪히기 쉽습니다. 공동 통장 여부, 생활비 분담, "
               "큰 지출을 결정하는 방식을 미리 합의해두세요."},
    {"topic": "가치관",
     "detail": "일과 가정의 우선순위, 아이 계획, 양가 가족과의 거리 같은 큰 방향을 솔직하게 확인해야 해요. "
               "지금 생각이 달라도 괜찮으니, 서로의 기준을 알고 접점을 찾아두는 것이 중요합니다."},
]
_MARRIAGE_SCENARIO_FALLBACK = (
    "두 사람은 서로의 부족한 부분을 채워주며 안정적인 가정을 만들어갈 수 있는 조합입니다. "
    "처음에는 생활 방식의 차이로 조율이 필요하지만, 대화로 규칙을 정해가며 점차 편안한 리듬을 찾게 돼요. "
    "집은 두 사람의 취향이 자연스럽게 섞인 아늑한 공간이 되고, 주말에는 각자의 시간과 함께하는 시간을 균형 있게 나눕니다. "
    "돈과 일에 대해서는 큰 그림을 함께 그리며 서두르지 않고 한 걸음씩 목표를 이뤄가는 편이에요. "
    "시간이 지날수록 서로를 향한 신뢰가 단단해져, 힘든 시기에도 흔들리지 않는 든든한 동반자가 됩니다."
)


# solo 전용 추가 필드 정적 DB 미스 시 고정 폴백.
_MARRIAGE_SOLO_FALLBACK = {
    "marriage_timing": (
        "당신의 결혼운은 마음이 안정되고 스스로의 삶이 어느 정도 자리를 잡았다고 느낄 때 가장 크게 열립니다. "
        "무언가에 쫓기듯 서두르기보다, 지금의 관계나 나 자신에게 확신이 설 때 한 걸음 내딛는 편이 좋아요. "
        "인연은 예상치 못한 자리에서 자연스럽게 이어지는 경우가 많으니, 새로운 모임이나 관계에 마음을 열어두세요. "
        "반대로 일이나 관계가 크게 흔들리는 시기에는 큰 결정을 미루고 흐름이 잔잔해질 때를 기다리는 것이 현명합니다."
    ),
    "spouse_type": (
        "당신에게 잘 맞는 배우자는 당신이 놓치기 쉬운 부분을 차분하게 채워주는 사람이에요. "
        "감정 기복이 크지 않고 대화가 잘 통하며, 당신의 페이스를 존중해 주는 사람과 함께일 때 가장 편안합니다. "
        "책임감이 있으면서도 유연해서, 갈등이 생겨도 대화로 풀어가려는 태도를 가진 사람이 잘 맞아요. "
        "반대로 자기 방식만 고집하거나 감정 표현이 지나치게 격한 유형과는 부딪히기 쉬우니 초반에 잘 살펴보세요."
    ),
    "prep_strategy": (
        "좋은 인연을 결혼까지 이어가려면 먼저 나의 일상과 마음의 여유를 단단히 만들어두는 것이 중요해요. "
        "상대의 말을 끝까지 듣고 내 감정을 솔직하게 표현하는 연습을 해두면 관계가 훨씬 안정됩니다. "
        "경제적인 계획과 미래에 대한 생각을 어느 정도 정리해두면 상대에게 신뢰를 주기 쉬워요. "
        "새로운 만남의 기회를 피하지 말고, 나를 꾸미고 관리하는 데에도 꾸준히 신경 써보세요."
    ),
}

# 결혼운 10년 강도 reason 코드 → 사용자용 라벨.
_MARRIAGE_REASON_KO = {
    "배우자성 세운": "인연이 들어오는 기운이 강한 해",
    "일지 육합": "결혼 상대와 손발이 맞아떨어지는 해",
    "일지 삼합": "배우자 자리가 활발하게 움직이는 해",
    "일지 충": "관계에 변화·이동이 큰 해",
    "도화 세운": "매력이 빛나고 만남이 많아지는 해",
    "용신 세운": "전반적으로 나에게 유리한 흐름의 해",
}

# 점수·궁합 → '감성 한줄 총평' 헤드라인 (템플릿, 생성 없음).
_HEADLINE_COUPLE = [
    (88, "서로의 부족함을 완벽하게 메워주는, 천생연분 밸런스"),
    (78, "오래 함께할수록 단단해지는, 믿음직한 동반자"),
    (68, "다른 색깔이 만나 근사한 조화를 이루는 관계"),
    (58, "서로 맞춰가며 완성해가는, 성장하는 사랑"),
    (0, "정성을 들인 만큼 깊어지는, 노력이 필요한 인연"),
]
_HEADLINE_SOLO = [
    (85, "인연을 매듭짓기에 더없이 좋은, 결혼운이 무르익은 흐름"),
    (72, "준비된 만큼 이뤄지는, 좋은 인연이 가까이 오는 흐름"),
    (60, "기반을 다지면 결실로 이어지는, 안정적인 결혼운"),
    (48, "서두르기보다 관계의 질을 쌓아야 할 시기"),
    (0, "결혼보다 나의 삶을 단단히 만드는 데 집중할 때"),
]


def _marriage_headline(score: int, is_couple: bool, day_ji_chung: bool) -> str:
    table = _HEADLINE_COUPLE if is_couple else _HEADLINE_SOLO
    base = next(txt for lo, txt in table if score >= lo)
    if is_couple and day_ji_chung and score < 78:
        base += " (변화가 잦으니 솔직한 대화가 열쇠예요)"
    return base


def _reasons_ko(reasons) -> list:
    seen, out = set(), []
    for r in reasons or []:
        ko = _MARRIAGE_REASON_KO.get(r)
        if ko and ko not in seen:
            seen.add(ko)
            out.append(ko)
    return out


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
    score = max(0, min(100, int(round(float(score)))))

    # BEST 연도에 사용자용 사유 라벨을 붙인다.
    best_years = [{**b, "reasons_ko": _reasons_ko(b.get("reasons"))} for b in w1["best"]]
    best_year = _couple_best_year(w1, w2) if partner_exists else (
        best_years[0]["year"] if best_years else ty)

    day_ji_chung = bool(partner_exists and s2 and
                        frozenset((s1.get("day_branch"), s2.get("day_branch"))) in CHUNG)

    out = {
        "content_type": "결혼운",
        "target_year": ty,
        "window": w1["window"],
        "partner_exists": partner_exists,
        "combo_key": content_db.make_key(g1, g2, "marriage"),
        "person1": _info(s1),
        "overall_score": score,
        "headline": _marriage_headline(score, partner_exists, day_ji_chung),
        "best_year": best_year,
        "best_period_label": w1["best_period_label"],
        "best_years": best_years,
        "year_strengths": w1["years"],
        "overall": paragraphize(str(data.get("overall", ""))),
    }
    if partner_exists:
        out["person2"] = _info(s2)
        out["partner_best_years"] = w2["best"]
        out["couple_best_year"] = best_year
        couple_overall = data.get("couple_overall") or _marriage_fallback(w1, w2, True)["couple_overall"]
        out["couple_overall"] = paragraphize(str(couple_overall))

        # couple 전용 추가 필드(결혼 전 확인사항 · 미래 시나리오). 정적 DB 에 있으면 사용, 없으면 폴백.
        chk = data.get("pre_marriage_check") if isinstance(data, dict) else None
        if isinstance(chk, list) and chk:
            out["pre_marriage_check"] = [
                {"topic": str(x.get("topic", "")).strip(),
                 "detail": paragraphize(str(x.get("detail", "")))}
                for x in chk if isinstance(x, dict) and str(x.get("topic", "")).strip()
            ][:3] or _MARRIAGE_CHECK_FALLBACK
        else:
            out["pre_marriage_check"] = _MARRIAGE_CHECK_FALLBACK
        scenario = data.get("future_scenario") if isinstance(data, dict) else None
        out["future_scenario"] = (
            paragraphize(str(scenario)) if isinstance(scenario, str) and scenario.strip()
            else _MARRIAGE_SCENARIO_FALLBACK
        )
    else:
        # solo 전용 3필드: 정적 DB 에 있으면 사용, 없으면 폴백.
        for f in ("marriage_timing", "spouse_type", "prep_strategy"):
            v = data.get(f) if isinstance(data, dict) else None
            out[f] = (paragraphize(str(v)) if isinstance(v, str) and v.strip()
                      else _MARRIAGE_SOLO_FALLBACK[f])
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
