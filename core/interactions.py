"""지지 상호작용: 합·충·형·파·해·삼합·방합.

- check_ji_interactions(ji_list) -> List[str] : 레거시 문자열 목록 (회귀 테스트 호환)
- analyze_branch_relations(branches) -> Dict : 구조화 결과 (도메인 파생값/프롬프트용)
"""
from typing import List, Dict, Any
from collections import Counter
from itertools import combinations

from core.constants import (
    YUKHAP, CHUNG, PA, HAE, SANGHYEONG, SELF_HYEONG, SAMHYEONG,
    SAMHAP, BANGHAP,
)

# 레거시 라벨 순서를 유지하기 위한 정규 순서 쌍
_YUKHAP_PAIRS = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]
_CHUNG_PAIRS = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
_PA_PAIRS = [("子", "酉"), ("午", "卯"), ("申", "巳"), ("寅", "亥"), ("辰", "丑"), ("戌", "未")]
_HAE_PAIRS = [("子", "未"), ("丑", "午"), ("寅", "巳"), ("卯", "辰"), ("申", "亥"), ("酉", "戌")]
_HYEONG_PAIRS = [("子", "卯")]


def check_ji_interactions(ji_list: List[str]) -> List[str]:
    """레거시 포맷. 육합/충/자형 + 형/파/해/삼합/방합 라벨을 문자열로 반환."""
    out: List[str] = []
    present = [j for j in ji_list if j]
    pset = set(present)
    counts = Counter(present)

    # 자형
    for ji, c in counts.items():
        if c >= 2 and ji in SELF_HYEONG:
            out.append(f"자형({ji}-{ji})")

    for label, pairs in (
        ("육합", _YUKHAP_PAIRS), ("충", _CHUNG_PAIRS),
        ("파", _PA_PAIRS), ("해", _HAE_PAIRS), ("형", _HYEONG_PAIRS),
    ):
        for a, b in pairs:
            if a in pset and b in pset:
                out.append(f"{label}({a}-{b})")

    # 삼형 (2자 이상 성립 시 형으로 표기)
    for group, name in SAMHYEONG:
        hit = [g for g in group if g in pset]
        if len(hit) >= 2:
            out.append(f"형({'-'.join(hit)})")

    # 삼합 / 방합 (2자 반합 이상)
    for group, elem in SAMHAP.items():
        hit = [g for g in group if g in pset]
        if len(hit) == 3:
            out.append(f"삼합({'-'.join(group)}→{elem})")
        elif len(hit) == 2:
            out.append(f"반합({'-'.join(hit)}→{elem})")
    for group, elem in BANGHAP.items():
        hit = [g for g in group if g in pset]
        if len(hit) >= 2:
            out.append(f"방합({'-'.join(hit)}→{elem})")

    return out


def analyze_branch_relations(branches: Dict[str, str]) -> Dict[str, Any]:
    """branches: {"year":"亥","month":"巳","day":"寅","hour":"未"} (hour 없으면 생략/"").

    반환: 관계 유형별 목록 + 요약 카운트.
    """
    labeled = [(pos, ji) for pos, ji in branches.items() if ji]
    rel = {
        "육합": [], "충": [], "형": [], "파": [], "해": [],
        "삼합": [], "반합": [], "방합": [], "자형": [],
    }

    names = [p for p, _ in labeled]
    jis = [j for _, j in labeled]
    counts = Counter(jis)
    for ji, c in counts.items():
        if c >= 2 and ji in SELF_HYEONG:
            rel["자형"].append(ji)

    for (pa, ja), (pb, jb) in combinations(labeled, 2):
        key = frozenset((ja, jb))
        pair = f"{pa}-{pb}"
        if key in YUKHAP:
            rel["육합"].append({"pair": pair, "branches": f"{ja}{jb}", "name": YUKHAP[key]})
        if key in CHUNG:
            rel["충"].append({"pair": pair, "branches": f"{ja}{jb}", "name": CHUNG[key]})
        if key in PA:
            rel["파"].append({"pair": pair, "branches": f"{ja}{jb}", "name": PA[key]})
        if key in HAE:
            rel["해"].append({"pair": pair, "branches": f"{ja}{jb}", "name": HAE[key]})
        if key in SANGHYEONG:
            rel["형"].append({"pair": pair, "branches": f"{ja}{jb}", "name": SANGHYEONG[key]})

    pset = set(jis)
    for group, name in SAMHYEONG:
        hit = [g for g in group if g in pset]
        if len(hit) >= 2:
            rel["형"].append({"branches": "".join(hit), "name": name})
    for group, elem in SAMHAP.items():
        hit = [g for g in group if g in pset]
        if len(hit) == 3:
            rel["삼합"].append({"branches": "".join(group), "element": elem})
        elif len(hit) == 2:
            rel["반합"].append({"branches": "".join(hit), "element": elem})
    for group, elem in BANGHAP.items():
        hit = [g for g in group if g in pset]
        if len(hit) >= 2:
            rel["방합"].append({"branches": "".join(hit), "element": elem})

    summary = {k: len(v) for k, v in rel.items()}
    return {"relations": rel, "counts": summary}
