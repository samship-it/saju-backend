"""유료 여부는 서버 상품 목록으로만 가른다.

실제 결제 원장은 서버에 없다. 복콩 차감은 브라우저에만 있다.
그래서 프론트가 보낸 가격이나 paid 표시는 보지 않는다.
나중에 지갑을 서버로 옮기면 PurchaseCheck 구현만 바꾸면 된다.
무료 상품과 목록에 없는 응답은 그 구현이 뭐든 LLM을 호출하지 않는다.
"""
from typing import Any, Dict, Protocol

# 이 값이 False인 동안에는 영수증을 확인할 수 없다.
SERVER_HAS_PAYMENT_LEDGER = False

FREE_CONTENT_TYPES = frozenset({
    "daily_fortune",
    "daily_finance",
})

PAID_CONTENT_TYPES = frozenset({
    "나의 성격",
    "나의 적성",
    "궁합",
    "재회운",
    "짝사랑운",
    "결혼운",
    "ideal_partner",
    "lifelong_fortune",
    "daewoon_period",
})

YEARLY_MARKERS = (
    "총운",
    "재물운",
    "애정운",
    "사업운",
    "직장·이직운",
    "학업운",
    "건강운",
    "여행운",
    "취미운",
    "여행·취미",
)

YEARLY_CATEGORIES = frozenset({
    "overall",
    "wealth",
    "love",
    "business",
    "career_change",
    "study",
    "health",
    "travel",
    "hobby",
    "travel_hobby",
})


class PurchaseCheck(Protocol):
    """나중에 서버 영수증으로 바꿀 자리. 지금은 상품 목록만 본다."""

    def allows_llm(self, tier: str) -> bool:
        """tier 가 paid 일 때만 True 를 고려한다. free 는 호출부에서 이미 막는다."""


class ProductListPurchase:
    """결제 원장 없이, 서버에 적어 둔 유료 상품이면 LLM 대상이다."""

    def allows_llm(self, tier: str) -> bool:
        return tier == "paid"


def classify(data: Dict[str, Any]) -> str:
    """반환: free, paid, unknown. unknown 은 LLM 을 부르지 않는다."""
    content_type = str(data.get("content_type") or "")
    reading_type = str(data.get("reading_type") or "")
    category = str(data.get("category") or "")
    if content_type in FREE_CONTENT_TYPES:
        return "free"
    if content_type in PAID_CONTENT_TYPES or category in YEARLY_CATEGORIES:
        return "paid"
    if "년" in content_type and any(content_type.endswith(marker) for marker in YEARLY_MARKERS):
        return "paid"
    if "타로" in reading_type:
        return "paid"
    return "unknown"


def llm_permitted(tier: str, checker: PurchaseCheck) -> bool:
    """무료와 미분류는 설정과 무관하게 LLM 을 거부한다."""
    if tier != "paid":
        return False
    return bool(checker.allows_llm(tier))
