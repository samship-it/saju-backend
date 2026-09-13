"""평생운세 (LIFELONG_FORTUNE, 250P).

daily/yearly 는 '오늘'·'올해' 처럼 특정 시점을 다루지만, 여기는 한 사람의 원국 +
평생 대운 흐름 전체를 다룬다. 5개 생애단계(1~19/20~29/30~49/50~69/70+) 각각을
지배하는 대운(또는 대운 시작 전이면 월주)의 십신(五分類: 비겁/식상/재성/관성/인성)을
Python 이 계산해서 '사실'로 넘기고, AI 는 그 사실에만 근거해 서술한다
(원칙 — Python 계산값만 근거로 사용, 사주 용어는 출력에 노출하지 않는다).
"""
import re
from typing import Dict, Any, List, Tuple, Optional

from core.saju_base import calculate_saju
from core.sipsin import calculate_sipsin, sipsin_group
from shared.ai_client import call_gemini_json
from shared.persona_map import persona_prompt
from shared.public import person_summary

CONTENT_TYPE = "lifelong_fortune"

_SYSTEM = (
    "당신은 사람의 평생 사주 흐름을 해석하는 인생 코치 화자입니다. 제공된 사주 원국·대운 데이터만 "
    "근거로 사용하고, 사주 전문 용어(십신 이름·합충형파해·용신·격국명 등)는 절대 그대로 노출하지 "
    "말고 구체적인 사건·행동 수준의 일상 언어로 풀어 씁니다. 유효한 JSON 만 출력합니다."
)

# (키, 시작나이, 끝나이(포함), 고정 라벨) — AI 가 만들지 않고 Python 이 그대로 박아 넣는다.
_LIFE_STAGES: List[Tuple[str, int, int, str]] = [
    ("stage_1_19", 0, 19, "1~19세 학업/가정/교우"),
    ("stage_20_29", 20, 29, "20~29세 독립/방향설정"),
    ("stage_30_49", 30, 49, "30~49세 커리어/재물/배우자"),
    ("stage_50_69", 50, 69, "50~69세 축적/재정비"),
    ("stage_70_plus", 70, 130, "70세+ 역할전환/정리"),
]

# 십신군 × 생애단계 — AI 서술을 구체화시키는 참고 사건결(그대로 베끼지 말고 자연스럽게 풀어 쓰게 유도).
_SIPSIN_STAGE_HINTS: Dict[str, Dict[str, str]] = {
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
    """생애단계별 지배 대운 간지·십신(그룹)·직전 단계 대비 변화 여부 — Python 이 계산하는 '사실'."""
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
            "hint": _SIPSIN_STAGE_HINTS.get(group, {}).get(key, ""),
            "prev_sipsin_group": prev_group,
            "group_changed": prev_group is not None and group != prev_group,
        }
        prev_group = group
    return out


def _stage_block(stages: Dict[str, Dict[str, Any]]) -> str:
    lines = ["[생애단계별 지배 기운 — Python 만세력 엔진 산출값. 이 사실만 근거로 서술할 것]"]
    for key, s in stages.items():
        age_hi = s["age_range"][1]
        prev = f"직전 단계 기운: {s['prev_sipsin_group']}" if s["prev_sipsin_group"] else "직전 단계 없음(첫 구간)"
        changed = "이전과 다른 기운으로 전환됨" if s["group_changed"] else "이전과 같은 흐름이 이어짐"
        lines.append(
            f"- {key} ({s['stage_name']}, 만 {s['age_range'][0]}~{age_hi if age_hi else '그 이상'}세): "
            f"지배 기운={s['dominant_sipsin_group']}({s['dominant_sipsin']}) · 참고 사건결={s['hint']} · "
            f"{prev} · {changed}"
        )
    return "\n".join(lines)


def _fallback(stages: Dict[str, Dict[str, Any]]) -> dict:
    def _f(key: str) -> dict:
        s = stages[key]
        hint = s["hint"] or "차분히 흐름을 따라가는 시기"
        return {
            "description": f"{s['stage_name']}는 {hint}입니다. 주어진 흐름에 맞춰 무리하지 않는 태도가 도움이 됩니다.",
            "daeun_influence": "이 시기의 기운은 관련된 선택에서 신중함이 필요하다는 신호로 작용합니다.",
            "previous_diff": (
                "직전 단계와 비슷한 흐름이 이어집니다." if not s["group_changed"]
                else "직전 단계와는 결이 다른 변화가 찾아오는 구간입니다."
            ),
        }

    return {
        "core_nature": {
            "personality": "안정적인 흐름 속에서 자기 페이스를 지키는 성향입니다.",
            "life_theme": "꾸준함으로 신뢰를 쌓아가는 인생",
        },
        "life_stages": {key: _f(key) for key in stages},
        "life_domains": {
            "wealth": {"style": "무리하지 않는 안정 지향형", "management_tip": "고정지출을 먼저 점검하세요."},
            "career": {"best_fit_work": "꾸준함이 필요한 전문 분야", "success_environment": "신뢰를 기반으로 한 조직"},
            "family": {"relation_characteristics": "가족과의 유대를 중요하게 여기는 편", "harmony_key": "정기적인 대화 시간"},
            "social": {"connection_style": "소수와 깊게 사귀는 편", "network_strategy": "기존 인연을 꾸준히 관리하기"},
        },
    }


# previous_diff 등에서 "관성 중심의 흐름으로" 처럼 사주 용어가 그대로 새는 경우가 있어(검증 중 실측),
# 용어(+ 뒤따르는 '중심'/'중심으로'/'중심의')만 제거하는 안전망. 문장 흐름은 자연스럽게 유지된다.
_JARGON_TERMS = [
    "비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인",
    "비겁", "식상", "재성", "관성", "인성", "격국", "용신", "십신", "신강", "신약",
]
_JARGON_RE = re.compile(r"(?:" + "|".join(_JARGON_TERMS) + r")\s*(?:중심(?:으로|의)?)?")


