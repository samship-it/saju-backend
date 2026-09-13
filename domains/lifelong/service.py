"""평생운세 (LIFELONG_FORTUNE, 250P).

daily/yearly 와 마찬가지로 런타임 Gemini 호출 없이 사전 생성된 정적 DB에서 즉시
조회한다(DB 생성은 scripts/generate_content_db.py --domain lifelong_base /
lifelong_stage 참고).

한 사람의 원국 + 평생 대운 흐름을 다루므로 daily(일주×일진, 3,600)나
yearly(일주×세운, 3,600)처럼 곧바로 60×60 격자에 대응되지 않는다. 대신:

1) core_nature(타고난 본질) + life_domains(평생 재물/직업/가족/대인관계 성향)는
   일주 60가지에만 의존한다고 본다(personality 도메인과 동일한 트레이드오프).
2) life_stages 의 각 생애단계(1~19/20~29/30~49/50~69/70+) 서술은, 실제 개인의
   정확한 대운 간지 대신 그 단계를 지배하는 십신 5분류(비겁/식상/재성/관성/인성)와
   직전 단계의 십신 5분류로 추상화한다 — 일주(60) × 단계(5) × 지배군(5) × 직전군
   (5, 첫 단계는 "없음" 1가지) = 6,300건. daily 의 "일주×일진" 트레이드오프와
   같은 성격의 단순화다.

_build_stage_engine() 이 Python 만세력 엔진(core/daewoon.py, core/sipsin.py)으로
이 '사실'(지배 간지·십신·십신군·직전군 대비 변화)을 계산한다. 이 함수는 배치 생성
스크립트(콤보 키 열거)와 런타임 조회(실제 개인의 조회 키 산출) 양쪽에서 재사용된다.
"""
from typing import Dict, Any, List, Tuple, Optional

from core.saju_base import calculate_saju
from core.sipsin import calculate_sipsin, sipsin_group
from domains.lifelong.content_db import lookup_base, lookup_stage
from shared.public import person_summary

CONTENT_TYPE = "lifelong_fortune"

# (키, 시작나이, 끝나이(포함), 고정 라벨) — AI 가 만들지 않고 Python 이 그대로 박아 넣는다.
_LIFE_STAGES: List[Tuple[str, int, int, str]] = [
    ("stage_1_19", 0, 19, "1~19세 학업/가정/교우"),
    ("stage_20_29", 20, 29, "20~29세 독립/방향설정"),
    ("stage_30_49", 30, 49, "30~49세 커리어/재물/배우자"),
    ("stage_50_69", 50, 69, "50~69세 축적/재정비"),
    ("stage_70_plus", 70, 130, "70세+ 역할전환/정리"),
]

DOMINANT_GROUPS: List[str] = ["비겁", "식상", "재성", "관성", "인성"]

# 십신군 × 생애단계 — 배치 생성 프롬프트를 구체화시키는 참고 사건결(그대로 베끼지 말고
# 자연스럽게 풀어 쓰게 유도하는 용도). scripts/generate_content_db.py 가 그대로 재사용한다.
SIPSIN_STAGE_HINTS: Dict[str, Dict[str, str]] = {
    "인성": {
        "stage_1_19": "부모의 보호와 학업적 조력, 스승 복이 따르는 시기",
        "stage_20_29": "전공·자격 심화, 윗사람의 인정과 추천을 받는 시기",
        "stage_30_49": "전문성 축적으로 신뢰를 얻는 시기",
        "stage_50_69": "지식과 경험을 나누는 멘토 역할이 커지는 시기",
        "stage_70_plus": "정신적으로 안정되고 존경받는 원로가 되는 시기",
    },
    "비겁": {
        "stage_1_19": "또래 관계 속에서 자기주장과 경쟁심이 커지는 시기",
        "stage_20_29": "독립을 시도하고 동료와 협업·경쟁하는 시기",
        "stage_30_49": "동업·파트너십이 확대되고 형제·동료 관계가 부각되는 시기",
        "stage_50_69": "인적 네트워크가 재편되며 협력의 결실을 보는 시기",
        "stage_70_plus": "오랜 인연·동년배와의 교류가 활발해지는 시기",
    },
    "식상": {
        "stage_1_19": "재능이 발현되고 자유로운 표현 욕구가 강한 시기",
        "stage_20_29": "사회에 진출해 실무 능력으로 성과를 내는 시기",
        "stage_30_49": "사업·창작 활동이 확장되며 활동 반경이 넓어지는 시기",
        "stage_50_69": "그동안의 성과가 드러나며 결실을 맺는 시기",
        "stage_70_plus": "취미·창작 활동으로 활력을 유지하는 시기",
    },
    "재성": {
        "stage_1_19": "현실 감각이 일찍 트이고 돈에 대한 개념이 자리잡는 시기",
        "stage_20_29": "첫 경제활동을 시작하며 재물 감각이 형성되는 시기",
        "stage_30_49": "자산 형성의 적기로 재물운이 오르는 시기",
        "stage_50_69": "자산을 관리·정리하며 현금흐름을 안정시키는 시기",
        "stage_70_plus": "자산을 정리·승계하며 노후자금을 관리하는 시기",
    },
    "관성": {
        "stage_1_19": "규율과 훈육 속에서 책임감이 형성되는 시기",
        "stage_20_29": "조직에 적응하며 취업·승진의 압박과 기회가 함께 오는 시기",
        "stage_30_49": "중책을 맡아 사회적 책임이 커지는 시기",
        "stage_50_69": "리더십을 발휘하며 명예·지위가 정점에 이르는 시기",
        "stage_70_plus": "역할에서 물러나 존경받는 자리로 전환되는 시기",
    },
}


