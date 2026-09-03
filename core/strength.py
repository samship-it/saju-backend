"""일간 강약 · 억부 용신/희신/기신 · 기본 격국 · 배우자성.

표준 명리 규칙 기준의 단순화 구현. 유파에 따라 세부 판정은 달라질 수 있으므로
결과에는 판정 근거(basis)를 함께 담는다.
"""
from typing import Dict, Any, List
from core.constants import (
    GAN_ELEM, JI_ELEM, JIJANGGAN, SHENG, KE, FIVE_ELEMENT_RELATIONS,
)
from core.sipsin import calculate_sipsin, sipsin_group


def _elem_relation_to_dm(dm_elem: str, other_elem: str) -> str:
    """일간오행 대비 other_elem 의 십신 그룹."""
    return FIVE_ELEMENT_RELATIONS.get((dm_elem, other_elem), "비겁")


def analyze_strength(day_master: str, pillars: Dict[str, str], birth_time_known: bool = True) -> Dict[str, Any]:
    """pillars: {"year":"癸亥","month":"丁巳","day":"壬寅","hour":"丁未" or ""}."""
    dm_elem = GAN_ELEM.get(day_master, "목")
    month_gz = pillars.get("month", "")
    month_ji = month_gz[1] if len(month_gz) > 1 else ""

    # 오행 세력 점수 (천간 1.0, 지장간 가중)
    elem_power = {"목": 0.0, "화": 0.0, "토": 0.0, "금": 0.0, "수": 0.0}
    for pos, gz in pillars.items():
        if not gz or len(gz) < 2:
            continue
        gan, ji = gz[0], gz[1]
        if gan in GAN_ELEM:
            elem_power[GAN_ELEM[gan]] += 1.0
        for hidden, w in JIJANGGAN.get(ji, []):
            elem_power[GAN_ELEM[hidden]] += w

    # 일간 편: 비겁(동일오행) + 인성(생해주는 오행)
    ally_elem = None
    for e in ("목", "화", "토", "금", "수"):
        if SHENG.get(e) == dm_elem:
            ally_elem = e  # 나를 생하는 오행 (인성)
    support = elem_power[dm_elem] + (elem_power.get(ally_elem, 0.0) if ally_elem else 0.0)
    total = sum(elem_power.values()) or 1.0
    oppose = total - support
    support_ratio = support / total

    # 득령: 월지가 비겁/인성
    deukryeong = False
    if month_ji:
        month_ji_elem = JI_ELEM.get(month_ji, "")
        grp = _elem_relation_to_dm(dm_elem, month_ji_elem)
        deukryeong = grp in ("비겁", "인성")

    if support_ratio >= 0.62 or (support_ratio >= 0.55 and deukryeong):
        verdict = "신강"
    elif support_ratio <= 0.38 or (support_ratio <= 0.45 and not deukryeong):
        verdict = "신약"
    else:
        verdict = "중화"

    # 억부 용신: 신강이면 관성/식상/재성 중 강한 것을 설기/억제, 신약이면 인성/비겁 보강
    def elem_for_group(group: str) -> str:
        for e in ("목", "화", "토", "금", "수"):
            if _elem_relation_to_dm(dm_elem, e) == group:
                return e
        return ""

    if verdict == "신강":
        yongsin_groups = ["관성", "식상", "재성"]
        gisin_groups = ["인성", "비겁"]
    elif verdict == "신약":
        yongsin_groups = ["인성", "비겁"]
        gisin_groups = ["재성", "관성", "식상"]
    else:  # 중화 — 통관/조후 성격, 가장 약한 세력 보강
        weakest = min(elem_power, key=elem_power.get)
        yongsin_groups = [_elem_relation_to_dm(dm_elem, weakest)]
        gisin_groups = []

    yongsin_elems = [elem_for_group(g) for g in yongsin_groups if elem_for_group(g)]
    gisin_elems = [elem_for_group(g) for g in gisin_groups if elem_for_group(g)]
    # 희신: 용신을 생하는 오행 (단, 기신/용신과 겹치면 제외)
    heesin_elems = []
    for ye in yongsin_elems:
        for e in ("목", "화", "토", "금", "수"):
            if SHENG.get(e) == ye and e not in heesin_elems and e not in gisin_elems and e not in yongsin_elems:
                heesin_elems.append(e)

    return {
        "day_master_elem": dm_elem,
        "verdict": verdict,
        "support_ratio": round(support_ratio, 3),
        "deukryeong": deukryeong,
        "elem_power": {k: round(v, 2) for k, v in elem_power.items()},
        "yongsin": yongsin_elems[:2],
        "heesin": heesin_elems[:2],
        "gisin": gisin_elems[:2],
        "basis": (
            f"support_ratio={round(support_ratio, 2)}, 득령={deukryeong} → {verdict}. "
            f"억부 기준 용신 {yongsin_groups}."
        ),
        "birth_time_known": birth_time_known,
    }


def analyze_gyeokguk(day_master: str, pillars: Dict[str, str]) -> Dict[str, Any]:
    """기본 격국: 월지 지장간 정기의 십신으로 판정 (내격 위주)."""
    month_gz = pillars.get("month", "")
    month_ji = month_gz[1] if len(month_gz) > 1 else ""
    if not month_ji:
        return {"name": "미정", "basis": "월지 없음"}
    hidden = JIJANGGAN.get(month_ji, [])
    if not hidden:
        return {"name": "미정", "basis": "지장간 없음"}
    main_hidden = hidden[0][0]
    sipsin = calculate_sipsin(day_master, main_hidden, is_gan=True)
    name_map = {
        "정관": "정관격", "편관": "편관격", "정재": "정재격", "편재": "편재격",
        "식신": "식신격", "상관": "상관격", "정인": "정인격", "편인": "편인격",
        "비견": "건록격", "겁재": "양인격",
    }
    return {
        "name": name_map.get(sipsin, f"{sipsin}격"),
        "month_branch_main_qi": main_hidden,
        "sipsin": sipsin,
        "basis": f"월지 {month_ji} 정기 {main_hidden} = {sipsin}",
    }


def spouse_star(day_master: str, gender: str, pillars: Dict[str, str], sipsin_map: Dict[str, str]) -> Dict[str, Any]:
    """배우자성: 남성=재성(정재 우선), 여성=관성(정관 우선). 배우자궁=일지."""
    is_female = str(gender).strip().lower() in {"female", "f", "여", "여자", "여성"}
    target_group = "관성" if is_female else "재성"
    primary = "정관" if is_female else "정재"
    secondary = "편관" if is_female else "편재"

    positions: List[str] = []
    for key, s in sipsin_map.items():
        if sipsin_group(s) == target_group:
            positions.append(key)

    day_gz = pillars.get("day", "")
    day_branch = day_gz[1] if len(day_gz) > 1 else ""
    return {
        "spouse_star_group": target_group,
        "primary_star": primary,
        "secondary_star": secondary,
        "found_positions": positions,
        "present": len(positions) > 0,
        "spouse_palace_branch": day_branch,
    }
