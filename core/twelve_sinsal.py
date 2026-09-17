"""십이신살(十二神殺) 계산 — 기준지(현대 표준: 일지)의 삼합 오행국으로 12지지 각각에
겁살~화개살 이름을 순서대로 배정한다.

근거(2026-09 웹 검색으로 확인한 표준 암기법): "삼합오행의 마지막 글자(墓地)의 다음
지지가 겁살로 시작해 겁재천지·연월망장·반역육화 순서로 이어진다." 예) 申子辰(水局)의
묘지=辰 -> 겁살=巳(辰 다음 지지) -> 재살=午 -> 천살=未 -> ... -> 화개살=辰.

현대에는 년지 대신 일지를 기준으로 보는 것이 대세이므로 이 모듈은 day_branch 를
기준지로 받는다(호출부에서 필요시 year_branch 도 넘길 수 있음).
"""
from typing import Dict, Optional

JI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

_SAMHAP_GROUPS = (("申", "子", "辰"), ("亥", "卯", "未"), ("寅", "午", "戌"), ("巳", "酉", "丑"))

SINSAL_ORDER = [
    "겁살", "재살", "천살", "지살", "년살", "월살",
    "망신살", "장성살", "반안살", "역마살", "육해살", "화개살",
]

# 전통적으로 흉살로 분류되는 4종(사용자 요청 범위) — 그 외(지살/년살/장성살/반안살/
# 역마살/화개살)는 길흉이 섞이거나 중립~길에 가까운 성격이라 경고 대상에서 제외.
WARNING_SINSAL = {"겁살", "재살", "천살", "망신살"}


def _samhap_group(branch: str) -> Optional[tuple]:
    for group in _SAMHAP_GROUPS:
        if branch in group:
            return group
    return None


def twelve_sinsal(base_branch: str, target_branch: str) -> str:
    """base_branch(기준지, 보통 일지) 대비 target_branch 가 어떤 신살에 해당하는지."""
    group = _samhap_group(base_branch)
    if not group or not target_branch:
        return ""
    myo = group[2]  # 묘지(고지) — 삼합 그룹의 마지막 지지
    geobsal_branch = JI[(JI.index(myo) + 1) % 12]
    offset = (JI.index(target_branch) - JI.index(geobsal_branch)) % 12
    return SINSAL_ORDER[offset]


def sinsal_check(base_branch: str, target_branch: str) -> Dict[str, object]:
    name = twelve_sinsal(base_branch, target_branch)
    return {"name": name, "is_warning": name in WARNING_SINSAL}
