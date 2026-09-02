from typing import List
from collections import Counter

def check_ji_interactions(ji_list: List[str]) -> List[str]:
    interactions = []
    hab_pairs = [("子", "丑"), ("寅", "亥"), ("卯", "戌"), ("辰", "酉"), ("巳", "申"), ("午", "未")]
    chung_pairs = [("子", "午"), ("丑", "未"), ("寅", "申"), ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]

    counts = Counter(ji_list)
    for ji, count in counts.items():
        if count >= 2 and ji in ["辰", "午", "酉", "亥"]:
            interactions.append(f"자형({ji}-{ji})")

    # 라벨은 set 순회 순서가 아니라 참조 테이블의 정규 순서(canonical order)로 만든다.
    present = set(ji_list)
    for a, b in hab_pairs:
        if a in present and b in present:
            interactions.append(f"육합({a}-{b})")
    for a, b in chung_pairs:
        if a in present and b in present:
            interactions.append(f"충({a}-{b})")

    return interactions