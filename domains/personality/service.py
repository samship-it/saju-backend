"""나의 성격 / 나의 적성 — 원국(원판) 중심. 운(運) 아님. 점수 없음."""
from typing import Dict, Any, Tuple

from core.saju_base import calculate_saju
from shared.ai_client import call_gemini_json
from shared.persona_map import persona_prompt
from shared.saju_prompt import engine_block
from shared.fortune_cache import get_or_create
from shared.public import person_summary
from shared.text_format import paragraphize

_SYSTEM = (
    "당신은 2030 세대를 위한 사주 앱 화자입니다. 제공된 원국 데이터만 근거로 성격/적성을 설명합니다. "
    "MBTI식 나열이 아니라 구체적인 행동 예시를 넣습니다. 사주 용어는 노출하지 않습니다. 유효한 JSON 만 출력합니다."
)


def _saju(year, month, day, hour, minute, gender, is_lunar):
    return calculate_saju(year, month, day, hour, minute, gender=gender, is_lunar=is_lunar)


def _character_fallback() -> dict:
    return {
        "base_nature": "자기 기준이 뚜렷하고, 하고 싶은 일이 생기면 스스로 방향을 정해 움직이는 편입니다. 남이 정해준 길보다 내가 납득한 길에서 힘이 납니다. 다만 페이스가 빠르다 보니 주변이 따라오는 속도를 놓칠 때가 있어요.",
        "strengths": "핵심을 빨리 파악하고, 한번 정한 건 끝까지 밀고 갑니다. 위기 상황에서 오히려 침착해지는 유형이라, 급한 일이 생겼을 때 사람들이 당신을 찾게 됩니다.",
        "weaknesses": "내 판단에 확신이 강해서 다른 의견을 늦게 받아들입니다. 성과에 몰입하다 휴식과 감정 관리를 뒤로 미루는 습관도 있어요.",
        "supplement": "결정 전에 신뢰하는 한 사람에게 먼저 말해보는 루틴, 그리고 주 1회는 아무 목적 없는 휴식을 의무적으로 넣어보세요. 부족한 결을 채워줍니다.",
        "relationships": "말이 앞서기보다 행동으로 챙기는 스타일이라 가까운 사람에겐 신뢰가 두텁습니다. 대신 표현이 담백해서 처음엔 차갑게 느껴질 수 있어요. 먼저 안부를 묻는 연습이 관계를 넓혀줍니다.",
        "work_style": "명확한 목표와 자율성이 주어질 때 최고의 성과를 냅니다. 마이크로매니징을 받으면 급격히 동력이 떨어져요. 스스로 마감과 우선순위를 설계하는 환경이 잘 맞습니다.",
    }


def _aptitude_fallback() -> dict:
    return {
        "fit_task": "기획하고 구조를 짜는 일, 문제를 분해해 해결책을 만드는 일에 강합니다. 반복 업무보다 새로 설계하는 업무에서 몰입도가 올라갑니다.",
        "fit_field": "전략/기획, 전문 기술·연구, 1인 사업이나 전문직처럼 결과가 명확히 드러나는 분야가 잘 맞습니다.",
        "good_env": "목표만 주고 방법은 맡기는 조직, 성과를 투명하게 인정하는 문화에서 능력이 커집니다.",
        "org_style": "수평적이고 실무 중심 팀에서 자기 몫을 확실히 하는 스타일. 형식적인 보고 라인이 길면 답답해합니다.",
        "tiring_env": "잦은 방향 전환, 불명확한 지시, 감정 소모가 큰 인간관계가 겹치면 빠르게 지칩니다.",
        "favorable_direction": "속도를 조금 늦추고 주변 피드백을 자산으로 삼을 때, 그리고 내 강점이 드러나는 전문 영역을 깊게 팔 때 가장 유리합니다.",
    }


def analyze_character(year, month, day, hour=None, minute=0, gender="female", is_lunar=False) -> Tuple[dict, bool]:
    saju = _saju(year, month, day, hour, minute, gender, is_lunar)

    def _gen():
        prompt = f"""{persona_prompt(saju.get('day_master'), saju.get('day_branch'))}

{engine_block(saju, domains=[])}

[규칙] 6개 영역을 하나의 재미있는 사람 설명으로 연결. 각 영역 5줄 이상, 구체적 행동 예시 포함. 사주 용어 금지.

[출력 JSON — 이 구조만]
{{
  "base_nature": "기본 성향 (일간+오행+십신+격국 반영)",
  "strengths": "성격적 강점 (강한 십신/오행 + 용희신 반영)",
  "weaknesses": "성격적 약점 (과다/부족 오행 + 십신 불균형 반영)",
  "supplement": "보완 방법 (부족한 요소 + 용희신 반영)",
  "relationships": "인간관계에서의 모습 (비겁+식상+관성+인성 반영)",
  "work_style": "일할 때 성향 (식상+관성+재성+인성 반영)"
}}"""
        ai, is_fb = call_gemini_json(prompt, _character_fallback(), system_instruction=_SYSTEM)
        data = _character_fallback() if is_fb else ai
        return {
            "content_type": "나의 성격",
            "saju_info": person_summary(saju),
            "report": {k: paragraphize(str(data.get(k, ""))) for k in _character_fallback()},
        }, is_fb

    payload = {"y": year, "m": month, "d": day, "h": hour, "min": minute, "g": gender, "lunar": is_lunar}
    data, is_fb, _ = get_or_create("personality_character", payload, _gen)
    return data, is_fb


def analyze_aptitude(year, month, day, hour=None, minute=0, gender="female", is_lunar=False) -> Tuple[dict, bool]:
    saju = _saju(year, month, day, hour, minute, gender, is_lunar)

    def _gen():
        prompt = f"""{persona_prompt(saju.get('day_master'), saju.get('day_branch'))}

{engine_block(saju, domains=[])}

[규칙] 직업 목록만 나열하지 말고 '왜 맞는지' 설명. 각 항목 5줄 이상. 사주 용어 금지.

[출력 JSON — 이 구조만]
{{
  "fit_task": "잘 맞는 업무 (십신 구조 반영)",
  "fit_field": "잘 맞는 분야 (오행+십신 반영)",
  "good_env": "좋은 환경 (관성/인성/식상 반영)",
  "org_style": "조직 스타일 (비겁/관성 반영)",
  "tiring_env": "피로한 환경 (과도하게 작용하는 요소 반영)",
  "favorable_direction": "적성상 유리한 방향 (전체 원국 + 용희신 반영)"
}}"""
        ai, is_fb = call_gemini_json(prompt, _aptitude_fallback(), system_instruction=_SYSTEM)
        data = _aptitude_fallback() if is_fb else ai
        return {
            "content_type": "나의 적성",
            "saju_info": person_summary(saju),
            "report": {k: paragraphize(str(data.get(k, ""))) for k in _aptitude_fallback()},
        }, is_fb

    payload = {"y": year, "m": month, "d": day, "h": hour, "min": minute, "g": gender, "lunar": is_lunar}
    data, is_fb, _ = get_or_create("personality_aptitude", payload, _gen)
    return data, is_fb
