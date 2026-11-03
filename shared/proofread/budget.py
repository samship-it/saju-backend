"""월간 예산. 실제 입력·출력 토큰과 모델 단가로 계산한다.

한도에 닿으면 다음 LLM 호출만 막는다. 맞춤법 규칙과 운세 원문은 그대로 나간다.
가격은 Google 공식 문서(2026-10-30)의 gemini-3.5-flash-lite 유료 단가다.
단가표에 없는 모델은 호출하지 않는다.
"""
from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from shared.proofread import store
from shared.proofread.settings import max_output_tokens, monthly_budget_usd

_KST = ZoneInfo("Asia/Seoul")

# (입력 USD/100만 토큰, 출력 USD/100만 토큰)
MODEL_PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
}


def month_key(now: Optional[datetime] = None) -> str:
    moment = now or datetime.now(_KST)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_KST)
    else:
        moment = moment.astimezone(_KST)
    return moment.strftime("%Y-%m")


def price_of(model: str) -> Optional[Tuple[float, float]]:
    return MODEL_PRICES.get(model)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    price = price_of(model)
    if price is None:
        return None
    return round(
        (max(0, int(input_tokens)) / 1_000_000) * price[0]
        + (max(0, int(output_tokens)) / 1_000_000) * price[1],
        8,
    )


def estimate_cost(model: str, prompt: str) -> Optional[float]:
    """호출 전에 한도를 넘을지 보는 보수적 견적. 실제 청구는 응답 토큰으로 다시 더한다."""
    input_tokens = max(1, len(prompt))
    return cost_usd(model, input_tokens, max_output_tokens())


def spent(now: Optional[datetime] = None) -> float:
    return float(store.usage(month_key(now))["cost_usd"])


def can_spend(model: str, prompt: str, now: Optional[datetime] = None) -> bool:
    estimate = estimate_cost(model, prompt)
    if estimate is None:
        return False
    return spent(now) + estimate <= monthly_budget_usd()


def record(model: str, input_tokens: int, output_tokens: int, now: Optional[datetime] = None) -> float:
    amount = cost_usd(model, input_tokens, output_tokens)
    if amount is None:
        return 0.0
    store.add_usage(month_key(now), input_tokens, output_tokens, amount)
    return amount