def _pillar_segments(
    month_ganji: str, flow: List[Dict[str, Any]], daewoon_num: int
) -> List[Tuple[int, int, str]]:
    """나이 0부터 마지막 대운 끝까지 빈틈없이 이어지는 [(시작나이, 끝나이(제외), 간지), ...].

    대운이 시작되기 전(0~daewoon_num세)은 월주가 그 사람의 초년 기운을 대행한다고 본다.
    """
    segs: List[Tuple[int, int, str]] = []
    if daewoon_num > 0 and month_ganji:
        segs.append((0, daewoon_num, month_ganji))
    for item in flow:
        start = item.get("start_age")
        ganji = item.get("ganji")
        if isinstance(start, int) and ganji:
            segs.append((start, start + 10, ganji))
    return segs


def _dominant_ganji(segs: List[Tuple[int, int, str]], lo: int, hi: int) -> Optional[str]:
    """[lo, hi] 구간과 겹치는 햇수가 가장 큰 대운(또는 월주) 간지를 고른다."""
    best, best_overlap = None, -1
    for seg_start, seg_end, ganji in segs:
        overlap = min(seg_end, hi + 1) - max(seg_start, lo)
        if overlap > best_overlap:
            best_overlap, best = overlap, ganji
    return best


def _build_stage_engine(saju: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """생애단계별 지배 대운 간지·십신(그룹)·직전 단계 대비 변화 여부 — Python 이 계산하는 '사실'.

    배치 생성 스크립트의 콤보 키 열거와, 실제 요청의 조회 키 산출 양쪽에서 쓰인다.
    """
    day_master = saju.get("day_master", "")
    daewoon = saju.get("daewoon") or {}
    flow = daewoon.get("flow") or []
    daewoon_num = daewoon.get("daewoon_num", 1)
    month_ganji = saju.get("month_ganji", "")
    segs = _pillar_segments(month_ganji, flow, daewoon_num)

    out: Dict[str, Dict[str, Any]] = {}
    prev_group: Optional[str] = None
    for key, lo, hi, label in _LIFE_STAGES:
        ganji = _dominant_ganji(segs, lo, hi)
        gan = ganji[0] if ganji else day_master
        sipsin = calculate_sipsin(day_master, gan, is_gan=True)
        group = sipsin_group(sipsin)
        out[key] = {
            "stage_name": label,
            "age_range": [lo, None if hi >= 130 else hi],
            "dominant_ganji": ganji,
            "dominant_sipsin": sipsin,
            "dominant_sipsin_group": group,
            "hint": SIPSIN_STAGE_HINTS.get(group, {}).get(key, ""),
            "prev_sipsin_group": prev_group,
            "group_changed": prev_group is not None and group != prev_group,
        }
        prev_group = group
    return out


def _ilju(saju: Dict[str, Any]) -> str:
    return saju.get("day_ganji") or f"{saju.get('day_master', '')}{saju.get('day_branch', '')}"


def _fallback_stage(s: Dict[str, Any]) -> dict:
    hint = s["hint"] or "차분히 흐름을 따라가는 시기"
    return {
        "description": f"{s['stage_name']}는 {hint}입니다. 주어진 흐름에 맞춰 무리하지 않는 태도가 도움이 됩니다.",
        "daeun_influence": "이 시기의 기운은 관련된 선택에서 신중함이 필요하다는 신호로 작용합니다.",
        "previous_diff": (
            "직전 단계와 비슷한 흐름이 이어집니다." if not s["group_changed"]
            else "직전 단계와는 결이 다른 변화가 찾아오는 구간입니다."
        ),
    }


_FALLBACK_BASE = {
    "core_nature": {
        "personality": "안정적인 흐름 속에서 자기 페이스를 지키는 성향입니다.",
        "life_theme": "꾸준함으로 신뢰를 쌓아가는 인생",
    },
    "life_domains": {
        "wealth": {"style": "무리하지 않는 안정 지향형", "management_tip": "고정지출을 먼저 점검하세요."},
        "career": {"best_fit_work": "꾸준함이 필요한 전문 분야", "success_environment": "신뢰를 기반으로 한 조직"},
        "family": {"relation_characteristics": "가족과의 유대를 중요하게 여기는 편", "harmony_key": "정기적인 대화 시간"},
        "social": {"connection_style": "소수와 깊게 사귀는 편", "network_strategy": "기존 인연을 꾸준히 관리하기"},
    },
}


def analyze_lifelong_fortune(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
) -> Tuple[dict, bool]:
    """(결과 dict, is_fallback) 반환. 정적 DB 조회만 — Gemini 호출 없음."""
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)
    ilju = _ilju(saju)
    stages = _build_stage_engine(saju)

    base = lookup_base(ilju)
    is_fallback = base is None
    if base is None:
        base = _FALLBACK_BASE

    life_stages = {}
    for key, s in stages.items():
        entry = lookup_stage(ilju, key, s["dominant_sipsin_group"], s["prev_sipsin_group"])
        if entry is None:
            is_fallback = True
            entry = _fallback_stage(s)
        life_stages[key] = {
            "stage_name": s["stage_name"],
            "age_range": s["age_range"],
            "description": entry.get("description", ""),
            "daeun_influence": entry.get("daeun_influence", ""),
            "previous_diff": entry.get("previous_diff", ""),
        }

    data = {
        "core_nature": base.get("core_nature", _FALLBACK_BASE["core_nature"]),
        "life_stages": life_stages,
        "life_domains": base.get("life_domains", _FALLBACK_BASE["life_domains"]),
    }

    return {
        "content_type": CONTENT_TYPE,
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, is_fallback
