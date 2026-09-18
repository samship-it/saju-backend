"""10년 대운(DECADE_DAEWOON) — '이 10년의 풍경' 카드.

AI 호출·새 정적 DB 없음. domains/lifelong/landscape.py의 SUBJECT_IMAGE(일간이
상징하는 형상)를 그대로 재수출해 재사용하고, 배경(ENV)은 평생운세와 달리 원국
전체의 elem_power가 아니라 '이 10년 대운 간지의 천간 오행'으로 고른다 — 평생
전체가 아니라 이 10년만의 기운을 보여주는 것이 이 카드의 목적이기 때문.
"""
from typing import Any, Dict

from core.constants import GAN_ELEM
from domains.lifelong.landscape import ENV_IMAGE, SUBJECT_IMAGE

_DEFAULT_SUBJECT = "고요히 서 있는 존재"
_DEFAULT_ENV = "잔잔한 풍경"


def build_decade_landscape(day_master_elem: str, ganji: str) -> Dict[str, Any]:
    """day_master_elem(saju["day_master_elem"]) + 이 대운 단계의 간지 -> {scene, decade_elem}."""
    gan = ganji[0] if ganji else ""
    decade_elem = GAN_ELEM.get(gan, "")
    subject = SUBJECT_IMAGE.get(day_master_elem, _DEFAULT_SUBJECT)
    env = ENV_IMAGE.get(decade_elem, _DEFAULT_ENV)
    return {
        "scene": f"{env} 아래 {subject}",
        "decade_elem": decade_elem or None,
    }
