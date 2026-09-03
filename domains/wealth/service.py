"""오늘의 재테크 사주 (DAILY 재테크).

시장 데이터(KOSPI/NASDAQ/BTC)는 사주 엔진과 분리. AI가 시장 포인트와 개인 사주 흐름을 결합하되
'주가가 오른다/내린다' 예언은 절대 하지 않는다. 점수는 없다.
"""
from typing import Dict, Any, Tuple

from core.saju_base import calculate_saju
from domains.market.cron_market import get_market_snapshot
from shared.ai_client import call_gemini_json
from shared.persona_map import persona_prompt
from shared.saju_prompt import engine_block
from shared.public import person_summary

CONTENT_TYPE = "daily_finance"

_SYSTEM = (
    "당신은 2030 세대를 위한 재테크 운세 화자입니다. 시장 전망과 사주 해석을 섞어 "
    "'주가가 오른다/내린다'고 예언하지 않습니다. 제공된 사주 데이터와 시장 포인트만 근거로 사용하고, "
    "유효한 JSON 만 출력합니다."
)


def _fallback(market: Dict[str, Any]) -> dict:
    return {
        "market_point": market.get("market_point"),
        "investment_fortune": (
            "오늘은 시장을 크게 베팅하기보다 관찰이 유리한 흐름입니다. 관심 종목이나 자산이 다시 "
            "눈에 들어올 수 있지만, 지금은 진입 타이밍보다 나만의 원칙을 다시 적어보는 편이 낫습니다. "
            "분할로 접근할 여지가 있는지, 현금 비중은 충분한지부터 점검하세요. 변동성이 커지는 구간에서 "
            "감정적으로 따라붙는 매매만 피하면 손실 위험이 크게 줄어듭니다."
        ),
        "consumption_fortune": (
            "소비에서는 '기분 지출'에 주의가 필요한 날입니다. 스트레스를 쇼핑으로 푸는 패턴이 "
            "나오기 쉬우니, 장바구니에 담아두고 하루 지난 뒤 다시 보는 습관이 도움이 됩니다. "
            "구독료·자동결제처럼 무심코 나가는 고정지출을 한 건만 정리해도 이번 주가 한결 여유로워집니다."
        ),
        "money_flow": (
            "돈이 들어오는 흐름보다 나가는 흐름이 도드라지는 하루입니다. 예정에 없던 지출 요청이나 "
            "비용이 생길 수 있으니, 큰 결제는 하루 미루고 실제로 필요한지 한 번 더 확인하세요. "
            "작은 환급·정산 건이 있다면 오늘 챙겨두면 흐름이 조금 균형을 찾습니다."
        ),
        "caution_point": (
            "오늘 가장 조심할 행동은 '급등한 자산을 홧김에 추격 매수하는 것'입니다. 확신이 없는 자금 "
            "집행은 멈추고 관망하세요."
        ),
        "investment_behavior": {
            "tendency": "관망",
            "aggressiveness": "낮음",
            "chase_risk": "보통",
            "spending_tendency": "충동 소비 주의",
        },
    }


def _shape(ai: dict, market: Dict[str, Any]) -> dict:
    beh = ai.get("investment_behavior") or {}
    return {
        "market": {
            "indices": market.get("indices"),
            "is_live": market.get("is_live"),
        },
        "market_point": str(ai.get("market_point") or market.get("market_point") or ""),
        "investment_fortune": str(ai.get("investment_fortune", "")),
        "consumption_fortune": str(ai.get("consumption_fortune", "")),
        "money_flow": str(ai.get("money_flow", "")),
        "caution_point": str(ai.get("caution_point", "")),
        "investment_behavior": {
            "tendency": str(beh.get("tendency", "")),
            "aggressiveness": str(beh.get("aggressiveness", "")),
            "chase_risk": str(beh.get("chase_risk", "")),
            "spending_tendency": str(beh.get("spending_tendency", "")),
        },
    }


def analyze_daily_finance(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    target_date=None,
) -> Tuple[dict, bool]:
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar, target_date=target_date)
    market = get_market_snapshot(saju.get("target_date"))

    prompt = f"""{persona_prompt(saju.get('day_master'), saju.get('day_branch'))}

[오늘의 시장 포인트 후보 — 사주와 무관한 외부 데이터]
{market.get('market_point')}

{engine_block(saju, domains=['money', 'business'])}

[규칙]
- 시장 포인트와 개인 사주 흐름을 결합하되 주가 방향을 예언하지 말 것.
- 각 해석은 최소 5줄. 사주 용어 노출 금지.

[출력 JSON — 이 구조만 출력]
{{
  "market_point": "오늘 시장에서 가장 중요한 현상 하나 (1-2문장)",
  "investment_fortune": "시장 상황 + 개인 사주를 연결한 투자운 (5줄 이상). 편재/식상/비겁/변동성 관련 충·형 반영",
  "consumption_fortune": "소비 성향을 구체적 일상 상황으로 번역 (5줄 이상). 재성/비겁/일간/당일 금전 흐름 반영",
  "money_flow": "오늘 돈이 들어오고 나가는 흐름 설명 (5줄 이상). 재성/식상/비겁 관계 반영",
  "caution_point": "오늘 가장 조심해야 할 행동 하나 (명확하게 1-2문장)",
  "investment_behavior": {{
    "tendency": "적극성 / 관망 중 하나",
    "aggressiveness": "높음 / 보통 / 낮음",
    "chase_risk": "추격 매수 가능성: 높음 / 보통 / 낮음",
    "spending_tendency": "소비 성향 한 줄"
  }}
}}"""

    ai, is_fallback = call_gemini_json(prompt, _fallback(market), system_instruction=_SYSTEM)
    data = _shape(_fallback(market) if is_fallback else ai, market)
    return {
        "target_date": saju.get("target_date"),
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, is_fallback
