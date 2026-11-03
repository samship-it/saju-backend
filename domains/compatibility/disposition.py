"""연애 이외 궁합의 상단 한줄.

점수는 만들지 않는다. 본문 문장은 일주 해설을 관계에 맞게 다듬어 쓰고,
여기서는 성향 궁합 한줄과 관계 이름만 고른다.
"""
from typing import Any, Dict

from core.constants import COMPAT_BANDS

_ROMANTIC = {"romantic", "spouse"}

_PLACE = {
    "friend": "친구 사이에서는",
    "family": "가족 사이에서는",
    "business": "사업에서는",
    "coworker": "직장에서는",
    "acquaintance": "지인 사이에서는",
}
_EXAMPLES = {
    "friend": {
        "mesh": "예를 들면 약속을 잡을 때 역할이 빨리 나뉩니다.",
        "clash": "예를 들면 만나는 방식이나 연락 속도에서 서운함이 반복됩니다.",
        "crack": "예를 들면 농담의 수위가 서로 다르게 느껴집니다.",
        "fill": "예를 들면 한 사람은 계획을 잡고, 다른 사람은 자리를 이끕니다.",
        "next": "서운한 점은 그 자리에서 짧게 말하고, 다음 약속의 방식을 바꿉니다.",
    },
    "family": {
        "mesh": "예를 들면 집안 행사를 준비할 때 손이 맞습니다.",
        "clash": "예를 들면 생활 습관을 두고 같은 말이 반복됩니다.",
        "crack": "예를 들면 식사나 살림 순서가 자꾸 어긋납니다.",
        "fill": "예를 들면 한 사람이 빠뜨린 살림을 다른 사람이 채웁니다.",
        "next": "집안일에서는 기대하는 역할을 먼저 나누고, 같은 지적을 반복하지 않습니다.",
    },
    "business": {
        "mesh": "예를 들면 제안과 실행이 한 흐름으로 붙습니다.",
        "clash": "예를 들면 가격이나 일정에서 결론이 갈립니다.",
        "crack": "예를 들면 맡은 범위가 겹치면서 책임이 흐려집니다.",
        "fill": "예를 들면 한 사람에게 없는 실무를 다른 사람이 맡습니다.",
        "next": "결정 전에 역할과 마감 기준을 적고, 같은 안건을 두 번 뒤집지 않습니다.",
    },
    "coworker": {
        "mesh": "예를 들면 회의에서 의견이 하나로 모이기 쉽습니다.",
        "clash": "예를 들면 보고 방식과 마감 기준이 갈립니다.",
        "crack": "예를 들면 일을 넘길 때 세부 사항이 빠집니다.",
        "fill": "예를 들면 문서와 실행처럼 비어 있는 일을 나눠 갖습니다.",
        "next": "담당과 확인 순서를 적어 두고, 같은 수정을 말로만 반복하지 않습니다.",
    },
}


def is_romantic(relation_type: str) -> bool:
    return (relation_type or "romantic").strip().lower() in _ROMANTIC


def normalize_relation(relation_type: str) -> str:
    key = (relation_type or "romantic").strip().lower()
    if key in _ROMANTIC:
        return "romantic"
    return key if key in _PLACE else "general"


def _band(score: int) -> str:
    s = max(0, min(100, int(score)))
    for lo, hi, *_rest in COMPAT_BANDS:
        if lo <= s <= hi:
            return f"{lo}-{hi}"
    return "0-29"


# COMPAT_BANDS와 같은 순서(90-100 … 0-29). 구간 경계는 그 표를 그대로 쓴다.
_ONE_LINERS = {
    "friend": (
        "이런 친구, 평생 옆에 둬야지! 🤝",
        "말하지 않아도 통하는 사이.",
        "우리 은근히 잘 맞는 조합인데?",
        "조금씩 알아가면 더 좋겠어.",
        "다름을 인정하면 괜찮아질 사이.",
        "친해지려면 서로 노력이 필요해.",
        "우리는 꽤 다른 타입이네.",
        "친하다는 이유만으로 다 맞을 순 없지.",
    ),
    "family": (
        "역시 가족은 가족이네! 🏡",
        "서로 달라도 결국 든든한 내 편.",
        "우리 가족, 생각보다 합이 좋은데?",
        "조금만 더 이해하면 편해질 사이.",
        "가족이어도 서로의 방식은 존중해야 해.",
        "가까운 만큼 서로 배려가 필요해.",
        "가족이지만 생각은 꽤 다르네.",
        "가족이라는 이유로 모든 걸 맞출 필요는 없어.",
    ),
    "business": (
        "이 조합이면 판을 키울 수 있겠는데? 🚀",
        "서로의 강점이 확실한 팀.",
        "역할만 잘 나누면 꽤 괜찮은 조합.",
        "합의와 조율이 성과를 좌우하겠어.",
        "시작 전에 역할과 책임부터 맞춰보자.",
        "일하는 방식부터 조율해야겠어.",
        "목표가 같아도 접근법은 다르네.",
        "의욕만으로 함께 사업하기는 어려워.",
    ),
    "coworker": (
        "같이 일하면 시너지가 제대로 나겠어! 💪",
        "서로의 빈틈을 채워주는 좋은 조합.",
        "호흡만 맞추면 일하기 편하겠는데?",
        "소통 방식을 맞추면 더 수월해질 사이.",
        "업무 기준부터 맞춰보는 게 좋겠어.",
        "서로의 업무 스타일을 이해해야겠어.",
        "일하는 방식이 꽤 다르네.",
        "친해지는 것보다 업무 경계를 명확히 하는 게 먼저야.",
    ),
    "acquaintance": (
        "처음부터 왠지 통하는 사람! ✨",
        "알아갈수록 괜찮은 인연이네.",
        "생각보다 대화가 잘 통하는 사이.",
        "천천히 알아가면 좋을 것 같아.",
        "아직은 서로 알아가는 중.",
        "조금 더 거리를 두고 알아가 보자.",
        "서로의 결이 꽤 다른 편이네.",
        "모든 사람과 가까워질 필요는 없으니까.",
    ),
}

