"""대운/세운/일운 실시간 보정 엔진.

AI 호출 없음. daily_db.json(일주×일진=3,600) 은 원국(일주) 기준의 "오늘" 텍스트만
갖고 있고 대운/세운을 전혀 모른다(설계 확인 완료). 이 모듈은 이미 core/saju_base.py
가 계산해 saju_data 에 담아둔 current_daewoon/seewoon_10years/today_ganji 를 읽어
대운·세운·일운 3개 레이어의 십신·지지관계를 순수 함수로 계산하고, 그 결과를
(1) 점수 가감치(-40~+40), (2) 짧은 상태 코멘트 로 합성해 daily 응답에 얹는다.

daily_db.json 은 이 모듈이 절대 건드리지 않는다(읽기 전용 정적 콘텐츠 유지).
"""
from typing import Any, Dict, Optional

from core.daewoon import branch_relation
from core.sipsin import calculate_sipsin, sipsin_group

# ── 1. 십신 극성(그 십신 자체의 길흉 방향) ──────────────────────────────────
# daily_prompt() 가 이미 쓰던 관습: 정재·정관·정인·식신·편재=안정/기회,
# 편관·상관·겁재·편인=변동/자극/주의. 비견/겁재만 비겁 내에서 갈린다.
SIPSIN_POLARITY: Dict[str, float] = {
    "정재": 1.0, "편재": 0.5,
    "정관": 1.0, "편관": -1.0,
    "정인": 0.8, "편인": -0.5,
    "식신": 0.7, "상관": -0.8,
    "비견": 0.2, "겁재": -0.6,
}

# ── 2. 지지관계(일지 vs 대운/세운/일운 지지) 점수 ───────────────────────────
BRANCH_RELATION_SCORE: Dict[str, float] = {
    "육합": 1.0, "복음": 0.3, "자형": -0.5,
    "충": -1.0, "형": -0.8, "파": -0.5, "해": -0.5, "무관": 0.0,
}

# ── 3. 레이어 가중치 — 대운(배경) > 세운(올해) > 일운(오늘), 최대 ±18/±14/±10 ──
LAYER_WEIGHTS: Dict[str, Dict[str, int]] = {
    "daewoon": {"gan": 6, "ji": 4, "relation": 8},
    "sewoon": {"gan": 5, "ji": 3, "relation": 6},
    "ilwoon": {"gan": 4, "ji": 2, "relation": 4},
}

_LAYER_PRIORITY = ("daewoon", "sewoon", "ilwoon")

# 레이어별 이론상 최대 절대 점수(모든 항이 극단값일 때) — 트리거 레이어 선정 시
# 원점수를 그대로 비교하면 가중치가 큰 대운이 거의 항상 이겨버리므로(파 -10.8 이
# 충 -10.0 을 근소하게 이기는 식), "자기 최대치 대비 비율(정규화 강도)"로 비교한다.
_LAYER_MAX_MAGNITUDE = {layer: sum(w.values()) for layer, w in LAYER_WEIGHTS.items()}


def _relation_key(relation: str) -> str:
    """branch_relation() 의 '충(충돌·이동)' 같은 라벨을 점수표 키로 정규화."""
    r = relation or "무관"
    if r.startswith("복음"):
        return "자형" if "자형" in r else "복음"
    return r.split("(")[0] if "(" in r else r


def _relation_bucket(relation: str) -> str:
    """social_template.py 의 _relation_bucket() 과 동일한 6버킷 분류(단일 소스 유지 위해 동형 유지)."""
    r = relation or ""
    if r.startswith("육합"):
        return "harmony"
    if r.startswith("충"):
        return "conflict"
    if r.startswith("형"):
        return "adjustment"
    if r.startswith("파") or r.startswith("해"):
        return "friction"
    if r.startswith("복음"):
        return "repeat"
    return "neutral"


def _layer_facts(day_master: str, day_branch: str, ganji: str) -> Optional[Dict[str, Any]]:
    if not ganji or len(ganji) < 2:
        return None
    gan, ji = ganji[0], ganji[1]
    sipsin_gan = calculate_sipsin(day_master, gan, is_gan=True)
    sipsin_ji = calculate_sipsin(day_master, ji, is_gan=False)
    relation = branch_relation(day_branch, ji)
    return {
        "ganji": ganji,
        "sipsin_gan": sipsin_gan,
        "sipsin_ji": sipsin_ji,
        "group_gan": sipsin_group(sipsin_gan),
        "relation": relation,
        "relation_bucket": _relation_bucket(relation),
    }