def _strip_jargon(text: str) -> str:
    if not text:
        return text
    cleaned = _JARGON_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _s(v: Any) -> str:
    return _strip_jargon(str(v)) if isinstance(v, str) else ""


def _shape(ai: dict, stages: Dict[str, Dict[str, Any]]) -> dict:
    core = ai.get("core_nature") or {}
    domains_ai = ai.get("life_domains") or {}
    ai_stages = ai.get("life_stages") or {}

    def _domain(name: str, f1: str, f2: str) -> dict:
        d = domains_ai.get(name) or {}
        return {f1: _s(d.get(f1)), f2: _s(d.get(f2))}

    out_stages = {}
    for key, s in stages.items():
        st = ai_stages.get(key) or {}
        out_stages[key] = {
            "stage_name": s["stage_name"],
            "age_range": s["age_range"],
            "description": _s(st.get("description")),
            "daeun_influence": _s(st.get("daeun_influence")),
            "previous_diff": _s(st.get("previous_diff")),
        }

    return {
        "core_nature": {
            "personality": _s(core.get("personality")),
            "life_theme": _s(core.get("life_theme")),
        },
        "life_stages": out_stages,
        "life_domains": {
            "wealth": _domain("wealth", "style", "management_tip"),
            "career": _domain("career", "best_fit_work", "success_environment"),
            "family": _domain("family", "relation_characteristics", "harmony_key"),
            "social": _domain("social", "connection_style", "network_strategy"),
        },
    }


def analyze_lifelong_fortune(
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
) -> Tuple[dict, bool]:
    saju = calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)
    stages = _build_stage_engine(saju)

    prompt = f"""{persona_prompt(saju.get('day_master'), saju.get('day_branch'))}

[원국 요약]
- 일간/일지: {saju.get('day_master')}({saju.get('day_master_elem')}) / {saju.get('day_branch')}
- 원국 사주: 년 {saju.get('year_ganji')} · 월 {saju.get('month_ganji')} · 일 {saju.get('day_ganji')} · 시 {saju.get('time_ganji') or '미상'}
- 일간 강약: {(saju.get('strength') or {}).get('verdict')}
- 격국: {(saju.get('gyeokguk') or {}).get('name')}

{_stage_block(stages)}

[작성 규칙]
- core_nature.personality: 원국(일간/오행/격국/강약)에 근거한 타고난 본질과 행동 패턴. 3~5문장.
- core_nature.life_theme: 인생을 관통하는 핵심 대주제를 한 문장(15~30자)으로.
- life_stages 의 각 단계는 반드시 위 [생애단계별 지배 기운] 데이터의 '지배 기운'과 '참고 사건결'을
  구체적인 사건·행동으로 풀어서 씁니다. 예: 지배 기운이 인성이면 "학업적 성과와 부모의 집중 조력을
  받는 시기"처럼 실제 사건 수준으로 구체화합니다. 범용적이고 추상적인 문장은 금지합니다.
  - description: 그 단계의 전반적 흐름과 태도 (4~6문장)
  - daeun_influence: 지배 기운이 구체적으로 어떤 사건/선택에 영향을 주는지 (3~5문장)
  - previous_diff: 직전 단계와 비교해 무엇이 달라지는지, 그 심리적/환경적 변화 계기를 설득력 있게
    (3~5문장). 반드시 채웁니다(첫 구간이면 "이전 단계 없이 시작되는 구간"이라는 취지로).
- life_domains 는 원국 전체(오행/십신 분포) 기준의 평생 성향입니다(특정 나이대에 국한하지 않음).
- 사주 전문 용어(십신 이름·합충형파해·용신·격국명 등)는 절대 그대로 쓰지 말고 일상 언어로 풀어 쓸 것.
- 모든 문장은 친근한 존댓말('~해요/~예요/~입니다' 등)로만 씁니다. 반말은 단 한 번도 쓰지 않습니다.

[출력 JSON — 이 구조와 키를 정확히 그대로, 이 객체 하나만 출력]
{{
  "core_nature": {{"personality": "...", "life_theme": "..."}},
  "life_stages": {{
    "stage_1_19": {{"description": "...", "daeun_influence": "...", "previous_diff": "..."}},
    "stage_20_29": {{"description": "...", "daeun_influence": "...", "previous_diff": "..."}},
    "stage_30_49": {{"description": "...", "daeun_influence": "...", "previous_diff": "..."}},
    "stage_50_69": {{"description": "...", "daeun_influence": "...", "previous_diff": "..."}},
    "stage_70_plus": {{"description": "...", "daeun_influence": "...", "previous_diff": "..."}}
  }},
  "life_domains": {{
    "wealth": {{"style": "...", "management_tip": "..."}},
    "career": {{"best_fit_work": "...", "success_environment": "..."}},
    "family": {{"relation_characteristics": "...", "harmony_key": "..."}},
    "social": {{"connection_style": "...", "network_strategy": "..."}}
  }}
}}"""

    ai, is_fallback = call_gemini_json(prompt, _fallback(stages), system_instruction=_SYSTEM)
    data = _shape(_fallback(stages) if is_fallback else ai, stages)
    return {
        "content_type": CONTENT_TYPE,
        "birth_time_known": saju.get("birth_time_known"),
        "day_master": saju.get("day_master"),
        "saju_info": person_summary(saju),
        "data": data,
    }, is_fallback
