"""십신(十神) 계산.

회귀 테스트(tests/test_saju_core_regression.py)가 GAN_FIVE_ELEMENTS / JI_FIVE_ELEMENTS /
calculate_sipsin 를 직접 import 하므로 이름을 유지한다.
"""
from core.constants import (
    GAN_ELEM as GAN_FIVE_ELEMENTS,
    JI_ELEM as JI_FIVE_ELEMENTS,
    GAN_YANG,
    JI_YANG,
    FIVE_ELEMENT_RELATIONS,
)

GAN_YIN_YANG = GAN_YANG
JI_YIN_YANG = JI_YANG


def calculate_sipsin(day_master: str, target_char: str, is_gan: bool = True) -> str:
    dm_elem = GAN_FIVE_ELEMENTS.get(day_master, "목")
    dm_yy = GAN_YANG.get(day_master, True)
    target_elem = GAN_FIVE_ELEMENTS.get(target_char) if is_gan else JI_FIVE_ELEMENTS.get(target_char)
    target_yy = GAN_YANG.get(target_char) if is_gan else JI_YANG.get(target_char)

    if not target_elem:
        return "미정"

    group = FIVE_ELEMENT_RELATIONS.get((dm_elem, target_elem), "비겁")
    same_yy = (dm_yy == target_yy)
    mapping = {
        "비겁": ("비견" if same_yy else "겁재"),
        "식상": ("식신" if same_yy else "상관"),
        "재성": ("편재" if same_yy else "정재"),
        "관성": ("편관" if same_yy else "정관"),
        "인성": ("편인" if same_yy else "정인"),
    }
    return mapping[group]


def get_sipsin(day_master: str, target_char: str, is_gan: bool = True) -> str:
    """calculate_sipsin 의 호환용 별칭."""
    return calculate_sipsin(day_master, target_char, is_gan=is_gan)


def sipsin_group(sipsin: str) -> str:
    """개별 십신 -> 5분류 그룹."""
    return {
        "비견": "비겁", "겁재": "비겁",
        "식신": "식상", "상관": "식상",
        "편재": "재성", "정재": "재성",
        "편관": "관성", "정관": "관성",
        "편인": "인성", "정인": "인성",
    }.get(sipsin, "미정")
