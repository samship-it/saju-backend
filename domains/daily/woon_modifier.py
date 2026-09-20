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

headline/today_energy 문구는 이제 HEADLINE_TABLE/TODAY_ENERGY_TABLE(셀당 1개, 아래
30~60종) 을 최종 폴백으로 두고, 우선은 domains/daily/headline_pool.py 가 읽는
사전 생성 대형 풀(셀당 기본 20개, scripts/generate_content_db.py --domain
daily_headline_pool 로 생성)에서 target_date 기준으로 결정적 로테이션해 고른다.
이 조회 역시 정적 JSON 파일 읽기일 뿐 런타임 Gemini 호출이 아니다.
"""
import datetime
from typing import Any, Dict, List, Optional

from core.constants import GAN_ELEM, JI_ELEM, BAEKHO, YANGIN
from core.daewoon import branch_relation
from core.sipsin import calculate_sipsin, sipsin_group
from core.twelve_sinsal import sinsal_check
from domains.daily.headline_pool import pick_headline, pick_today_energy

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

# 헤드라인에 신살을 짧게 덧붙일 때 쓰는 절(clause) — SINSAL_NOTE(두 문장, woon_today용)보다
# 짧게 한 구절로 줄인 버전. 신살이 여러 개 겹치면 감점이 가장 큰(=가장 강한) 것 하나만 붙인다.
SINSAL_HEADLINE_SUFFIX: Dict[str, str] = {
    "겁살": "겁살(劫煞)까지 겹치니 지출·손실에 유의하세요.",
    "재살": "재살(災煞)까지 겹치니 사고·다툼에 유의하세요.",
    "천살": "천살(天煞)까지 겹치니 뜻대로 안 풀려도 순리대로 받아들이세요.",
    "망신살": "망신살(亡身煞)까지 겹치니 말과 행동에 신경 쓰세요.",
    "백호": "백호살(白虎殺)까지 겹치니 안전·건강에 더 유의하세요.",
    "양인": "양인살(陽刃殺)까지 겹치니 감정 조절에 신경 쓰세요.",
}

# ── 6. 영역별 십신군 소속 — core/domain_derived.py의 domains 딕셔너리와 동일(단일
# 소스 유지 위해 반드시 동기화). money/love/work_study 각 점수는 이제 score_delta를
# 균등 복사하지 않고, 그 점수와 관련 없는 십신군의 기여는 제외한 별도 델타를 쓴다.
DOMAIN_GROUPS: Dict[str, set] = {
    "money": {"재성", "식상", "비겁"},
    "love": {"관성", "재성", "인성"},
    "work_study": {"관성", "인성", "식상"},
}


def _domain_delta(layers: Dict[str, Dict[str, Any]], domain_groups: set) -> int:
    """도메인 소속 십신군에 해당하는 글자(천간/지지)의 기여만 합산 — 지지관계는
    지지(ji)가 속한 그룹을 따른다. 신살 감점은 도메인별로 안 쪼개고 overall에만 반영."""
    total = 0.0
    for layer, w in LAYER_WEIGHTS.items():
        f = layers.get(layer)
        if not f:
            continue
        if f["group_gan"] in domain_groups:
            total += w["gan"] * f["polarity_gan"]
        if f["group_ji"] in domain_groups:
            total += w["ji"] * f["polarity_ji"]
            rel_key = _relation_key(f["relation"])
            total += w["relation"] * BRANCH_RELATION_SCORE.get(rel_key, 0.0)
    return max(-40, min(40, round(total)))


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
    """실제 신호 부호(희기 반영된 layer_intensity)가 항상 우선한다.

    예전 버전은 관계가 '무관/복음'일 때만 부호를 재확인했는데, 그 결과 관계가
    '해'(friction) 같은 비-중립 버킷이면 부호가 실제로 양수여도 무조건 "주의" 문구가
    나가는 버그가 있었다(1961년생 남 실측: intensity +0.36인데도 relation_bucket이
    friction이라 "보고/전달 주의"가 뜸). 이제 모든 버킷에서 강도가 임계값을 넘으면
    부호가 이긴다 — 관계 타입은 "부정일 때 어떤 종류의 부정인지"만 고른다.
    """
    if layer_intensity >= _NEUTRAL_OVERRIDE_THRESHOLD:
        return "harmony"
    if layer_intensity <= -_NEUTRAL_OVERRIDE_THRESHOLD:
        return relation_bucket if relation_bucket in ("conflict", "adjustment", "friction") else "conflict"
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

# ── 7. 상태별 한줄평(headline) 고정 문구 (10 십신 × 6 관계버킷 = 60종, AI 미관여) ──
# WOON_STATE_TABLE의 label/comment와는 다른 각도(느낌/행동 팁 중심)로 새로 쓴 문장이다.
# headline·woon_today·social이 같은 (group,bucket) 신호를 그대로 복붙해 3중 반복되던
# 문제를 고치기 위해, 세 필드가 서로 다른 단어·구조로 같은 신호를 전달하도록 분리했다.
#
# 키를 5십신군이 아니라 10개 개별 십신으로 세분화한 이유(사용자 리포트: 오늘의 운세
# 한줄평이 어제와 똑같이 반복됨) — 일진 천간은 10일 주기로 매일 +1칸씩 도는데, 십신군은
# 그 중 이웃한 두 칸(비견↔겁재, 식신↔상관, 편재↔정재, 편관↔정관, 편인↔정인)이 항상
# 같은 그룹으로 묶인다. 즉 그룹(5종) 기준으로 조회하면 이틀에 한 번꼴로 어제와 같은
# 셀을 다시 조회해 문장이 그대로 반복된다. 개별 십신(10종)으로 쪼개면 이 이웃 쌍이
# GAN_YANG(음양)으로 갈라져(예: 비견=양간, 겁재=음간) 매일 음양이 번갈아 바뀌므로 —
# 하루 단위로는 (그룹이 바뀌거나, 그룹은 같아도 음양이 달라 다른 십신) 둘 중 하나라
# 어제와 정확히 같은 키가 다시 나오는 경우가 구조적으로 없다(직전 이력 조회 없이도
# 보장됨). 10일 주기를 완전히 한 바퀴 돌면 같은 키가 재등장할 수 있으나 그건 "어제"가
# 아니라 열흘 전이라 반복 체감이 거의 없다.
HEADLINE_TABLE: Dict[str, Dict[str, str]] = {
    "비견": {
        "harmony": "함께하면 시너지가 나는 날이니 협업 제안이 있다면 적극적으로 받아들이세요.",
        "conflict": "괜히 경쟁심이 발동하기 쉬운 날이니 힘 빼고 가는 게 이득이에요.",
        "adjustment": "역할 분담을 다시 맞춰보면 훨씬 수월해지는 하루예요.",
        "friction": "타이밍이 살짝 어긋나도 서두르지 않으면 무난히 지나가는 하루예요.",
        "repeat": "익숙한 리듬 그대로, 무리하지 않아도 되는 편안한 하루예요.",
        "neutral": "특별한 사건 없이 잔잔하게 흘러가는 하루예요.",
    },
    "겁재": {
        "harmony": "가까운 사람과 손발이 척척 맞는 날이니 도움을 주고받는 데 망설이지 마세요.",
        "conflict": "은근히 지는 걸 못 참게 되는 날이니 굳이 승부를 보려 하지 마세요.",
        "adjustment": "내 몫과 남의 몫을 한번 명확히 나눠두면 뒤탈이 없는 하루예요.",
        "friction": "누가 먼저랄 것 없이 신경전이 붙기 쉬우니 한 발 물러서 보세요.",
        "repeat": "옆 사람과 늘 그렇듯 티격태격해도 결국 무난히 넘어가는 하루예요.",
        "neutral": "경쟁이나 비교할 일 없이 조용히 흘러가는 하루예요.",
    },
    "식신": {
        "harmony": "아이디어가 술술 풀리는 날이니 적극적으로 표현해 보세요.",
        "conflict": "느긋함이 게으름으로 비칠 수 있는 날이니 마감만큼은 챙기세요.",
        "adjustment": "의도와 다르게 전달될 수 있으니 표현을 한 번 더 점검해보는 하루예요.",
        "friction": "여유를 부리다 타이밍을 놓칠 수 있으니 중요한 건 미리 챙기세요.",
        "repeat": "늘 하던 방식 그대로 편안하게 흘러가는 하루예요.",
        "neutral": "표현이나 활동 면에서 튀는 일 없이 흘러가는 하루예요.",
    },
    "상관": {
        "harmony": "재치 있는 한마디가 먹히는 날이니 하고 싶은 말을 시원하게 꺼내도 좋아요.",
        "conflict": "직설적인 말이 날카롭게 튈 수 있는 날이니 하고 싶은 말은 한 번 걸러서 꺼내보세요.",
        "adjustment": "옳은 말도 방식에 따라 다르게 들리니 톤을 한 번 더 다듬어보는 하루예요.",
        "friction": "사소한 착오가 생길 수 있으니 중요한 이야기는 명확하게 짚고 가세요.",
        "repeat": "할 말은 하면서도 크게 부딪히지 않고 넘어가는 하루예요.",
        "neutral": "말이나 논쟁거리 없이 조용히 지나가는 하루예요.",
    },
    "편재": {
        "harmony": "생각보다 좋은 제안이 들어올 수 있는 날이니 기회다 싶으면 잡아보세요.",
        "conflict": "돈 씀씀이에 예민해지기 쉬운 날이니 큰 지출은 하루 미뤄보세요.",
        "adjustment": "여러 갈래로 벌인 돈 흐름을 한번 정리해보면 도움이 되는 하루예요.",
        "friction": "정산이나 계산에서 사소하게 안 맞을 수 있으니 미리 확인해두세요.",
        "repeat": "지금 흐름 그대로 안정적으로 이어지는 하루예요.",
        "neutral": "재물 면에서 특별한 이슈 없이 평이하게 흘러가는 하루예요.",
    },
    "정재": {
        "harmony": "꾸준히 모아온 게 눈에 띄게 불어나는 날이니 계획한 저축·투자를 이어가도 좋아요.",
        "conflict": "고정 지출이 부담스럽게 느껴지는 날이니 가계부부터 다시 훑어보세요.",
        "adjustment": "수입·지출 구조를 한번 점검해보면 도움이 되는 하루예요.",
        "friction": "정기적으로 나가는 돈에서 사소하게 안 맞는 부분이 생길 수 있으니 확인해두세요.",
        "repeat": "정해둔 방식대로 안정적으로 관리되는 하루예요.",
        "neutral": "고정 수입·지출 면에서 특별한 변동 없이 흘러가는 하루예요.",
    },
    "편관": {
        "harmony": "부담스럽던 일도 과감하게 밀어붙이면 뜻밖에 잘 풀리는 날이에요.",
        "conflict": "윗선이나 공적인 일에서 부딪힐 수 있으니 서류나 약속은 한 번 더 챙겨보세요.",
        "adjustment": "쫓기듯 처리하던 일의 우선순위를 다시 정리해두면 든든해지는 하루예요.",
        "friction": "예상치 못한 압박이 갑자기 들이닥칠 수 있으니 여유 시간을 좀 남겨두세요.",
        "repeat": "버거운 상황에도 어떻게든 버텨내며 넘어가는 하루예요.",
        "neutral": "긴장할 일 없이 조직·공적 관계가 평온하게 흘러가는 하루예요.",
    },
    "정관": {
        "harmony": "책임진 일이 좋은 평가로 돌아오는 날이니 나서야 할 자리에서 존재감을 보여도 좋아요.",
        "conflict": "규칙이나 절차가 답답하게 느껴질 수 있으니 원칙대로 처리하는 게 결국 더 편해요.",
        "adjustment": "맡은 역할과 책임을 다시 정리해두면 든든해지는 하루예요.",
        "friction": "보고나 전달 타이밍이 살짝 어긋날 수 있으니 조금 더 명확하게 전해보세요.",
        "repeat": "지금 자리를 꾸준히 지키는 것만으로 충분한 하루예요.",
        "neutral": "조직이나 공적인 관계에서 평온하게 흘러가는 하루예요.",
    },
    "편인": {
        "harmony": "남들과 다른 촉이 발휘되는 날이니 낯선 아이디어나 배움에 과감히 뛰어들어도 좋아요.",
        "conflict": "생각이 많아져 의심부터 앞서기 쉬운 날이니 일단 믿고 한 걸음 내디뎌 보세요.",
        "adjustment": "혼자 끌어안던 고민을 누군가와 나눠보면 정리가 되는 하루예요.",
        "friction": "감(感)이 평소와 살짝 어긋날 수 있으니 중요한 판단은 한 번 더 검증하세요.",
        "repeat": "익숙한 방식·감각을 믿고 가도 되는 편안한 하루예요.",
        "neutral": "번뜩이는 영감 없이도 무난하게 흘러가는 하루예요.",
    },
    "정인": {
        "harmony": "귀인이나 배움의 기회를 만나기 좋은 날이니 고민이 있다면 오늘 털어놔 보세요.",
        "conflict": "조언이 부담스럽게 느껴질 수 있으니 일단 듣고 판단은 천천히 해도 괜찮아요.",
        "adjustment": "기대치를 서로 맞춰보면 관계가 한결 편해지는 하루예요.",
        "friction": "조언을 주고받는 결이 살짝 안 맞을 수 있으니 가볍게 확인해보세요.",
        "repeat": "의지하던 관계가 꾸준히 이어지는 편안한 하루예요.",
        "neutral": "조력자·배움 면에서 특별한 일 없이 잔잔한 하루예요.",
    },
}

_DEFAULT_HEADLINE = "오늘은 큰 굴곡 없이 잔잔하게 흘러가는 하루예요."


def _resolve_headline(sipsin: Optional[str], bucket: Optional[str], day_ordinal: int = 0) -> str:
    """(오늘 일진의 개별 십신, bucket) 조합의 headline 한 문장. 신살은 절대 안 붙인다 —
    headline은 "오늘 하루 한 줄 요약" 전용이고, 신살 경고는 today_energy 쪽 몫이다.

    사전 생성 대형 풀(headline_pool.json, 셀당 기본 20개)이 있으면 day_ordinal로
    그 안에서 로테이션해 고르고, 없으면(아직 미생성 등) HEADLINE_TABLE(셀당 1개)로
    폴백한다."""
    pooled = pick_headline(sipsin, bucket, day_ordinal)
    if pooled:
        return pooled
    return HEADLINE_TABLE.get(sipsin or "", {}).get(bucket or "") or _DEFAULT_HEADLINE


# ── 8. "오늘의 기운" 전용 고정 문구 (5 십신군 × 6 관계버킷 = 30종, AI 미관여) ──
# HEADLINE_TABLE과 절대 같은 표를 쓰지 않는다 — trigger_layer가 ilwoon으로 뽑히면
# headline과 today_energy가 (group,bucket)까지 완전히 같아져 문장이 그대로 겹치는
# 문제가 있었다(사용자 실측 리포트: 2026-09-19 등 특정 날짜에 두 필드가 동일 문장).
# today_energy는 "내 일간이 오늘 일진과 만나 어떤 기운을 이루는지"를 항상 명시적으로
# 서술해 headline(대운/세운/일운 종합 한 줄)과 문장 구조 자체가 달라지게 한다.
TODAY_ENERGY_TABLE: Dict[str, Dict[str, str]] = {
    "비겁": {
        "harmony": "오늘 일진이 내 기운과 같은 결이라 자신감이 자연스럽게 차오릅니다.",
        "conflict": "오늘 일진의 기운이 나와 팽팽히 맞서면서 괜한 경쟁심을 자극할 수 있어요.",
        "adjustment": "오늘 일진이 내 기운과 부딪히며 역할이나 페이스를 다시 맞추라는 신호를 보냅니다.",
        "friction": "오늘 일진의 기운이 내 기운과 살짝 어긋나며 타이밍이 미묘하게 안 맞을 수 있어요.",
        "repeat": "오늘 일진이 평소 내 기운과 비슷하게 흘러가 낯설지 않은 하루가 됩니다.",
        "neutral": "오늘 일진이 내 기운에 큰 자극을 주지 않아 잔잔하게 지나갑니다.",
    },
    "식상": {
        "harmony": "오늘 일진이 내 표현력을 끌어올려 하고 싶은 말이 술술 풀립니다.",
        "conflict": "오늘 일진의 기운이 나를 들뜨게 만들어 말이 앞서기 쉬운 하루예요.",
        "adjustment": "오늘 일진이 내 표현 방식을 다시 점검해보라는 신호를 보냅니다.",
        "friction": "오늘 일진의 기운이 내 뜻과 살짝 엇갈리며 전달이 미묘하게 어긋날 수 있어요.",
        "repeat": "오늘 일진이 평소 표현 리듬과 비슷하게 흘러가 편안합니다.",
        "neutral": "오늘 일진이 표현 쪽에는 큰 자극을 주지 않아 무난하게 지나갑니다.",
    },
    "재성": {
        "harmony": "오늘 일진이 재물 기운을 북돋아 뜻밖의 기회가 들어올 수 있어요.",
        "conflict": "오늘 일진의 기운이 내 재물운과 부딪히며 지출을 자극할 수 있어요.",
        "adjustment": "오늘 일진이 돈의 흐름을 다시 점검해보라는 신호를 보냅니다.",
        "friction": "오늘 일진의 기운이 재물 계산과 살짝 어긋나며 사소하게 안 맞을 수 있어요.",
        "repeat": "오늘 일진이 평소 재물 흐름과 비슷하게 흘러가 안정적입니다.",
        "neutral": "오늘 일진이 재물 쪽에는 큰 자극을 주지 않아 평이하게 지나갑니다.",
    },
    "관성": {
        "harmony": "오늘 일진이 책임감 있는 내 모습을 부각시켜 좋은 평가로 이어질 수 있어요.",
        "conflict": "오늘 일진의 기운이 윗사람·공적 관계와 부딪히며 마찰을 자극할 수 있어요.",
        "adjustment": "오늘 일진이 맡은 역할과 책임을 다시 정리해보라는 신호를 보냅니다.",
        "friction": "오늘 일진의 기운이 보고나 전달 타이밍과 살짝 어긋날 수 있어요.",
        "repeat": "오늘 일진이 평소 자리와 역할을 그대로 지켜줘 안정적입니다.",
        "neutral": "오늘 일진이 조직·공적 관계에는 큰 자극을 주지 않아 평온하게 지나갑니다.",
    },
    "인성": {
        "harmony": "오늘 일진이 귀인이나 배움의 기운을 끌어당겨 도움을 받기 좋습니다.",
        "conflict": "오늘 일진의 기운이 조언·잔소리를 부담스럽게 느끼도록 자극할 수 있어요.",
        "adjustment": "오늘 일진이 도움을 주고받는 기대치를 다시 맞춰보라는 신호를 보냅니다.",
        "friction": "오늘 일진의 기운이 조언을 주고받는 결과 살짝 어긋날 수 있어요.",
        "repeat": "오늘 일진이 평소 의지하던 관계와 비슷하게 흘러가 편안합니다.",
        "neutral": "오늘 일진이 조력·배움 쪽에는 큰 자극을 주지 않아 잔잔하게 지나갑니다.",
    },
}

_DEFAULT_TODAY_ENERGY = "오늘 일진이 내 기운에 큰 자극을 주지 않아 무난하게 지나갑니다."


def _resolve_today_energy(
    sipsin: Optional[str], bucket: Optional[str], sinsal_hits: List[Dict[str, Any]], day_ordinal: int = 0
) -> str:
    """내 일간이 오늘 일진과 만나 이루는 기운 한 줄 + (있으면) 가장 강한 신살 한 줄만 짧게
    덧붙인다. HEADLINE_TABLE이 아니라 별도 TODAY_ENERGY_TABLE을 쓴다 — headline은 대운/
    세운/일운 중 가장 강한 레이어의 종합 한 줄이라, trigger_layer가 ilwoon이면 같은
    (group,bucket)을 가리켜 headline과 문장이 그대로 겹쳐버리기 때문(사용자 확인·수정).

    사전 생성 대형 풀(today_energy_pool.json)이 있으면 개별 십신(sipsin, 10종) ×
    bucket 셀에서 day_ordinal로 로테이션해 고른다(headline과 동일한 풀 구조 —
    today_energy도 예전엔 십신군(5종) 기준이라 headline과 같은 2일 주기 반복
    위험이 있었다). 풀에 없으면 십신군(TODAY_ENERGY_TABLE, 5종)으로 폴백한다."""
    pooled = pick_today_energy(sipsin, bucket, day_ordinal)
    if pooled:
        base = pooled
    else:
        group = sipsin_group(sipsin) if sipsin else None
        base = TODAY_ENERGY_TABLE.get(group or "", {}).get(bucket or "") or _DEFAULT_TODAY_ENERGY
    if sinsal_hits:
        worst = min(sinsal_hits, key=lambda h: h["penalty"])  # penalty가 가장 큰(가장 음수인) 것
        suffix = SINSAL_HEADLINE_SUFFIX.get(worst["name"])
        if suffix:
            return f"{base} {suffix}"
    return base

_DEFAULT_STATE = {"label": "무난한 흐름", "comment": "특별한 이슈 없이 잔잔하게 흘러가는 시기예요."}


def _day_ordinal(saju_data: Dict[str, Any]) -> int:
    """target_date(YYYY-MM-DD)를 정수 순번으로 — headline/today_energy 풀 로테이션 시드.
    없거나 파싱 실패하면 0(그래도 셀 자체가 매일 달라지므로 안전하게 폴백)."""
    raw = saju_data.get("target_date")
    if not raw:
        return 0
    try:
        return datetime.date.fromisoformat(str(raw)).toordinal()
    except (ValueError, TypeError):
        return 0


def compute_woon_modifier(saju_data: Dict[str, Any]) -> Dict[str, Any]:
    """saju_data(calculate_saju 산출물) -> 점수 가감치·상태 라벨·십이신살 경고 종합."""
    day_ordinal = _day_ordinal(saju_data)
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

    trigger_group = None
    bucket = None
    if trigger_layer and trigger_layer in layers:
        facts = layers[trigger_layer]
        trigger_group = facts["group_gan"]
        bucket = _resolve_bucket(facts["relation_bucket"], facts["layer_intensity"])
        state = WOON_STATE_TABLE.get(trigger_group, {}).get(bucket, _DEFAULT_STATE)
    else:
        state = _DEFAULT_STATE

    state_comment = state["comment"]
    if sinsal["notes"]:
        state_comment = state_comment + " " + " ".join(sinsal["notes"])

    # "오늘의 기운"(Today Energy Movement) 전용 — trigger_layer가 대운/세운이어도 이건
    # 항상 ilwoon(오늘 일진) 레이어 하나만 본다. 새 계산 없이 위에서 이미 구한 layers["ilwoon"]
    # (원국 대비 오늘 지지의 십신·용신희기·지지관계)을 그대로 재사용해 HEADLINE_TABLE에서 조회.
    today_sipsin = None
    today_bucket = None
    if "ilwoon" in layers:
        f = layers["ilwoon"]
        today_sipsin = f["sipsin_gan"]
        today_bucket = _resolve_bucket(f["relation_bucket"], f["layer_intensity"])
    ilwoon_sinsal_hits = [h for h in sinsal["hits"] if h["layer"] == "ilwoon"]
    today_energy = _resolve_today_energy(today_sipsin, today_bucket, ilwoon_sinsal_hits, day_ordinal)

    return {
        "score_delta": score_delta,
        "money_delta": _domain_delta(layers, DOMAIN_GROUPS["money"]),
        "love_delta": _domain_delta(layers, DOMAIN_GROUPS["love"]),
        "work_study_delta": _domain_delta(layers, DOMAIN_GROUPS["work_study"]),
        # 대운/세운 중심 "전체 흐름" 라벨/코멘트 — 며칠~몇 년 단위로 안 바뀔 수 있는 배경
        # 정보라 headline(오늘 한 줄)이 아니라 여기(보조 설명 몫)에만 남겨둔다.
        "state_label": state["label"],
        "state_comment": state_comment,
        # 한줄평(headline) — "오늘의 운세"이므로 매일 바뀌는 일진(ilwoon)을 최우선 트리거로
        # 쓴다. 대운/세운은 며칠~몇 년 단위로 고정돼 있어 이걸 트리거로 쓰면 여러 날 동안
        # headline이 똑같이 나가는 문제가 있었다(사용자 실측 리포트: 2026-09-15~17 동일
        # 문장). 대운/세운의 영향은 score_delta(점수)와 state_label/state_comment(보조
        # 설명)에만 반영되고, headline 자체는 today_energy와 같은 신호(오늘 일진)를 쓰되
        # 서로 다른 풀/표(headline_pool.json+HEADLINE_TABLE vs today_energy_pool.json+
        # TODAY_ENERGY_TABLE)라 문장은 겹치지 않는다.
        # today_group(5분류) 대신 today_sipsin(10분류)으로 조회 — 어제·오늘 한줄평이
        # 그대로 반복되던 버그 수정(HEADLINE_TABLE 상단 주석 참고). day_ordinal은 같은
        # 셀이 재등장했을 때도 풀 안에서 다른 변형을 고르기 위한 날짜 시드.
        "headline": _resolve_headline(today_sipsin, today_bucket, day_ordinal),
        # 오늘 일진(ilwoon) 하나만 놓고 본 한줄평 — "Today Energy Movement" 섹션 전용.
        # headline과 정확히 같은 (sipsin,bucket) 신호를 쓰지만 표/풀이 달라 문장은 다르다.
        "today_energy": today_energy,
        "trigger_layer": trigger_layer,
        # social_template.py 가 자체적으로 (그룹,버킷)을 재계산하지 않고 이 값을
        # 그대로 받아쓴다 — woon_state와 summary.social이 항상 같은 방향을 보도록.
        "trigger_group": trigger_group,
        "trigger_bucket": bucket,
        "layers": layers,
        "sinsal_hits": sinsal["hits"],
        "sinsal_penalty": sinsal["penalty"],
    }