if any(len(lines) != len(COMPAT_BANDS) for lines in _ONE_LINERS.values()):
    raise RuntimeError("compatibility one-liner count does not match COMPAT_BANDS")


def _general_one_liner(score: int) -> str:
    """화면의 일곱 관계가 아닌 코드만 쓰는 기존 네 구간."""
    if score >= 80:
        tail = "성향이 잘 맞물립니다."
    elif score >= 60:
        tail = "차이를 조율하며 갈 수 있습니다."
    elif score >= 40:
        tail = "다른 방식이 먼저 드러납니다."
    else:
        tail = "성향 차이가 크게 드러납니다."
    return f"이 관계에서는 {tail}"


def one_liner(score: int, relation_type: str) -> str:
    key = normalize_relation(relation_type)
    s = max(0, min(100, int(score)))
    lines = _ONE_LINERS.get(key)
    if not lines:
        return _general_one_liner(s)
    for (lo, hi, *_rest), text in zip(COMPAT_BANDS, lines):
        if lo <= s <= hi:
            return text
    return lines[-1]


def _temperament(interactions: Dict[str, Any], place: str) -> str:
    relation = interactions.get("day_master_relation") or ""
    if interactions.get("day_master_hap"):
        return f"{place} 기질이 쉽게 붙습니다. 금세 한 편이 되지만, 역할 경계가 흐려질 수 있습니다."
    if interactions.get("day_master_chung"):
        return f"{place} 기질이 정면으로 부딪힙니다. 같은 일을 두고 방향이 갈리기 쉽습니다."
    if relation == "상생":
        return f"{place} 한쪽 기질이 다른 쪽을 받칩니다. 지친 쪽의 빈자리를 다른 쪽이 이어 가기 쉽습니다."
    if relation == "비화(같은 기운)":
        return f"{place} 기질이 비슷합니다. 속도는 맞지만, 같은 고집이 겹칠 수 있습니다."
    if relation == "상극":
        return f"{place} 일하는 방식이 다릅니다. 속도나 우선순위가 어긋나 보일 수 있습니다."
    return f"{place} 기질은 특별히 붙지도 밀치지도 않습니다."


def _rhythm(day_ji: str, place: str) -> str:
    if day_ji in ("육합", "삼합"):
        return f"{place} 생활 리듬이 맞물립니다."
    if day_ji in ("충", "형"):
        return f"{place} 가까이 붙어 지낼수록 생활 리듬이 부딪힙니다."
    if day_ji in ("해", "파"):
        return f"{place} 생활 리듬에 작은 어긋남이 반복되기 쉽습니다."
    if day_ji == "동일":
        return f"{place} 생활 리듬이 비슷합니다."
    return f"{place} 생활 리듬이 특별히 붙거나 부딪히지 않습니다."


def build_report(interactions: Dict[str, Any], relation_type: str) -> Dict[str, str]:
    key = normalize_relation(relation_type)
    place = _PLACE.get(key, "이 관계에서는")
    example = _EXAMPLES.get(key, _EXAMPLES["friend"])
    basis = interactions.get("overall_basis") or {}
    mesh = (basis.get("천간합") or 0) + (basis.get("지지육합") or 0) + (basis.get("지지삼합") or 0)
    clash = (basis.get("천간충") or 0) + (basis.get("지지충") or 0) + (basis.get("지지형") or 0)
    crack = (basis.get("지지파") or 0) + (basis.get("지지해") or 0)
    fill = basis.get("오행보완") or 0

    parts = [
        _temperament(interactions, place),
        _rhythm(str(interactions.get("day_ji_relation") or ""), place),
    ]
    if mesh:
        parts.append(f"맞물리는 조합이 있습니다. {example['mesh']}")
    if clash:
        parts.append(f"부딪히는 조합이 있습니다. {example['clash']}")
    if crack:
        parts.append(f"작게 어긋나는 조합이 있습니다. {example['crack']}")
    if fill:
        parts.append(f"한쪽에 없는 기운을 상대가 채웁니다. {example['fill']}")
    if not (mesh or clash or crack or fill):
        parts.append(f"{place} 두드러지는 합이나 충은 적습니다.")

    communication = (
        f"{place} 말의 결은 기질 차이를 따라갑니다. "
        + (example["mesh"] if mesh else example["next"])
    )
    if clash or crack:
        conflict = f"{place} 같은 자리를 두고 방식 차이가 드러납니다. {example['clash'] if clash else example['crack']}"
    else:
        conflict = f"{place} 크게 부딪히는 조합은 적습니다. 다만 역할이 겹치면 작은 차이가 커질 수 있습니다."
    resolution = f"{example['next']} {place} 이 순서를 기준으로 삼습니다."
    advice = " ".join(parts[:2] + [example["next"]])
    return {
        "overall": " ".join(parts),
        "love": "",
        "communication": communication,
        "conflict": conflict,
        "conflict_resolution": resolution,
        "economy": "",
        "relationship_advice": advice,
    }


def headline(score: int, relation_type: str) -> Dict[str, str]:
    return {
        "relation_type": "성향 궁합",
        "one_liner": one_liner(score, relation_type),
        "band": _band(score),
    }