def _layer_score(layer: str, facts: Dict[str, Any]) -> float:
    w = LAYER_WEIGHTS[layer]
    rel_key = _relation_key(facts["relation"])
    return (
        w["gan"] * SIPSIN_POLARITY.get(facts["sipsin_gan"], 0.0)
        + w["ji"] * SIPSIN_POLARITY.get(facts["sipsin_ji"], 0.0)
        + w["relation"] * BRANCH_RELATION_SCORE.get(rel_key, 0.0)
    )


# ── 4. 기운 조합 상태 표 (5 십신군 × 6 관계버킷 = 30종, AI 미관여 고정 문구) ──
WOON_STATE_TABLE: Dict[str, Dict[str, Dict[str, str]]] = {
    "비겁": {
        "harmony": {"label": "동료운 상승", "comment": "함께하면 힘이 실리는 시기예요. 협업이나 동업 제안이 있다면 긍정적으로 봐도 좋습니다."},
        "conflict": {"label": "경쟁/마찰 주의", "comment": "주변과 은근히 부딪히기 쉬운 시기예요. 굳이 이기려 들지 않는 편이 낫습니다."},
        "adjustment": {"label": "역할 조정 필요", "comment": "함께 일하는 사람과 역할·몫을 다시 정리할 필요가 있는 시기예요."},
        "friction": {"label": "사소한 어긋남", "comment": "동료·친구 관계에서 타이밍이 살짝 안 맞을 수 있어요. 서두르지 마세요."},
        "repeat": {"label": "익숙한 흐름 지속", "comment": "지금까지 해오던 관계·방식이 안정적으로 이어지는 시기입니다."},
        "neutral": {"label": "무난한 흐름", "comment": "특별한 이슈 없이 잔잔하게 흘러가는 시기예요."},
    },
    "식상": {
        "harmony": {"label": "표현/기회 상승", "comment": "아이디어와 말이 잘 통하는 시기예요. 적극적으로 나서면 좋은 반응을 얻습니다."},
        "conflict": {"label": "말실수/과욕 주의", "comment": "하고 싶은 말이 많아 오버하기 쉬운 시기예요. 표현을 한 번 더 다듬어 보세요."},
        "adjustment": {"label": "표현 방식 조정", "comment": "의도와 다르게 전달되기 쉬운 시기예요. 말과 행동을 한 번 더 점검하세요."},
        "friction": {"label": "소통 엇갈림 주의", "comment": "대화나 일정이 살짝 어긋나는 순간이 있을 수 있어요."},
        "repeat": {"label": "익숙한 리듬 유지", "comment": "해오던 방식 그대로 편안하게 진행되는 시기입니다."},
        "neutral": {"label": "무난한 흐름", "comment": "표현이나 활동 면에서 특별한 굴곡 없이 흘러가는 시기예요."},
    },
    "재성": {
        "harmony": {"label": "재물 기회", "comment": "들어오는 흐름이 좋아지는 시기입니다. 기회다 싶으면 조금 과감해져도 좋습니다."},
        "conflict": {"label": "지출/구설 주의", "comment": "돈 문제로 신경전이 생기거나 예상 밖 지출이 나갈 수 있는 시기예요. 큰돈은 신중하게 움직이세요."},
        "adjustment": {"label": "돈 관리 재정비", "comment": "수입·지출 구조를 다시 점검할 필요가 있는 시기입니다."},
        "friction": {"label": "계산 어긋남 주의", "comment": "거래나 정산에서 사소하게 안 맞는 부분이 생길 수 있어요. 미리 확인하세요."},
        "repeat": {"label": "안정적 자산 흐름", "comment": "지금까지의 재정 흐름이 큰 변화 없이 이어지는 시기예요."},
        "neutral": {"label": "무난한 흐름", "comment": "재물 면에서 특별한 이슈 없이 평이하게 흘러가는 시기입니다."},
    },
    "관성": {
        "harmony": {"label": "명예/승진운", "comment": "책임진 일이 좋은 평가로 이어지는 흐름이에요. 나서야 할 자리에서 존재감을 보여도 좋습니다."},
        "conflict": {"label": "관재/마찰 주의", "comment": "윗선·계약·공적인 자리에서 부딪힐 일이 생기기 쉬운 시기예요. 서류나 약속은 한 번 더 확인하세요."},
        "adjustment": {"label": "역할/책임 재정비", "comment": "맡은 역할과 책임 범위를 다시 정리할 필요가 있는 시기입니다."},
        "friction": {"label": "보고/전달 주의", "comment": "윗사람과의 소통에서 타이밍이 어긋나기 쉬운 시기예요. 조금 더 정중하고 명확하게 전달하세요."},
        "repeat": {"label": "안정적 위치 유지", "comment": "맡은 자리에서 꾸준함만으로 충분히 인정받는 시기입니다."},
        "neutral": {"label": "무난한 흐름", "comment": "조직·공적 관계에서 특별한 이슈 없이 평온하게 흘러가는 시기예요."},
    },
    "인성": {
        "harmony": {"label": "귀인/학업운 상승", "comment": "믿을 만한 조력자나 배움의 기회를 만나기 좋은 시기예요. 고민이 있다면 이 시기에 털어놓아 보세요."},
        "conflict": {"label": "잔소리/부담 주의", "comment": "조언이 부담스럽게 느껴질 수 있는 시기예요. 일단 듣고 판단은 천천히 해도 늦지 않습니다."},
        "adjustment": {"label": "기대치 조율 필요", "comment": "도움을 주고받는 관계에서 기대치를 조율할 필요가 있는 시기입니다."},
        "friction": {"label": "미묘한 결 차이", "comment": "조언·도움을 주고받는 과정에서 결이 살짝 안 맞을 수 있어요."},
        "repeat": {"label": "안정적 조력 지속", "comment": "의지하던 사람과의 관계가 꾸준히 이어지는 시기입니다."},
        "neutral": {"label": "무난한 흐름", "comment": "조력자·배움 면에서 특별한 일 없이 잔잔한 시기예요."},
    },
}

