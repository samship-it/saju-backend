"""12운성(十二運星) 계산.

일간의 장생 지지에서 시작하여 양간은 순행, 음간은 역행으로 12지지에 배속한다.
"""
from typing import Dict
from core.constants import JI, TWELVE_STAGES, CHANGSAENG_JI, YANG_GAN_FORWARD


def twelve_unseong(day_master: str, branch: str) -> str:
    start = CHANGSAENG_JI.get(day_master)
    if not start or branch not in JI:
        return "미정"
    start_idx = JI.index(start)
    forward = day_master in YANG_GAN_FORWARD
    target_idx = JI.index(branch)
    steps = (target_idx - start_idx) if forward else (start_idx - target_idx)
    return TWELVE_STAGES[steps % 12]


def twelve_unseong_map(day_master: str, branches: Dict[str, str]) -> Dict[str, str]:
    return {pos: twelve_unseong(day_master, ji) for pos, ji in branches.items() if ji}


# 왕/쇠 판정용 강한 단계
STRONG_STAGES = {"장생", "관대", "건록", "제왕"}
WEAK_STAGES = {"사", "묘", "절", "병", "쇠"}
