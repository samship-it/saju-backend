"""대운/세운/일운 실시간 보정 엔진.

AI 호출 없음. daily_db.json(일주×일진=3,600) 은 원국(일주) 기준의 "오늘" 텍스트만
갖고 있고 대운/세운을 전혀 모른다(설계 확인 완료). 이 모듈은 이미 core/saju_base.py
가 계산해 saju_data 에 담아둔 current_daewoon/seewoon_10years/today_ganji/strength 를
읽어 대운·세운·일운 3개 레이어의 십신·지지관계·억부용신 희기를 순수 함수로 계산하고,
그 결과를 (1) 점수 가감치(-40~+40), (2) 짧은 상태 코멘트, (3) 십이신살/백호/양인
경고 로 합성해 daily 응답에 얹는다.

삼재(三災)는 여기 넣지 않는다 — 3년 유지되는 배경 상태를 매일 점수에 고정 감점으로
넣으면 "3년 내내 매일 나쁜 점수"가 되는 구조적 오류라 daily 범위에서 제외(사용자
확정). yearly(연간 총운) 쪽에 정보성 문구로 넣는 방향은 별도로 논의.

daily_db.json 은 이 모듈이 절대 건드리지 않는다(읽기 전용 정적 콘텐츠 유지).
"""
from typing import Any, Dict, List, Optional

from core.constants import GAN_ELEM, JI_ELEM, BAEKHO, YANGIN
from core.daewoon import branch_relation
from core.sipsin import calculate_sipsin, sipsin_group
from core.twelve_sinsal import sinsal_check

# ── 1. 십신 극성 기본값(억부용신 정보가 없을 때의 폴백) ─────────────────────
# daily_prompt() 가 쓰던 관습: 정재·정관·정인·식신·편재=안정/기회,
# 편관·상관·겁재·편인=변동/자극/주의. 신강약 판정이 있으면 2번 로직이 이 값을 덮어쓴다.
SIPSIN_POLARITY: Dict[str, float] = {
    "정재": 1.0, "편재": 0.5,
    "정관": 1.0, "편관": -1.0,
    "정인": 0.8, "편인": -0.5,
    "식신": 0.7, "상관": -0.8,
    "비견": 0.2, "겁재": -0.6,
}

# ── 2. 억부용신 기준 희기(喜忌) 극성 — 오행이 용신/희신/기신 중 어디 속하는지로 덮어씀 ──
_YONGSIN_POLARITY = 1.0
_HEESIN_POLARITY = 0.6
_GISIN_POLARITY = -1.0


def _resolve_polarity(sipsin: str, elem: str, group: str, strength: Dict[str, Any]) -> float:
    """오행이 용신/희신/기신에 속하면 그 방향으로 극성을 덮어쓴다(한신이면 기본표 폴백).

    사용자 지정 규칙: 신약 사주에 식상(식신/상관) 일운·대운·세운이 들어오면
    '재능 발휘(+)'가 아니라 '기운 소모/말실수/구설수(-)'다 — 오행이 한신이라
    용신/기신 어느 쪽에도 안 걸려도, 신약+식상이면 무조건 부정으로 강제한다.
    """
    yongsin = set(strength.get("yongsin") or [])
    gisin = set(strength.get("gisin") or [])
    heesin = set(strength.get("heesin") or [])

    if elem in gisin:
        polarity = _GISIN_POLARITY
    elif elem in yongsin:
        polarity = _YONGSIN_POLARITY
    elif elem in heesin:
        polarity = _HEESIN_POLARITY
    else:
        polarity = SIPSIN_POLARITY.get(sipsin, 0.0)

    if strength.get("verdict") == "신약" and group == "식상":
        polarity = min(polarity, -0.6)

    return polarity


# ── 3. 지지관계(일지 vs 대운/세운/일운 지지) 점수 ───────────────────────────
BRANCH_RELATION_SCORE: Dict[str, float] = {
    "육합": 1.0, "복음": 0.3, "자형": -0.5,
    "충": -1.0, "형": -0.8, "파": -0.5, "해": -0.5, "무관": 0.0,
}

