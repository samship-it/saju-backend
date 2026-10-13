"""인연 가이드 서비스.

라우터 → 이 모듈(프로필 조회·복콩 차감) → 명리 코어(calculate_saju) → 정적 룰 조립.
요청 경로에서 LLM을 호출하지 않는다. 같은 출생 정보는 프로세스 안에서 한 번만 계산한다.
"""
import logging
from functools import lru_cache

from core.saju_base import calculate_saju
from domains.love.engine import build_ideal_partner
from domains.love.profiles import birth_of, deduct_bokkong, ideal_partner_cost

logger = logging.getLogger(__name__)

CONTENT_TYPE = "ideal_partner"


class ProfileMissing(Exception):
    """로그인 사용자 프로필이 없다."""


class InsufficientBokkong(Exception):
    def __init__(self, remaining: int):
        self.remaining = remaining


@lru_cache(maxsize=1024)
def _reading_cache(year: int, month: int, day: int, hour, minute: int, gender: str, is_lunar: bool):
    saju = calculate_saju(
        year, month, day, hour, minute,
        gender=gender, is_lunar=is_lunar,
    )
    data, is_fallback = build_ideal_partner(saju)
    # 캐시에 넣는 값은 불변 튜플. 호출마다 dict를 새로 만든다.
    return (
        data["user_diagnosis"],
        data["complement_element"]["element"],
        data["complement_element"]["label"],
        data["complement_element"]["support_element"],
        data["complement_element"]["support_label"],
        data["complement_element"]["text"],
        data["partner_personality"]["type"],
        data["partner_personality"]["text"],
        data["partner_synergy_tip"],
        bool(is_fallback),
    )


def _unpack(cached) -> tuple:
    (
        diagnosis, element, label, support, support_label, text,
        ptype, ptext, tip, is_fallback,
    ) = cached
    data = {
        "user_diagnosis": diagnosis,
        "complement_element": {
            "element": element,
            "label": label,
            "support_element": support,
            "support_label": support_label,
            "text": text,
        },
        "partner_personality": {"type": ptype, "text": ptext},
        "partner_synergy_tip": tip,
    }
    return data, is_fallback


def analyze_ideal_partner(user_id: str):
    """프로필 사주로 인연 가이드를 만들고, 성공 응답 직전에 복콩을 차감한다.

    반환: (data, is_fallback). data 에 remaining_bokkong, is_fallback 이 포함된다.
    """
    profile = birth_of(user_id)
    if profile is None:
        raise ProfileMissing()

    cost = ideal_partner_cost()
    cached = _reading_cache(
        int(profile["year"]), int(profile["month"]), int(profile["day"]),
        profile["hour"], int(profile["minute"] or 0),
        profile["gender"] or "female", bool(profile["is_lunar"]),
    )
    data, is_fallback = _unpack(cached)

    status, remaining = deduct_bokkong(user_id, cost)
    if status == "missing":
        raise ProfileMissing()
    if status == "insufficient":
        raise InsufficientBokkong(remaining if remaining is not None else 0)

    data["remaining_bokkong"] = remaining
    data["is_fallback"] = is_fallback
    return data, is_fallback
