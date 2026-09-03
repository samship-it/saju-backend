"""주요 신살(神殺) 계산 — 표준 규칙 기준.

기준지(년지 또는 일지)의 삼합 그룹으로 도화/역마/화개를 판정하고,
일간 기준으로 홍염·양인, 간지 조합으로 백호를 판정한다.
용신/격국 수준의 논쟁적 신살은 제외한다.
"""
from typing import Dict, List, Any
from core.constants import (
    SAMHAP, DOHWA_BY_GROUP, YEOKMA_BY_GROUP, HWAGAE_BY_GROUP,
    HONGYEOM, YANGIN, BAEKHO,
)


def _samhap_group(branch: str) -> str:
    for group, elem in SAMHAP.items():
        if branch in group:
            return elem
    return ""


def analyze_sinsal(day_master: str, branches: Dict[str, str], pillars: Dict[str, str]) -> Dict[str, Any]:
    """branches: {pos: 지지}, pillars: {pos: 간지(2자)}.

    반환: 신살명 -> 걸린 위치 목록.
    """
    year_ji = branches.get("year", "")
    day_ji = branches.get("day", "")
    found: Dict[str, List[str]] = {}

    def add(name: str, pos: str):
        found.setdefault(name, [])
        if pos not in found[name]:
            found[name].append(pos)

    for base_ji in {year_ji, day_ji}:
        if not base_ji:
            continue
        grp = _samhap_group(base_ji)
        if not grp:
            continue
        dohwa = DOHWA_BY_GROUP.get(grp)
        yeokma = YEOKMA_BY_GROUP.get(grp)
        hwagae = HWAGAE_BY_GROUP.get(grp)
        for pos, ji in branches.items():
            if ji and ji == dohwa:
                add("도화", pos)
            if ji and ji == yeokma:
                add("역마", pos)
            if ji and ji == hwagae:
                add("화개", pos)

    hy = HONGYEOM.get(day_master)
    yi = YANGIN.get(day_master)
    for pos, ji in branches.items():
        if ji and ji == hy:
            add("홍염", pos)
        if ji and ji == yi:
            add("양인", pos)

    for pos, gz in pillars.items():
        if gz and gz in BAEKHO:
            add("백호", pos)

    return {
        "found": found,
        "names": sorted(found.keys()),
        "has_yeokma": "역마" in found,
        "has_dohwa": "도화" in found,
        "has_hwagae": "화개" in found,
        "has_hongyeom": "홍염" in found,
    }