# ── 4. 레이어 가중치 — 대운(배경) > 세운(올해) > 일운(오늘), 최대 ±18/±14/±10 ──
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

# 관계가 "무관/복음"(neutral·repeat 버킷)이어도, 억부용신 희기가 뚜렷하면(정규화
# 강도 기준) 라벨을 "무난한 흐름"으로 뭉개지 않고 기존 conflict/harmony 문구를
# 재사용해 드러낸다. 30종 표를 새로 안 늘리고 재사용하는 방식.
_NEUTRAL_OVERRIDE_THRESHOLD = 0.2

# ── 5. 십이신살/백호/양인 오늘 경고 문구 ────────────────────────────────────
SINSAL_NOTE: Dict[str, str] = {
    "겁살": "오늘은 겁살(劫煞)에 해당하는 날이에요. 예상치 못한 지출이나 손실에 주의하세요.",
    "재살": "오늘은 재살(災煞)에 해당하는 날이에요. 사고나 다툼이 생기지 않게 평소보다 조심하세요.",
    "천살": "오늘은 천살(天煞)에 해당하는 날이에요. 뜻대로 안 풀리는 일이 있어도 순리대로 받아들이는 게 낫습니다.",
    "망신살": "오늘은 망신살(亡身煞)에 해당하는 날이에요. 말과 행동을 신중히 해서 구설수에 오르지 않게 하세요.",
    "백호": "오늘은 백호살(白虎殺)이 발동하는 날이에요. 안전·건강 관련해서 평소보다 조심하세요.",
    "양인": "오늘은 양인살(陽刃殺)이 발동하는 날이에요. 기운이 강하게 몰리는 날이라 감정 조절에 신경 쓰세요.",
}
SINSAL_PENALTY: Dict[str, int] = {
    "겁살": -8, "재살": -8, "천살": -6, "망신살": -8, "백호": -10, "양인": -6,
}
_SINSAL_LAYER_SCALE = {"ilwoon": 1.0, "daewoon": 0.75, "sewoon": 0.75}


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