_DEFAULT_STATE = {"label": "무난한 흐름", "comment": "특별한 이슈 없이 잔잔하게 흘러가는 시기예요."}


def compute_woon_modifier(saju_data: Dict[str, Any]) -> Dict[str, Any]:
    """saju_data(calculate_saju 산출물) -> {"score_delta", "state_label", "state_comment", "trigger_layer", "layers"}."""
    day_master = saju_data.get("day_master") or ""
    day_branch = saju_data.get("day_branch") or ""

    daewoon_ganji = (saju_data.get("current_daewoon") or {}).get("ganji", "")
    seewoon_list = saju_data.get("seewoon_10years") or []
    sewoon_ganji = seewoon_list[0].get("ganji", "") if seewoon_list else ""
    ilwoon_ganji = (saju_data.get("today_ganji") or {}).get("day", "")

    raw_ganji = {"daewoon": daewoon_ganji, "sewoon": sewoon_ganji, "ilwoon": ilwoon_ganji}
    layers: Dict[str, Dict[str, Any]] = {}
    layer_scores: Dict[str, float] = {}
    total = 0.0
    for layer, ganji in raw_ganji.items():
        facts = _layer_facts(day_master, day_branch, ganji)
        if not facts:
            continue
        score = _layer_score(layer, facts)
        facts["layer_score"] = round(score, 2)
        facts["layer_intensity"] = round(score / _LAYER_MAX_MAGNITUDE[layer], 3)
        layers[layer] = facts
        layer_scores[layer] = score
        total += score

    score_delta = max(-40, min(40, round(total)))

    # 라벨은 "가장 강하게 발동된 레이어"를 트리거로 선택한다. 원점수(layer_score) 그대로
    # 비교하면 가중치가 큰 대운이 거의 항상 이겨버리므로(약한 관계라도 무거운 레이어가
    # 이김), 각 레이어의 자기 최대치 대비 비율(layer_intensity)로 정규화해서 비교한다.
    # 동률이면 대운>세운>일운으로 tie-break.
    trigger_layer = None
    if layers:
        trigger_layer = max(
            layers,
            key=lambda layer: (abs(layers[layer]["layer_intensity"]), -_LAYER_PRIORITY.index(layer)),
        )

    if trigger_layer and trigger_layer in layers:
        facts = layers[trigger_layer]
        state = WOON_STATE_TABLE.get(facts["group_gan"], {}).get(facts["relation_bucket"], _DEFAULT_STATE)
    else:
        state = _DEFAULT_STATE

    return {
        "score_delta": score_delta,
        "state_label": state["label"],
        "state_comment": state["comment"],
        "trigger_layer": trigger_layer,
        "layers": layers,
    }
