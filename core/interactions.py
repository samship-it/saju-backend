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

    unique_jis = list(set(ji_list))
    for i in range(len(unique_jis)):
        for j in range(i + 1, len(unique_jis)):
            pair = (unique_jis[i], unique_jis[j])
            rev_pair = (unique_jis[j], unique_jis[i])
            if pair in hab_pairs or rev_pair in hab_pairs:
                interactions.append(f"육합({pair[0]}-{pair[1]})")
            if pair in chung_pairs or rev_pair in chung_pairs:
                interactions.append(f"충({pair[0]}-{pair[1]})")

    return interactions