def _layer_facts(day_master: str, day_branch: str, ganji: str, strength: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not ganji or len(ganji) < 2:
        return None
    gan, ji = ganji[0], ganji[1]
    sipsin_gan = calculate_sipsin(day_master, gan, is_gan=True)
    sipsin_ji = calculate_sipsin(day_master, ji, is_gan=False)
    group_gan = sipsin_group(sipsin_gan)
    group_ji = sipsin_group(sipsin_ji)
    relation = branch_relation(day_branch, ji)
    return {
        "ganji": ganji,
        "sipsin_gan": sipsin_gan,
        "sipsin_ji": sipsin_ji,
        "group_gan": group_gan,
        "group_ji": group_ji,
        "polarity_gan": _resolve_polarity(sipsin_gan, GAN_ELEM.get(gan, ""), group_gan, strength),
        "polarity_ji": _resolve_polarity(sipsin_ji, JI_ELEM.get(ji, ""), group_ji, strength),
        "relation": relation,
        "relation_bucket": _relation_bucket(relation),
    }


def _layer_score(layer: str, facts: Dict[str, Any]) -> float:
    w = LAYER_WEIGHTS[layer]
    rel_key = _relation_key(facts["relation"])
    return (
        w["gan"] * facts["polarity_gan"]
        + w["ji"] * facts["polarity_ji"]
        + w["relation"] * BRANCH_RELATION_SCORE.get(rel_key, 0.0)
    )


def _resolve_bucket(relation_bucket: str, layer_intensity: float) -> str:
    """관계가 무관/복음이어도 억부용신 희기가 뚜렷하면 conflict/harmony 문구를 재사용."""
    if relation_bucket in ("neutral", "repeat"):
        if layer_intensity <= -_NEUTRAL_OVERRIDE_THRESHOLD:
            return "conflict"
        if layer_intensity >= _NEUTRAL_OVERRIDE_THRESHOLD:
            return "harmony"
    return relation_bucket


def _check_sinsal(day_branch: str, layers: Dict[str, Dict[str, Any]], ilwoon_ganji: str, day_master: str) -> Dict[str, Any]:
    """오늘 일진(+대운/세운)이 일지 기준 십이신살(겁살/재살/천살/망신살)을 형성하는지,
    오늘 일진이 백호/양인에 해당하는지 체크한다. 감점과 경고 문구를 반환."""
    hits: List[Dict[str, Any]] = []
    penalty = 0.0

    for layer, facts in layers.items():
        branch = facts["ganji"][1] if len(facts["ganji"]) > 1 else ""
        r = sinsal_check(day_branch, branch)
        if r["is_warning"]:
            scale = _SINSAL_LAYER_SCALE.get(layer, 0.75)
            p = SINSAL_PENALTY.get(r["name"], -6) * scale
            hits.append({"layer": layer, "name": r["name"], "penalty": round(p, 1)})
            penalty += p

    if ilwoon_ganji and len(ilwoon_ganji) >= 2:
        if ilwoon_ganji in BAEKHO:
            p = SINSAL_PENALTY["백호"]
            hits.append({"layer": "ilwoon", "name": "백호", "penalty": p})
            penalty += p
        if YANGIN.get(day_master) == ilwoon_ganji[1]:
            p = SINSAL_PENALTY["양인"]
            hits.append({"layer": "ilwoon", "name": "양인", "penalty": p})
            penalty += p

    notes = [SINSAL_NOTE[h["name"]] for h in hits]
    return {"hits": hits, "penalty": round(penalty, 1), "notes": notes}


# ── 6. 기운 조합 상태 표 (5 십신군 × 6 관계버킷 = 30종, AI 미관여 고정 문구) ──
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
    """saju_data(calculate_saju 산출물) -> 점수 가감치·상태 라벨·십이신살 경고 종합."""
    day_master = saju_data.get("day_master") or ""
    day_branch = saju_data.get("day_branch") or ""
    strength = saju_data.get("strength") or {}

    daewoon_ganji = (saju_data.get("current_daewoon") or {}).get("ganji", "")
    seewoon_list = saju_data.get("seewoon_10years") or []
    sewoon_ganji = seewoon_list[0].get("ganji", "") if seewoon_list else ""
    ilwoon_ganji = (saju_data.get("today_ganji") or {}).get("day", "")

    raw_ganji = {"daewoon": daewoon_ganji, "sewoon": sewoon_ganji, "ilwoon": ilwoon_ganji}
    layers: Dict[str, Dict[str, Any]] = {}
    total = 0.0
    for layer, ganji in raw_ganji.items():
        facts = _layer_facts(day_master, day_branch, ganji, strength)
        if not facts:
            continue
        score = _layer_score(layer, facts)
        facts["layer_score"] = round(score, 2)
        facts["layer_intensity"] = round(score / _LAYER_MAX_MAGNITUDE[layer], 3)
        layers[layer] = facts
        total += score

    sinsal = _check_sinsal(day_branch, layers, ilwoon_ganji, day_master)
    total += sinsal["penalty"]

    score_delta = max(-40, min(40, round(total)))

    # 라벨은 "가장 강하게 발동된 레이어"를 트리거로 선택한다(정규화 강도 기준,
    # 동률이면 대운>세운>일운). 관계가 무관/복음이어도 희기가 뚜렷하면 버킷을 보정한다.
    trigger_layer = None
    if layers:
        trigger_layer = max(
            layers,
            key=lambda layer: (abs(layers[layer]["layer_intensity"]), -_LAYER_PRIORITY.index(layer)),
        )

    if trigger_layer and trigger_layer in layers:
        facts = layers[trigger_layer]
        bucket = _resolve_bucket(facts["relation_bucket"], facts["layer_intensity"])
        state = WOON_STATE_TABLE.get(facts["group_gan"], {}).get(bucket, _DEFAULT_STATE)
    else:
        state = _DEFAULT_STATE

    state_comment = state["comment"]
    if sinsal["notes"]:
        state_comment = state_comment + " " + " ".join(sinsal["notes"])

    return {
        "score_delta": score_delta,
        "state_label": state["label"],
        "state_comment": state_comment,
        "trigger_layer": trigger_layer,
        "layers": layers,
        "sinsal_hits": sinsal["hits"],
        "sinsal_penalty": sinsal["penalty"],
    }
