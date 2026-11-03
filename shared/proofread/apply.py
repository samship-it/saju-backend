"""응답 직전 검수.

맞춤법 규칙은 무료와 유료에 모두 적용한다.
LLM 은 서버 상품 목록의 유료 상품에만 적용한다.
시간 초과, API 오류, 예산 초과, 캐시 오류는 그 순간 원문으로 돌아간다.
"""
import logging
import threading
from typing import Any, Callable, Optional

from shared.proofread import budget, guard, llm, store
from shared.proofread.policy import ProductListPurchase, PurchaseCheck, classify, llm_permitted
from shared.proofread.settings import (
    enabled,
    llm_enabled,
    max_input_chars,
    max_output_tokens,
    model,
    timeout_sec,
)
from shared.proofread.spell import correct
from shared.prose_quality import _SKIP_KEYS

logger = logging.getLogger("proofread")

_SKIP = _SKIP_KEYS | frozenset({
    "saju_info", "person1", "person2", "best_years", "year_strengths",
    "partner_best_years", "sinsal_hits", "keywords", "card", "score_emoji",
    "score_band", "woon_score_delta", "overall_score", "money_score",
    "love_score", "work_study_score", "is_fallback", "birth_time_known",
    "strength", "rank", "reasons", "reasons_ko", "window",
})
_MIN_LLM_CHARS = 24

Complete = Callable[[str, str, Optional[int]], Optional[llm.LlmOutcome]]


def proofread_reading(
    data: Any,
    complete: Optional[Complete] = None,
    checker: Optional[PurchaseCheck] = None,
) -> Any:
    if not enabled() or not isinstance(data, dict):
        return data
    try:
        tier = classify(data)
        state = {"sent": 0, "checker": checker or ProductListPurchase(), "complete": complete}
        return _walk(data, "", tier, state)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[proofread] 검수 중단. 원문을 유지합니다: %s", type(exc).__name__)
        return data


def _walk(value: Any, key: str, tier: str, state: dict) -> Any:
    if key in _SKIP:
        return value
    if isinstance(value, str):
        return _one(value, tier, state)
    if isinstance(value, list):
        return [_walk(item, key, tier, state) for item in value]
    if isinstance(value, dict):
        return {name: _walk(item, name, tier, state) for name, item in value.items()}
    return value


def _one(text: str, tier: str, state: dict) -> str:
    corrected, _issues = correct(text)
    if not _should_call_llm(corrected, tier, state):
        return corrected
    chosen = model()
    cached = _cached(corrected, chosen)
    if cached is not None:
        return cached
    prompt = llm.SYSTEM + "\n" + corrected
    if not budget.can_spend(chosen, prompt):
        logger.info("[proofread] 월간 예산에 도달해 LLM 을 건너뜁니다.")
        return corrected
    if state["sent"] + len(corrected) > max_input_chars():
        logger.info("[proofread] 요청당 입력 한도에 도달해 LLM 을 건너뜁니다.")
        return corrected
    state["sent"] += len(corrected)
    outcome = _within_timeout(state["complete"] or llm.complete, corrected, chosen)
    if outcome is _TIMEOUT:
        _charge_timeout_estimate(chosen, prompt)
        return corrected
    if not isinstance(outcome, llm.LlmOutcome):
        return corrected
    input_tokens = outcome.input_tokens or max(1, len(prompt))
    output_tokens = outcome.output_tokens
    budget.record(chosen, input_tokens, output_tokens)
    revised = guard.apply_edits(corrected, outcome.edits)
    if not guard.same_facts(corrected, revised):
        return corrected
    try:
        store.put_cached(corrected, chosen, revised)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[proofread] 캐시 기록 실패: %s", type(exc).__name__)
    return revised


def _should_call_llm(text: str, tier: str, state: dict) -> bool:
    if not llm_enabled() or len(text) < _MIN_LLM_CHARS:
        return False
    if not llm_permitted(tier, state["checker"]):
        return False
    if budget.price_of(model()) is None:
        logger.warning("[proofread] 단가표에 없는 모델이라 LLM 을 건너뜁니다.")
        return False
    return True


def _cached(text: str, chosen: str) -> Optional[str]:
    try:
        return store.get_cached(text, chosen)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[proofread] 캐시 조회 실패. 원문 흐름으로 계속합니다: %s", type(exc).__name__)
        return None


_TIMEOUT = object()


def _within_timeout(complete: Complete, text: str, chosen: str):
    box: dict = {}

    def run() -> None:
        try:
            box["value"] = complete(text, chosen, None)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout_sec())
    if thread.is_alive():
        logger.warning("[proofread] 제한 시간 초과. 원문을 유지합니다.")
        return _TIMEOUT
    if "error" in box:
        logger.warning("[proofread] 검수 호출 오류. 원문을 유지합니다: %s", type(box["error"]).__name__)
        return None
    return box.get("value")


def _charge_timeout_estimate(chosen: str, prompt: str) -> None:
    """응답을 기다리다 끊긴 호출도 예산에 견적을 남겨 한도를 넘기지 않게 한다."""
    budget.record(chosen, max(1, len(prompt)), max_output_tokens())
