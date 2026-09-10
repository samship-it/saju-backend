"""사전 생성 콘텐츠 DB 빌더.

런타임 Gemini 호출을 없애기 위해, 가능한 모든 입력 조합을 미리 순회하며
Gemini 로 콘텐츠를 생성해 JSON 파일로 저장한다.

────────────────────────────────────────────────────────────────────────
[DAILY 도메인]  (--domain daily, 기본값)
  - 60개 일주(내 일주) × 60개 일진(오늘 일진) = 3,600개 조합
  - 결과: domains/daily/data/daily_db.json
  - 키: "<일주 간지>_<일진 간지>"  예) "戊辰_乙巳"

사용 예:
  # 8개만 샘플 생성 후 확인
  python scripts/generate_content_db.py --domain daily --limit 8

  # 전체 생성 (이미 있는 키는 건너뜀 = 체크포인트/이어하기)
  python scripts/generate_content_db.py --domain daily

  # 특정 조합만 (디버그)
  python scripts/generate_content_db.py --domain daily --only 戊辰_乙巳

  # 강제 재생성
  python scripts/generate_content_db.py --domain daily --overwrite --limit 3

키 × 모델 순환 (무료 등급 일일 한도 우회):
  무료 등급 PerDay 한도는 (프로젝트 × 모델)별로 따로 잡힌다. 그래서 이 스크립트는
  (API 키 N개) × (모델 M개) = N·M 개의 슬롯을 순환한다.
    - 한 슬롯이 PerDay 로 막히면 → 그 슬롯만 제외하고 다음 슬롯으로 (멈춤 없음)
    - 키가 무효면 → 그 키의 모든 슬롯 제외
    - 모델이 404 면 → 그 모델의 모든 슬롯 제외
    - 분당(PerMinute) 429 면 → 제외 없이 다음 슬롯으로 회전, 다 돌면 잠깐 대기
  모든 슬롯이 소진되면 안전하게 중단하고(항목마다 체크포인트 저장됨),
  한도 리셋(태평양시 자정) 후 같은 명령으로 이어서 진행한다.
  생성된 각 항목에는 어떤 모델이 만들었는지 "_model" 키가 기록된다.

환경변수:
  - GEMINI_API_KEY (필수) — 단일 키
  - GEMINI_API_KEY_1, GEMINI_API_KEY_2, ... (선택) — 추가 키. 번호 순서대로 순환.
  - GEMINI_MODEL_NAME (선택) — 순환 목록의 맨 앞(최우선) 모델. 기본 config 값.
옵션:
  --model NAME        이 모델 하나만 사용 (모델 순환 끔)
  --no-model-rotate   운영 모델 하나만 사용 (키 순환은 유지)
────────────────────────────────────────────────────────────────────────
"""
import argparse
import json
import os
import queue as _queue
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

# Windows 콘솔(cp949 등)에서도 ✓/✗/한자 출력이 깨지거나 죽지 않도록 UTF-8 강제
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from core.constants import (  # noqa: E402
    GAN, JI, YUKHAP, CHUNG, PA, HAE, SANGHYEONG, SELF_HYEONG,
    GAN_ELEM, JI_ELEM, JIJANGGAN, SHENG, KE,
)
from core.sipsin import calculate_sipsin, sipsin_group  # noqa: E402
from shared.persona_map import persona_prompt, GAN_PERSONA, JI_PERSONA  # noqa: E402
from shared.ai_client import _extract_json as _extract_json_strict, _is_rate_limited, _retry_delay_sec  # noqa: E402


def _extract_json(text: str) -> dict:
    """관대한 JSON 파서.

    일부 모델(gemini-3.5-flash 등)은 response_mime_type=application/json 이어도
    JSON 뒤에 설명/개행을 덧붙이곤 한다. 첫 번째 완전한 { ... } 객체만 취한다.
    """
    try:
        return _extract_json_strict(text)
    except Exception:
        pass
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
        s = s.strip()
    start = s.find("{")
    if start == -1:
        raise ValueError("JSON 객체 없음")
    obj, _end = json.JSONDecoder().raw_decode(s[start:])
    if not isinstance(obj, dict):
        raise ValueError("최상위가 객체가 아님")
    return obj

try:
    import google.generativeai as genai
    import google.ai.generativelanguage as glm
except Exception as e:  # pragma: no cover
    print(f"google-generativeai 임포트 실패: {e}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────── 공통

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DAILY_DB_PATH = os.path.join(_ROOT, "domains", "daily", "data", "daily_db.json")
PERSONALITY_DB_PATH = os.path.join(_ROOT, "domains", "personality", "data", "personality_db.json")

_SYSTEM = (
    "당신은 2030 세대를 위한 사주 운세 앱의 화자입니다. "
    "제공된 '내 일주'와 '오늘 일진' 관계 데이터만 근거로 오늘의 운세를 생성합니다. "
    "말투는 예외 없이 '친근한 존댓말'로만 씁니다. 모든 문장은 '~해요', '~예요', '~입니다', "
    "'~보세요', '~됩니다' 같은 존댓말 어미로 끝냅니다. '~해', '~야', '~봐', '~자', '~거야' 같은 "
    "반말 어미는 단 한 번도 쓰지 않습니다. "
    "반드시 아래에 지정된 키를 하나도 빠짐없이 포함한 유효한 JSON 하나만 출력하고, "
    "Markdown 펜스(```)나 그 밖의 설명 문장은 절대 쓰지 않습니다."
)

_PERSONALITY_SYSTEM = (
    "당신은 2030 세대를 위한 사주 앱 화자입니다. 제공된 '일주(일간·일지)' 데이터만 근거로 "
    "그 사람의 타고난 성격과 적성을 설명합니다. MBTI식 형용사 나열이 아니라 구체적인 행동·상황 "
    "예시로 씁니다. 사주 용어(십신·오행·격국·용신 등)는 절대 노출하지 않고 태도로만 드러냅니다. "
    "말투는 예외 없이 '친근한 존댓말'로만 씁니다('~해요/~예요/~입니다/~보세요/~편입니다'). "
    "반말('~해', '~야', '~지', '~거야')은 한 번도 쓰지 않습니다. "
    "각 값은 번호·순번·목록 기호(1., 1), 1/6, [1], ①, 문장 앞의 '-' 등)를 붙이지 않고 서술형 문장으로만 씁니다. "
    "지정된 키를 하나도 빠짐없이 포함한 유효한 JSON 하나만 출력하고, Markdown 펜스나 설명 문장은 쓰지 않습니다."
)


def sixty_gapja() -> List[str]:
    """60갑자(한자) 리스트. index i -> GAN[i%10] + JI[i%12]."""
    return [f"{GAN[i % 10]}{JI[i % 12]}" for i in range(60)]


class DailyQuotaExceeded(Exception):
    """무료 등급 '하루 한도(PerDay)' 초과 — 이 키로는 오늘 재시도 불가, 키를 죽이고 전환."""


class InvalidApiKey(Exception):
    """API 키가 무효하거나 권한이 없음 — 이 키로는 재시도 불가, 키를 죽이고 전환."""


class ModelUnavailable(Exception):
    """이 모델을 이 키로 쓸 수 없음(404 등) — 해당 모델의 모든 슬롯 제외."""


class RateLimited(Exception):
    """단기 창(분당 등) 429 — 키를 죽이지 말고 다른 키로 돌리거나 잠시 뒤 재시도."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class CreditsDepleted(Exception):
    """유료 선불(prepay) 크레딧 소진 — 키/모델 전환으로 해결 안 됨(같은 프로젝트 결제 문제).
    재시도·회전 없이 즉시 전체 중단해야 한다(안 그러면 RateLimited 로 오분류돼
    영원히 재시도만 반복하며 리소스를 낭비한다)."""


def _is_credits_depleted(err: Exception) -> bool:
    low = str(err).lower()
    return "prepayment credits" in low or "prepay" in low


def _is_daily_quota(err: Exception) -> bool:
    """'하루(PerDay)' 한도 소진인지.

    Gemini 429 에는 하루 한도여도 무의미한 retry_delay(예: 4s)가 붙어 오므로
    retry_delay 유무가 아니라 quota_id/metric 의 'PerDay' 표기로 판정한다.
    분당 한도는 'PerMinute' 로 오므로 자연히 구분된다.
    """
    low = str(err).lower()
    return "perday" in low or "per day" in low or "requests per day" in low


def _is_invalid_key(err: Exception) -> bool:
    t = str(err)
    low = t.lower()
    return (
        "API_KEY_INVALID" in t
        or "api key not valid" in low
        or "invalid api key" in low
        or ("PERMISSION_DENIED" in t and "quota" not in low)
        or ("400" in t and "api key" in low)
    )


def _is_model_unavailable(err: Exception) -> bool:
    t = str(err)
    low = t.lower()
    return (
        "404" in t
        or "was not found" in low
        or "no longer available" in low
        or "not supported for generateContent" in t
        or "NotFound" in type(err).__name__
    )


# 무료 등급에서 텍스트 JSON 생성이 되는 모델들. PerDay 한도는 (프로젝트 × 모델)별로
# 따로 잡히므로, 한 모델이 소진되면 다음 모델로 넘어가 계속 생성한다. 맨 앞이 최우선.
#   - gemini-2.5-flash       : 이 API 키들에선 404(신규 사용자 불가) → 제외
#   - gemini-flash-latest    : 별칭이 현재 무거운 모델로 연결돼 호출당 2~3분/행이 걸림 → 제외
#   - gemini-2.5-flash-lite  : 무료 하루 20회뿐 → 기본 목록에서 제외(--model 로 강제만 가능)
# 비-lite flash(3.5/3.6…)는 호출당 ~12s, lite 계열은 ~5s.
DEFAULT_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
]

# ── 배치 생성 모드 전용 설정 ──────────────────────────────────────
# 조합 1개당 1회 호출 대신, 1회 호출로 N개 조합을 생성한다(--batch, 권장 10).
# 호출 수를 ~1/10 로 줄여 (1) 유료 시 비용, (2) 무료 등급 시 일일 요청 한도(RPD)를 아낀다.
# 모델: gemini-3.5-flash-lite 우선.
#   - 새로 발급한 무료 프로젝트에서는 gemini-2.5-flash-lite / 2.5-flash 가 404
#     ("no longer available to new users") → 2.5 계열은 목록에서 제외.
#   - 3.5-flash-lite 가 Google 이 안내하는 2.5-flash-lite 공식 후속. lite 계열이라 저렴/빠름.
#   - 404/사용불가 시 아래 순서로 폴백.
DAILY_BATCH_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
]
# 배치 응답은 조합 N개분 JSON이라 길다. lite 계열 기본 출력 상한(8192)으로는 잘리므로 크게 잡는다.
DAILY_BATCH_MAX_OUTPUT_TOKENS = 65536


def load_api_keys() -> List[str]:
    """GEMINI_API_KEY 와 GEMINI_API_KEY_<n> 을 순서대로 모아 중복 제거한 목록."""
    keys: List[str] = []
    seen = set()

    def _add(v: Optional[str]) -> None:
        v = (v or "").strip()
        if v and v not in seen:
            seen.add(v)
            keys.append(v)

    _add(os.environ.get("GEMINI_API_KEY"))
    numbered = []
    for name, val in os.environ.items():
        m = re.fullmatch(r"GEMINI_API_KEY_(\d+)", name)
        if m:
            numbered.append((int(m.group(1)), val))
    for _, val in sorted(numbered):
        _add(val)
    return keys


class Rotator:
    """(API 키 × 모델) 슬롯을 순환한다.

    - 슬롯 순서: key0×model0, key0×model1, ... (키를 오래 유지하며 모델을 먼저 바꾼다)
    - PerDay 소진: 그 슬롯 하나만 죽인다 (같은 키의 다른 모델은 살아있음).
    - 키 무효: 그 키의 모든 슬롯을 죽인다.
    - 모델 사용불가(404): 그 모델의 모든 슬롯을 죽인다.
    - 단기 429: 죽이지 않고 다음 살아있는 슬롯으로 회전.
    """

    def __init__(self, keys: List[str], models: List[str]):
        self.keys = list(keys)
        self.models = list(models)
        self.slots: List[Tuple[int, int]] = [
            (ki, mi) for ki in range(len(keys)) for mi in range(len(models))
        ]
        self._i = 0
        self._dead = set()

    def __len__(self) -> int:
        return len(self.slots)

    @property
    def alive_count(self) -> int:
        return len(self.slots) - len(self._dead)

    @property
    def _cur(self) -> Tuple[int, int]:
        return self.slots[self._i]

    @property
    def current_key(self) -> str:
        return self.keys[self._cur[0]]

    @property
    def current_model(self) -> str:
        return self.models[self._cur[1]]

    @property
    def label(self) -> str:
        ki, mi = self._cur
        return f"{self.models[mi]} · 키#{ki + 1}/{len(self.keys)}"

    def _alive_keys(self) -> int:
        return len({self.slots[j][0] for j in range(len(self.slots)) if j not in self._dead})

    def kill_current(self) -> None:
        self._dead.add(self._i)

    def kill_current_key(self) -> None:
        ki = self._cur[0]
        for j, (k, _) in enumerate(self.slots):
            if k == ki:
                self._dead.add(j)

    def kill_current_model(self) -> None:
        mi = self._cur[1]
        for j, (_, m) in enumerate(self.slots):
            if m == mi:
                self._dead.add(j)

    def advance(self) -> bool:
        """살아있는 다음 슬롯으로 이동. 남은 슬롯이 없으면 False."""
        for step in range(1, len(self.slots) + 1):
            nxt = (self._i + step) % len(self.slots)
            if nxt not in self._dead:
                self._i = nxt
                return True
        return False

    def status(self) -> str:
        return (f"살아있는 슬롯 {self.alive_count}/{len(self.slots)} "
                f"(키 {self._alive_keys()}/{len(self.keys)})")


_SENT_SPLIT = re.compile(r"[.!?…\n]+")
_JONDAE_END = re.compile(r"(?:요|죠|음|까|오|쥬)['\"”’]?$")
_BANMAL_END = re.compile(r"(?:거야|잖아|더라|구나|는데|은데|[가-힣](?:야|해|봐|줘|어|아|지|자))['\"”’]?$")

# 번호·순번·목록 기호 제거용. 자연어 숫자("5분", "100점", "웹3", "9시부터 6시")는 건드리지 않도록
# '열거 문맥'(문두 / 개행 뒤 / 문장부호 뒤 / 공백으로 둘러싸인 괄호숫자)에서만 매치한다.
_ENUM_MARKERS = [
    re.compile(r"(?m)^[ \t]*[\(\[]?\s*\d{1,2}\s*/\s*\d{1,2}\s*[\)\]]?[.):]?[ \t]+"),  # "1/6 ", "(1/6) "
    re.compile(r"(?m)^[ \t]*[\(\[]?\s*\d{1,2}\s*[\)\].:]\s+"),                          # "1. ", "1) ", "(1) ", "[1] ", "1: "
    re.compile(r"(?m)^[ \t]*[①-⑳➀-➉❶-❿]\s*[.):]?\s+"),                                   # "① ", "①. "
    re.compile(r"(?<=[\s。.!?…])[\(\[]\s*\d{1,2}\s*[\)\]]\s*"),                          # 문장 중간의 " (1) " / " [2] "
    re.compile(r"(?<=[\s。.!?…])\d{1,2}\s*/\s*\d{1,2}(?=[\s:)]| )"),                      # 문장 중간의 " 1/6 "
    re.compile(r"[①-⑳➀-➉❶-❿]"),                                                          # 남은 동그라미 숫자
]


def strip_enumeration(s: Any) -> Any:
    """열거 번호 표기(1. / 1) / 1/6 / [1] / ① 등)를 제거하고 공백을 정리한다."""
    if not isinstance(s, str):
        return s
    out = s
    for rx in _ENUM_MARKERS:
        out = rx.sub(" ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


# 모델이 가끔 만드는 글자 깨짐 오타. (검수에서 발견되는 대로 추가)
_TYPO_FIXUPS = {
    "천섀기": "천천히",
    "여미까": "여기니까",
}
# '타고난 흐름' 설명에 부적합한 시점 단어 제거(relationship 등에서 strip_time_words=True 로 사용).
_TIME_WORD_LEAD = re.compile(r"(?:^|(?<=[.!?…]\s)|(?<=[\s,]))(?:오늘|요즘)[,\s]+")


def apply_text_fixups(s: Any, strip_time_words: bool = False) -> Any:
    """오타 교정(+선택적으로 시점 단어 제거). strip_enumeration 과 함께 쓴다."""
    if not isinstance(s, str):
        return s
    for bad, good in _TYPO_FIXUPS.items():
        if bad in s:
            s = s.replace(bad, good)
    if strip_time_words:
        s = s.replace("오늘이라도", "지금이라도").replace("오늘 당장", "당장")
        s = _TIME_WORD_LEAD.sub("", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _has_banmal(entry: Dict[str, Any]) -> bool:
    """문장 종결부만 검사해 반말 어미를 대략 탐지 (경고용, 저장은 막지 않음)."""
    parts = list((entry.get("summary") or {}).values()) + [entry.get("recommended_action", "")]
    hits = 0
    for blob in parts:
        for sent in _SENT_SPLIT.split(str(blob)):
            s = sent.strip().strip("\"'“”‘’()[]")
            if len(s) < 3 or _JONDAE_END.search(s):
                continue
            if _BANMAL_END.search(s):
                hits += 1
    return hits >= 2


def branch_relation(my_branch: str, iljin_branch: str) -> str:
    """내 일지 vs 오늘 일진 지지 관계(합/충/파/해/형)를 한국어로."""
    if not my_branch or not iljin_branch:
        return "무관"
    pair = frozenset((my_branch, iljin_branch))
    if my_branch == iljin_branch:
        return "복음(같은 지지)" + (" · 자형" if my_branch in SELF_HYEONG else "")
    for table, label in ((YUKHAP, "육합(협력·인연)"), (CHUNG, "충(충돌·이동)"),
                         (PA, "파(어긋남)"), (HAE, "해(방해·구설)"), (SANGHYEONG, "형(마찰·조정)")):
        if pair in table:
            return label
    return "무관"


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# ─────────────────────────────────────────────────────────── DAILY

def daily_prompt(day_ganji: str, iljin_ganji: str) -> str:
    dm, db = day_ganji[0], day_ganji[1]
    ig, ib = iljin_ganji[0], iljin_ganji[1]
    sipsin_gan = calculate_sipsin(dm, ig, is_gan=True)
    sipsin_ji = calculate_sipsin(dm, ib, is_gan=False)
    rel = branch_relation(db, ib)

    return f"""{persona_prompt(dm, db)}

[오늘의 일진 데이터 — 이 값만 근거로 사용]
- 내 일주(성격/말투 기준): {day_ganji}
- 오늘 일진: {iljin_ganji}
- 오늘 일진의 천간({ig})이 나에게 주는 기운: {sipsin_gan}
- 오늘 일진의 지지({ib})가 나에게 주는 기운: {sipsin_ji}
- 내 일지({db})와 오늘 일진 지지({ib})의 관계: {rel}

[말투 규칙 — 최우선, 절대 예외 없음]
- 모든 문장을 '친근한 존댓말'로만 씁니다. 어미는 '~해요 / ~예요 / ~입니다 / ~보세요 / ~됩니다 / ~할게요' 등만 사용합니다.
- 반말('~해', '~야', '~봐', '~자', '~거야', '~지', '~더라')은 전체 출력에서 단 한 번도 쓰지 않습니다.
- 위 [화자 캐릭터]의 성격·에너지는 어휘 선택과 감탄사 빈도로만 표현하고, 존댓말은 그대로 유지합니다.

[점수화 규칙]
- 위 두 기운(십신)과 지지 관계의 긍정/부정 방향·강도를 종합해 분야별 0~100 정수 점수를 산출합니다.
- 정재·정관·정인·식신·편재 계열은 대체로 안정·기회, 편관·상관·겁재·편인 계열은 변동·자극·주의로 봅니다.
- 육합은 협력·인연, 충·파·해·형은 해당 분야의 마찰·이동으로 반영합니다.
- 점수를 50~60 중간값으로 뭉개지 마세요. 기운이 강하면 80 이상, 약하면 40 이하도 허용합니다.
- 점수와 문구의 방향은 일치시키되, 높은 점수에도 현실적 주의사항을, 낮은 점수에도 활용 가능한 행동을 담습니다.
- 모든 해석 문구는 최소 5줄 이상입니다. 사주 용어(십신·합충·용신 등)는 절대 노출하지 말고 캐릭터의 태도로만 드러냅니다.
- 2030 세대가 공감할 현실 언어로 말합니다. 같은 일주는 늘 같은 말투를 유지합니다.

[출력 스키마 규칙 — 반드시 준수]
- 아래 JSON의 키를 하나도 빠뜨리지 말고 정확히 그대로 출력합니다. 키 추가·삭제·이름 변경 금지.
- summary 객체는 반드시 overall, money, love_single, love_couple, work_study 5개 키를 모두 포함합니다.
  (싱글이든 커플이든 관계없이 love_single 과 love_couple 을 항상 둘 다 채웁니다.)
- keywords 는 빈 문자열 없이 서로 다른 한국어 키워드 정확히 3개입니다.
- 모든 값은 비어 있으면 안 됩니다.

[출력 JSON — 이 구조와 키를 그대로, 이 JSON 객체 하나만 출력]
{{
  "overall_score": <0-100 정수>,
  "money_score": <0-100 정수>,
  "love_score": <0-100 정수>,
  "work_study_score": <0-100 정수>,
  "summary": {{
    "overall": "오늘 하루 종합 총평 (존댓말, 5줄 이상)",
    "money": "돈의 흐름과 오늘의 구체적 상황 (존댓말, 5줄 이상)",
    "love_single": "싱글 관점 애정운 (존댓말, 5줄 이상)",
    "love_couple": "커플 관점 애정운 (존댓말, 5줄 이상)",
    "work_study": "직장/학업운 (존댓말, 5줄 이상)"
  }},
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "recommended_action": "오늘 실제로 해볼 행동으로 변환 (존댓말, 2-3문장)"
}}"""


_SUMMARY_SUBKEYS = ("overall", "money", "love_single", "love_couple", "work_study")


def coerce_daily_entry(entry: Any) -> Any:
    """모델이 스키마를 평탄화해서 준 경우 정규화한다.

    gemini-3.5-flash-lite 등 lite 계열은 배치 응답에서 summary 중첩 객체를 자주
    평탄화한다: summary 를 overall 텍스트(문자열)로, money/love_single/love_couple/
    work_study 를 최상위 형제 키로 내보낸다. 내용은 정상이므로 다시 중첩시켜 살린다.
    """
    if not isinstance(entry, dict):
        return entry
    summ = entry.get("summary")
    if isinstance(summ, str) and summ.strip():
        rebuilt = {"overall": summ}
        for k in ("money", "love_single", "love_couple", "work_study"):
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                rebuilt[k] = v
        # love_single/love_couple 이 없고 love 하나로 왔으면 양쪽에 복제
        if "love_single" not in rebuilt and isinstance(entry.get("love"), str):
            rebuilt["love_single"] = rebuilt["love_couple"] = entry["love"].strip()
        entry["summary"] = rebuilt
        for k in ("overall", "money", "love", "love_single", "love_couple", "work_study"):
            if isinstance(entry.get(k), str):   # 텍스트 형제 키만 제거(_score 는 int 라 보존)
                entry.pop(k, None)

    # 공백 정규화(문장마다 \n 넣는 응답 → 한 줄) + 번호/순번 표기 제거 + 오타 교정
    _c = lambda v: strip_enumeration(apply_text_fixups(v))
    if isinstance(entry.get("summary"), dict):
        entry["summary"] = {k: _c(v) for k, v in entry["summary"].items()}
    if isinstance(entry.get("recommended_action"), str):
        entry["recommended_action"] = _c(entry["recommended_action"])
    if isinstance(entry.get("keywords"), list):
        entry["keywords"] = [_c(k) for k in entry["keywords"]]
    return entry


def daily_valid(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    for k in ("overall_score", "money_score", "love_score", "work_study_score"):
        try:
            v = int(round(float(entry[k])))
        except Exception:
            return False
        if not (0 <= v <= 100):
            return False
    summ = entry.get("summary")
    if not isinstance(summ, dict):
        return False
    if not all(str(summ.get(k, "")).strip() for k in
               ("overall", "money", "love_single", "love_couple", "work_study")):
        return False
    kws = entry.get("keywords")
    if not isinstance(kws, list) or len([k for k in kws if str(k).strip()]) < 1:
        return False
    if not str(entry.get("recommended_action", "")).strip():
        return False
    return True


def daily_keys(only: Optional[str]) -> List[Tuple[str, str, str]]:
    """(key, day_ganji, iljin_ganji) 목록."""
    gapja = sixty_gapja()
    if only:
        d, _, i = only.partition("_")
        if d not in gapja or i not in gapja:
            print(f"[에러] --only 값이 60갑자 조합이 아닙니다: {only!r}")
            sys.exit(2)
        return [(only, d, i)]
    out = []
    for d in gapja:
        for i in gapja:
            out.append((f"{d}_{i}", d, i))
    return out


# ─────────────────────────────────────────────────────────── 생성 루프

def make_model(model_name: str, api_key: str, max_output_tokens: Optional[int] = None,
               system_instruction: Optional[str] = None):
    """모델별 독립 클라이언트로 생성.

    genai.configure() 는 프로세스 전역 싱글턴(_client_manager)을 덮어써 스레드 간
    경쟁이 생긴다(멀티 키 병렬 생성 시 다른 스레드의 키로 요청이 새어나갈 수 있음).
    대신 GenerativeModel._client 를 이 키 전용 클라이언트로 직접 바인딩해
    전역 상태를 건드리지 않고 스레드마다 독립적으로 동작하게 한다.
    """
    gen_cfg = {
        "response_mime_type": "application/json",
        "temperature": 0.0,
        "top_p": 1.0,
    }
    if max_output_tokens:
        gen_cfg["max_output_tokens"] = max_output_tokens
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction or _SYSTEM,
        generation_config=gen_cfg,
    )
    model._client = glm.GenerativeServiceClient(client_options={"api_key": api_key})
    return model


def generate_one(model, prompt: str, max_retries: int, base_delay: float,
                 timeout: int = 90) -> dict:
    """성공 시 dict 반환, 끝까지 실패하면 예외 raise (폴백 저장 방지)."""
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            # 응답 없이 무한 대기하는 것을 막는다(별칭이 무거운 모델로 연결된 경우 등).
            resp = model.generate_content(prompt, request_options={"timeout": timeout})
            return _extract_json(resp.text)
        except Exception as e:  # noqa: BLE001
            last_err = e
            if _is_credits_depleted(e):
                raise CreditsDepleted(str(e)) from e
            if _is_daily_quota(e):
                raise DailyQuotaExceeded(str(e)) from e
            if _is_invalid_key(e):
                raise InvalidApiKey(str(e)) from e
            if _is_model_unavailable(e):
                raise ModelUnavailable(str(e)) from e
            if _is_rate_limited(e):
                # 단기 429: 이 키로 오래 붙잡지 말고 호출자에게 넘겨 다른 키로 돌린다.
                raise RateLimited(str(e), _retry_delay_sec(e)) from e
            if attempt >= max_retries:
                break
            wait = min(base_delay * (2 ** attempt), 30)
            print(f"    ↻ 재시도 {attempt + 1}/{max_retries} ({type(e).__name__}, {wait:.0f}s 대기): {str(e)[:160]}")
            time.sleep(wait)
    raise RuntimeError(f"max_retries 초과: {last_err}")


def _resolve_models(args) -> List[str]:
    """최우선 모델: --model > GEMINI_MODEL_NAME(env) > DEFAULT_MODELS[0].

    config.GEMINI_MODEL_NAME(=flash-lite, 하루 20회) 은 여기서 기본값으로 쓰지 않는다.
    """
    primary = args.model or os.environ.get("GEMINI_MODEL_NAME") or DEFAULT_MODELS[0]
    if args.model or args.no_model_rotate:
        return [primary]
    return [primary] + [m for m in DEFAULT_MODELS if m != primary]


def _next_alive_key(cur: int, n_keys: int, dead: set) -> Optional[int]:
    """cur 다음 순번부터 한 바퀴 돌며 살아있는 키 인덱스를 찾는다."""
    for step in range(1, n_keys + 1):
        cand = (cur + step) % n_keys
        if cand not in dead:
            return cand
    return None


def run_daily_concurrent(args, todo: List[Tuple[str, str, str]], db: Dict[str, Any],
                          out_path: str, models: List[str], keys: List[str]) -> None:
    """(스레드 × 고정 키 1개) 로 동시에 여러 조합을 생성한다.

    google-generativeai 의 genai.configure() 는 프로세스 전역 상태라 스레드 간
    공유하면 요청이 다른 키로 새어나가는 경쟁이 생긴다. make_model() 이 스레드마다
    독립 클라이언트를 만들어 주므로, 워커마다 키를 하나씩 고정 배정해 안전하게
    병렬화한다. 모델 로테이션은 지원하지 않고(요청이 뒤섞이면 위험) 최우선
    모델 하나만 쓴다.
    """
    model_name = models[0]
    if len(models) > 1:
        print(f"[알림] 병렬 모드는 모델 로테이션을 지원하지 않습니다 → {model_name} 고정 사용")

    if args.limit:
        todo = todo[: args.limit]

    n_workers = max(1, min(args.workers, len(keys)))
    print(f"병렬 생성: worker {n_workers}개 (키 {len(keys)}개 중 1개씩 고정 배정) · 모델 {model_name}\n")

    work_q: "_queue.Queue[Tuple[str, str, str]]" = _queue.Queue()
    for t in todo:
        work_q.put(t)
    total_todo = len(todo)

    db_lock = threading.Lock()
    stats_lock = threading.Lock()
    dead_keys: set = set()
    made = 0
    failed: List[str] = []
    banmal: List[str] = []
    stop_all = threading.Event()
    credits_depleted = threading.Event()
    t0 = time.time()

    def log(msg: str) -> None:
        with stats_lock:
            print(msg)

    def worker_loop(worker_id: int) -> None:
        nonlocal made
        key_idx = worker_id % len(keys)
        model = make_model(model_name, keys[key_idx])
        while not stop_all.is_set():
            try:
                item = work_q.get_nowait()
            except _queue.Empty:
                return
            key_label, d, i = item
            try:
                entry = generate_one(model, daily_prompt(d, i), args.max_retries, args.delay)
            except CreditsDepleted as e:
                log(f"\n[전체중단] 결제 프리페이 크레딧 소진 — 재시도 무의미: {str(e)[:200]}")
                log("  → 충전 후 같은 명령으로 재실행하면 체크포인트부터 이어서 진행합니다.")
                credits_depleted.set()
                stop_all.set()
                work_q.put(item)
                return
            except (DailyQuotaExceeded, InvalidApiKey) as e:
                reason = "오늘 소진(PerDay)" if isinstance(e, DailyQuotaExceeded) else "키 무효/권한없음"
                with stats_lock:
                    dead_keys.add(key_idx)
                    alive = len(keys) - len(dead_keys)
                log(f"    ⚠ 워커#{worker_id} 키#{key_idx + 1} {reason} → 키 전환  (살아있는 키 {alive}/{len(keys)})")
                nxt = _next_alive_key(key_idx, len(keys), dead_keys)
                work_q.put(item)  # 이 항목은 다른 워커/키로 재시도
                if nxt is None:
                    log(f"    ✗ 워커#{worker_id} 사용 가능한 키가 없어 종료")
                    return
                key_idx = nxt
                model = make_model(model_name, keys[key_idx])
                continue
            except ModelUnavailable as e:
                log(f"[전체중단] 모델 {model_name} 사용 불가: {str(e)[:160]}")
                stop_all.set()
                work_q.put(item)
                return
            except RateLimited as e:
                wait = min(max(e.retry_after or 5, 3), 30)
                work_q.put(item)
                time.sleep(wait)
                continue
            except Exception as e:  # noqa: BLE001
                with stats_lock:
                    failed.append(key_label)
                log(f"[{key_label}]  ✗ 실패: {str(e)[:160]}")
                continue

            if not daily_valid(entry):
                with stats_lock:
                    failed.append(key_label)
                log(f"[{key_label}]  ✗ 스키마 불량(키 누락 등) → 건너뜀")
                continue

            entry["_model"] = model_name
            with db_lock:
                db[key_label] = entry
                _atomic_write_json(out_path, db)
                cur_total = len(db)
            with stats_lock:
                made += 1
                cur_made = made
                if _has_banmal(entry):
                    banmal.append(key_label)
                    flag = "  ⚠ 반말 의심"
                else:
                    flag = ""
                if cur_made % 25 == 0:
                    elapsed = time.time() - t0
                    remain = (total_todo - cur_made) * (elapsed / cur_made) / max(n_workers, 1)
                    extra = (f"  ── 진행: 이번 실행 {cur_made}/{total_todo} · DB {cur_total}/3600 "
                             f"· 남은 예상 ~{remain / 60:.0f}분 ──")
                else:
                    extra = ""
            print(f"[{cur_made}/{total_todo}] {key_label}  ✓ "
                  f"(전체 {entry['overall_score']} / 돈 {entry['money_score']} / "
                  f"애정 {entry['love_score']} / 일·학업 {entry['work_study_score']}) DB {cur_total}/3600{flag}")
            if extra:
                print(extra)

    threads = [threading.Thread(target=worker_loop, args=(w,), daemon=True) for w in range(n_workers)]
    try:
        for th in threads:
            th.start()
        for th in threads:
            th.join()
    except KeyboardInterrupt:
        stop_all.set()
        print("\n[중단] Ctrl-C — 여기까지 저장됨. 다시 실행하면 이어서 진행합니다.")
        for th in threads:
            th.join(timeout=10)

    dt = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"이번 실행: {made}개 생성 · 실패 {len(failed)}개 · 반말 의심 {len(banmal)}개 · {dt:.0f}s 소요")
    print(f"DB 총 {len(db)}/3600  ({100 * len(db) / 3600:.1f}%)  → {out_path}")
    if credits_depleted.is_set():
        print("상태: 결제 프리페이 크레딧 소진으로 중단됨. 충전 후 같은 명령으로 재실행하세요.")
    elif len(dead_keys) >= len(keys):
        print("상태: 모든 키가 소진/무효로 중단됨. 내일(한도 리셋 후) 재실행하세요.")
    elif len(db) >= 3600:
        print("상태: 전체 3600개 생성 완료 🎉")
    else:
        print("상태: 아직 미완료. 같은 명령을 다시 실행하면 이어서 진행합니다.")
    if failed:
        print(f"실패 키 {len(failed)}개(재실행 시 자동 재시도): " + ", ".join(failed[:30])
              + (" ..." if len(failed) > 30 else ""))
    if banmal:
        print(f"반말 의심 키 {len(banmal)}개(검토 후 필요 시 --overwrite --only 로 재생성): "
              + ", ".join(banmal[:30]) + (" ..." if len(banmal) > 30 else ""))


# ─────────────────────────────────────────────────── 배치 생성(비용 절감)

_DAILY_SCHEMA_BLOCK = """{
    "overall_score": <0-100 정수>,
    "money_score": <0-100 정수>,
    "love_score": <0-100 정수>,
    "work_study_score": <0-100 정수>,
    "summary": {
      "overall": "오늘 하루 종합 총평 (존댓말, 5줄 이상)",
      "money": "돈의 흐름과 오늘의 구체적 상황 (존댓말, 5줄 이상)",
      "love_single": "싱글 관점 애정운 (존댓말, 5줄 이상)",
      "love_couple": "커플 관점 애정운 (존댓말, 5줄 이상)",
      "work_study": "직장/학업운 (존댓말, 5줄 이상)"
    },
    "keywords": ["키워드1", "키워드2", "키워드3"],
    "recommended_action": "오늘 실제로 해볼 행동으로 변환 (존댓말, 2-3문장)"
  }"""


def _daily_item_block(key: str, day_ganji: str, iljin_ganji: str) -> str:
    """배치 프롬프트에 넣을, 조합 1개분 근거 데이터 블록."""
    dm, db = day_ganji[0], day_ganji[1]
    ig, ib = iljin_ganji[0], iljin_ganji[1]
    sipsin_gan = calculate_sipsin(dm, ig, is_gan=True)
    sipsin_ji = calculate_sipsin(dm, ib, is_gan=False)
    rel = branch_relation(db, ib)
    return (
        f"── 조합 키: {key} ──\n"
        f"{persona_prompt(dm, db)}\n"
        f"- 내 일주(성격/말투 기준): {day_ganji}\n"
        f"- 오늘 일진: {iljin_ganji}\n"
        f"- 오늘 일진의 천간({ig})이 나에게 주는 기운: {sipsin_gan}\n"
        f"- 오늘 일진의 지지({ib})가 나에게 주는 기운: {sipsin_ji}\n"
        f"- 내 일지({db})와 오늘 일진 지지({ib})의 관계: {rel}"
    )


def daily_batch_prompt(items: List[Tuple[str, str, str]]) -> str:
    """(key, 일주, 일진) N개 → 1회 호출용 프롬프트.

    응답은 '조합 키'를 최상위 key 로 갖는 JSON 객체 하나.
    """
    keys = [k for k, _, _ in items]
    blocks = "\n\n".join(_daily_item_block(k, d, i) for k, d, i in items)
    return f"""아래 {len(items)}개의 (내 일주, 오늘 일진) 조합 각각에 대해 오늘의 운세 텍스트를 만듭니다.
각 조합은 서로 완전히 독립입니다. 한 조합의 내용을 다른 조합에 복사하지 말고, 근거 데이터에 맞춰 개별적으로 씁니다.

[말투 규칙 — 최우선, 절대 예외 없음]
- 모든 문장을 '친근한 존댓말'로만 씁니다. 어미는 '~해요 / ~예요 / ~입니다 / ~보세요 / ~됩니다 / ~할게요' 등만 사용합니다.
- 반말('~해', '~야', '~봐', '~자', '~거야', '~지', '~더라')은 전체 출력에서 단 한 번도 쓰지 않습니다.
- 각 조합의 [화자 캐릭터] 성격·에너지는 어휘 선택과 감탄사 빈도로만 표현하고, 존댓말은 그대로 유지합니다.

[점수화 규칙]
- 각 조합의 두 기운(십신)과 지지 관계의 긍정/부정 방향·강도를 종합해 분야별 0~100 정수 점수를 산출합니다.
- 정재·정관·정인·식신·편재 계열은 대체로 안정·기회, 편관·상관·겁재·편인 계열은 변동·자극·주의로 봅니다.
- 육합은 협력·인연, 충·파·해·형은 해당 분야의 마찰·이동으로 반영합니다.
- 점수를 50~60 중간값으로 뭉개지 마세요. 기운이 강하면 80 이상, 약하면 40 이하도 허용합니다.
- 점수와 문구의 방향은 일치시키되, 높은 점수에도 현실적 주의사항을, 낮은 점수에도 활용 가능한 행동을 담습니다.
- 모든 해석 문구는 최소 5줄 이상입니다. 사주 용어(십신·합충·용신 등)는 절대 노출하지 말고 캐릭터의 태도로만 드러냅니다.
- 2030 세대가 공감할 현실 언어로 말합니다. 같은 일주는 늘 같은 말투를 유지합니다.

[출력 스키마 규칙 — 반드시 준수]
- 각 조합의 값은 정확히 이 7개 키만 가집니다: overall_score, money_score, love_score, work_study_score, summary, keywords, recommended_action.
- **summary 는 반드시 중첩된 JSON 객체입니다.** overall, money, love_single, love_couple, work_study 5개 하위 키를 summary "안에" 넣습니다.
  summary 를 문자열로 쓰거나, money·love_single·love_couple·work_study 를 조합 값의 최상위로 빼내지 마세요.
  (싱글이든 커플이든 love_single 과 love_couple 을 항상 둘 다 채웁니다.)
- keywords 는 빈 문자열 없이 서로 다른 한국어 키워드 정확히 3개입니다.
- 모든 값은 비어 있으면 안 됩니다.

[생성할 조합 — 총 {len(items)}개]

{blocks}

[출력 형식 — 아래 JSON 객체 하나만, 마크다운 펜스(```)나 설명 문장 없이]
- 최상위 key 는 위에 준 '조합 키' 문자열을 그대로 사용합니다: {', '.join(keys)}
- 요청한 {len(items)}개 키를 모두 포함하고, 각 값에 아래 구조를 정확히 그대로 채웁니다(모든 조합 동일 구조).

{{
  "{keys[0]}": {_DAILY_SCHEMA_BLOCK},
  "{keys[1] if len(keys) > 1 else '조합키2'}": {{ "...위와 완전히 동일한 구조..." }}
}}"""


def _seconds_until_pacific_midnight(buffer_min: int = 3) -> float:
    """다음 태평양시(America/Los_Angeles) 자정까지 남은 초 + 여유분.

    Gemini 무료 등급 PerDay 한도는 태평양시 자정에 리셋된다.
    """
    from datetime import datetime, timedelta
    try:
        from zoneinfo import ZoneInfo
        tz: Any = ZoneInfo("America/Los_Angeles")
    except Exception:
        tz = None
    now = datetime.now(tz)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (nxt - now).total_seconds() + buffer_min * 60)


def _unwrap_batch_payload(raw: dict, want_keys: List[str]) -> dict:
    """모델이 {"results": {...}} / {"운세": {...}} 처럼 한 겹 더 감쌌으면 벗겨낸다."""
    if not isinstance(raw, dict):
        return {}
    if any(k in raw for k in want_keys):
        return raw
    if len(raw) == 1:
        inner = next(iter(raw.values()))
        if isinstance(inner, dict) and any(k in inner for k in want_keys):
            return inner
    return raw


def _run_batched(args, todo, db, out_path, keys, *, prompt_fn, valid_fn, coerce_fn,
                 models, max_output_tokens, total, system_instruction, banmal_fn,
                 unit="조합", store_fn=None, count_fn=None, header="") -> None:
    """1회 호출 = 여러 항목. 이미 있는 키는 상위 run_* 에서 이미 걸러진 상태.

    daily / personality 공용. 도메인 차이는 prompt_fn·valid_fn·coerce_fn·models·
    system_instruction·total 로 주입한다. todo/chunk 항목은 (key, ...) 튜플이며
    이 함수는 it[0](=key)만 사용한다.

    store_fn(db, key, entry, model_name): 저장 방식(기본: db[key]=entry + _model).
    count_fn(db): 진행률 표시용 완료 수(기본: len(db)).
    """
    batch_size = max(1, args.batch)
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("생성할 항목이 없습니다. (모두 완료)")
        return

    def _mk(mi_: int, ki_: int):
        return make_model(models[mi_], keys[ki_], max_output_tokens, system_instruction)

    if store_fn is None:
        def store_fn(_db, _key, _entry, _model):
            _entry["_model"] = _model
            _db[_key] = _entry
    if count_fn is None:
        count_fn = len

    n_calls = (len(todo) + batch_size - 1) // batch_size
    if header:
        print(header)
    print(f"배치 모드: {len(todo)}개 {unit} · {batch_size}개/호출 ≈ {n_calls}회 호출")
    print(f"모델 우선순위: {', '.join(models)}   ·   API 키 {len(keys)}개")
    print(f"PerDay(일일 한도) 소진 시: 다음 키로 → 모든 키 소진 시 태평양시 자정까지 "
          f"대기 후 자동 재개 (최대 {args.max_days}일)\n")

    mi, ki = 0, 0
    dead_keys: set = set()          # 오늘 PerDay 소진된 키 (자정 리셋)
    made, day_waits = 0, 0
    failed: List[str] = []
    banmal: List[str] = []
    attempts: Dict[str, int] = {}   # 키별 시도 횟수 (누락/불량 재시도 상한)
    t0 = time.time()

    model = _mk(mi, ki)

    from collections import deque
    work = deque(todo[i:i + batch_size] for i in range(0, len(todo), batch_size))
    done_calls = 0
    try:
        while work:
            chunk = work.popleft()
            chunk_keys = [it[0] for it in chunk]
            try:
                raw = generate_one(model, prompt_fn(chunk),
                                   args.max_retries, args.delay, timeout=300)
            except CreditsDepleted as e:
                print(f"\n[전체중단] 결제 프리페이 크레딧 소진 — 대기·재시도 무의미: {str(e)[:200]}")
                print("  → 크레딧을 충전하거나 결제를 해제해 무료 등급으로 되돌린 뒤, "
                      "같은 명령으로 재실행하면 체크포인트부터 이어서 진행합니다.")
                work.appendleft(chunk)
                break
            except DailyQuotaExceeded:
                dead_keys.add(ki)
                alive = len(keys) - len(dead_keys)
                print(f"    ⚠ 키#{ki + 1} 오늘 한도(PerDay) 소진 → 키 전환  (남은 키 {alive}/{len(keys)})")
                nxt = _next_alive_key(ki, len(keys), dead_keys)
                if nxt is not None:
                    ki = nxt
                    model = _mk(mi, ki)
                    work.appendleft(chunk)
                    continue
                # 모든 키 소진 → 자정까지 대기
                if day_waits >= args.max_days:
                    print(f"\n[중단] 연속 대기 {args.max_days}일 한도 도달. "
                          f"나중에 같은 명령으로 이어서 진행하세요.")
                    work.appendleft(chunk)
                    break
                wait_s = _seconds_until_pacific_midnight()
                day_waits += 1
                from datetime import datetime, timedelta
                resume_at = datetime.now() + timedelta(seconds=wait_s)
                print(f"\n[대기] 모든 키가 오늘 한도 소진 → 태평양시 자정까지 ~{wait_s / 3600:.1f}시간 대기."
                      f"\n       재개 예정: {resume_at:%Y-%m-%d %H:%M} (로컬)  ·  {day_waits}/{args.max_days}일차"
                      f"\n       (Ctrl-C 로 중단해도 여기까지 저장돼 있고, 재실행하면 이어집니다.)")
                time.sleep(wait_s)
                dead_keys.clear()
                ki = 0
                model = _mk(mi, ki)
                work.appendleft(chunk)
                continue
            except ModelUnavailable as e:
                if mi + 1 < len(models):
                    print(f"    ⚠ 모델 {models[mi]} 사용불가 → {models[mi + 1]} 전환: {str(e)[:120]}")
                    mi += 1
                    model = _mk(mi, ki)
                    work.appendleft(chunk)
                    continue
                print(f"\n[중단] 사용 가능한 배치 모델이 없습니다: {str(e)[:160]}")
                work.appendleft(chunk)
                break
            except InvalidApiKey:
                dead_keys.add(ki)
                nxt = _next_alive_key(ki, len(keys), dead_keys)
                print(f"    ⚠ 키#{ki + 1} 무효/권한없음 → 키 전환")
                if nxt is None:
                    print("\n[중단] 사용 가능한 키가 없습니다.")
                    work.appendleft(chunk)
                    break
                ki = nxt
                model = _mk(mi, ki)
                work.appendleft(chunk)
                continue
            except RateLimited as e:
                wait = min(max(e.retry_after or 10, 5), 60)
                print(f"    ⏳ 분당(PerMinute) 한도 → {wait}s 대기 후 재시도")
                time.sleep(wait)
                work.appendleft(chunk)
                continue
            except Exception as e:  # noqa: BLE001
                # JSON 잘림/파싱 실패 등 → 절반 크기로 쪼개 재시도(상한 내)
                done_calls += 1
                retriable = [it for it in chunk if attempts.get(it[0], 0) < 2]
                for it in retriable:
                    attempts[it[0]] = attempts.get(it[0], 0) + 1
                giveup = [it[0] for it in chunk if attempts.get(it[0], 0) >= 2]
                failed.extend(giveup)
                print(f"[{done_calls}] {chunk_keys[0]}…({len(chunk)})  ✗ 호출/파싱 실패: {str(e)[:130]}")
                if retriable:
                    half = max(1, len(retriable) // 2) if len(retriable) > 1 else 1
                    for j in range(0, len(retriable), half):
                        work.append(retriable[j:j + half])
                continue

            done_calls += 1
            payload = _unwrap_batch_payload(raw, chunk_keys)
            got, miss, bad = 0, [], []
            for it in chunk:
                key = it[0]
                entry = payload.get(key) if isinstance(payload, dict) else None
                if not isinstance(entry, dict):
                    miss.append(it); continue
                entry = coerce_fn(entry)
                if not valid_fn(entry):
                    bad.append(it); continue
                store_fn(db, key, entry, models[mi])
                got += 1
                if banmal_fn and banmal_fn(entry):
                    banmal.append(key)
            if got:
                _atomic_write_json(out_path, db)
            made += got

            # 누락/불량 → 시도 2회까지 재시도, 넘으면 포기(다음 전체 재실행 때 자동 재시도됨)
            requeue = []
            for it in miss + bad:
                attempts[it[0]] = attempts.get(it[0], 0) + 1
                if attempts[it[0]] < 2:
                    requeue.append(it)
                else:
                    failed.append(it[0])
            if requeue:
                work.append(requeue)

            cnt = count_fn(db)
            print(f"[{done_calls}] {chunk_keys[0]}…({len(chunk)})  ✓ {got}개"
                  + (f" · 누락 {len(miss)}" if miss else "")
                  + (f" · 불량 {len(bad)}" if bad else "")
                  + f"   완료 {cnt}/{total}")
            if made and done_calls % 10 == 0:
                elapsed = time.time() - t0
                rate = elapsed / max(made, 1)
                remain = (total - cnt) * rate
                print(f"  ── 진행: {cnt}/{total} · 이번 실행 {made}개 "
                      f"· 평균 {rate:.1f}s/{unit} · 남은 예상 {remain / 3600:.1f}h ──")
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\n[중단] Ctrl-C — 여기까지 저장됨. 같은 명령으로 이어서 진행합니다.")

    dt = time.time() - t0
    uniq_fail = sorted(set(failed))
    final_cnt = count_fn(db)
    print(f"\n{'=' * 60}")
    print(f"이번 실행: {made}개 생성 · 미완료(재실행 시 자동 재시도) {len(uniq_fail)}개 "
          f"· 반말 의심 {len(set(banmal))}개 · {dt:.0f}s 소요 · 대기 {day_waits}일")
    print(f"완료 {final_cnt}/{total}  ({100 * final_cnt / total:.1f}%)  → {out_path}")
    if final_cnt >= total:
        print(f"상태: 전체 {total}개 생성 완료 🎉")
    else:
        print("상태: 아직 미완료. 같은 명령을 다시 실행하면 이어서 진행합니다.")
    if uniq_fail:
        print(f"미완료 키: " + ", ".join(uniq_fail[:30]) + (" ..." if len(uniq_fail) > 30 else ""))
    if banmal:
        b = sorted(set(banmal))
        print(f"반말 의심 키(검토 후 --overwrite --only 로 재생성): "
              + ", ".join(b[:30]) + (" ..." if len(b) > 30 else ""))
    return made


def run_daily_batched(args, todo, db, out_path, keys) -> None:
    models = [args.model] if args.model else list(DAILY_BATCH_MODELS)
    _run_batched(args, todo, db, out_path, keys,
                 prompt_fn=daily_batch_prompt, valid_fn=daily_valid,
                 coerce_fn=coerce_daily_entry, models=models,
                 max_output_tokens=DAILY_BATCH_MAX_OUTPUT_TOKENS, total=3600,
                 system_instruction=None, banmal_fn=_has_banmal, unit="조합")


# ─────────────────────────────────────────────── PERSONALITY (나의 성격/적성)

# 일주(일간·일지) 60가지만으로 생성. 오늘 일진·대운·원국 나머지는 반영 안 함(daily 와 동일 트레이드오프).
# 키 = 일주 간지 한자 2자(예 "戊辰"). 값 = {"character": {6필드}, "aptitude": {6필드},
#   "_model_character": ..., "_model_aptitude": ...}. 성격/적성은 각각 별도 호출로 생성한다.
PERSONALITY_BATCH_MAX_OUTPUT_TOKENS = 65536
_PERSONALITY_CHAR_KEYS = ("base_nature", "strengths", "weaknesses",
                          "supplement", "relationships", "work_style")
_PERSONALITY_APT_KEYS = ("fit_task", "fit_field", "good_env",
                         "org_style", "tiring_env", "favorable_direction")


def _personality_item_block(ganji: str) -> str:
    dm, db = ganji[0], ganji[1]
    dm_elem = GAN_ELEM.get(dm, "?")
    db_elem = JI_ELEM.get(db, "?")
    ji_sipsin = calculate_sipsin(dm, db, is_gan=False)
    jjg = JIJANGGAN.get(db, []) or []
    jjg_desc = ", ".join(f"{c}({calculate_sipsin(dm, c, is_gan=True)})" for c, _ in jjg) or "-"
    return (
        f"── 일주 키: {ganji} ──\n"
        f"{persona_prompt(dm, db)}\n"
        f"- 일간(타고난 기질의 축): {dm} · 오행 {dm_elem}\n"
        f"- 일지(받쳐주는 성향): {db} · 오행 {db_elem} · 일간과의 관계 {ji_sipsin}\n"
        f"- 일지 속 숨은 기운: {jjg_desc}"
    )


# 두 개의 독립 결과물: 성격(character) 6필드 · 적성/직업운(aptitude) 6필드.
# 유저 화면에서 각각 풍성하게 보여야 하므로 한 번의 호출에 섞지 않고 그룹별로 따로 생성한다.
_PERSONALITY_GROUPS = {
    "character": {
        "keys": _PERSONALITY_CHAR_KEYS,
        "title": "타고난 '성격'",
        "focus": "이 사람이 '어떤 사람인지' — 기질, 강점, 약점, 인간관계, 일하는 태도",
        "schema": [
            ("base_nature", "타고난 기본 성향 — 이 사람을 한마디로 어떤 사람이라 부를 수 있는지"),
            ("strengths", "성격적 강점 — 어떤 상황에서 이 사람의 진가가 드러나는지"),
            ("weaknesses", "성격적 약점·주의점 — 어떤 상황에서 손해를 보거나 부딪히는지"),
            ("supplement", "그 약점을 보완하는 구체적인 습관·행동"),
            ("relationships", "친구·연인·동료 관계에서 실제로 드러나는 모습"),
            ("work_style", "일할 때의 태도 — 어떤 방식으로 일할 때 성과가 나는지"),
        ],
    },
    "aptitude": {
        "keys": _PERSONALITY_APT_KEYS,
        "title": "타고난 '적성·직업운'",
        "focus": "이 사람에게 '어떤 일·분야·환경이 맞는지' — 구체적인 직무·업종·조직 환경",
        "schema": [
            ("fit_task", "잘 맞는 업무 유형과 그 이유 (구체적인 직무 활동 예시 포함)"),
            ("fit_field", "잘 맞는 분야·업종 (실제 직업·산업 이름을 몇 개 들어 설명)"),
            ("good_env", "능력이 크게 자라는 조직·환경 조건"),
            ("org_style", "조직 안에서 맡으면 잘하는 역할·포지션"),
            ("tiring_env", "빨리 지치고 성과가 안 나는 환경 — 피해야 할 조건"),
            ("favorable_direction", "적성을 살리기 위해 커리어에서 잡으면 좋은 방향·전략"),
        ],
    },
}


def _personality_group_prompt(group: str, items: List[Tuple[str, str]]) -> str:
    g = _PERSONALITY_GROUPS[group]
    keys = [k for k, _ in items]
    blocks = "\n\n".join(_personality_item_block(gj) for _, gj in items)
    schema_lines = ",\n    ".join(
        f'"{k}": "{desc} (친근한 존댓말, 5~7문장으로 풍성하게)"' for k, desc in g["schema"]
    )
    return f"""아래 {len(items)}개 일주(일간·일지) 각각에 대해, 그 사람의 {g['title']}을 씁니다.
초점: {g['focus']}.
각 일주는 완전히 독립입니다. 한 일주의 내용을 다른 일주에 복사하지 말고 근거에 맞춰 개별적으로 씁니다.
이건 '오늘의 운세'가 아니라 타고난 원판(기질) 설명이므로 날짜·시기·"오늘"·"요즘" 같은 표현을 쓰지 않습니다.

[말투 규칙 — 최우선, 예외 없음]
- 모든 문장을 친근한 존댓말로만 씁니다('~해요 / ~예요 / ~입니다 / ~보세요 / ~편입니다').
- 반말('~해', '~야', '~지', '~거야', '~더라')은 전체 출력에서 한 번도 쓰지 않습니다.
- 각 일주 [화자 캐릭터]의 성격·에너지는 어휘 선택으로만 드러내고 존댓말은 그대로 유지합니다.

[내용 규칙]
- 각 항목은 **5~7문장으로 충분히 풍성하게** 씁니다. 한두 문장으로 짧게 끝내지 않습니다.
- 각 값은 번호·순번·목록 기호(예: "1.", "1)", "1/6", "[1]", "①", 문장 앞의 "-")를 붙이지 않고, 자연스럽게 이어지는 서술형 문장으로만 씁니다.
- 형용사 나열이 아니라 구체적인 행동·상황·직무 예시를 넣습니다.
- 사주 용어(십신·오행·격국·용신·지장간 등)는 절대 노출하지 않고 태도로만 드러냅니다.
- 2030 세대가 공감할 현실 언어로 씁니다. 같은 일주는 늘 같은 캐릭터를 유지합니다.

[생성할 일주 — 총 {len(items)}개]

{blocks}

[출력 형식 — 아래 JSON 객체 하나만, 마크다운 펜스(```)나 설명 문장 없이]
- 최상위 key 는 위 '일주 키'(한자 2자)를 그대로 사용합니다: {', '.join(keys)}
- 각 일주 값은 정확히 아래 {len(g['keys'])}개 키만 가지는 평평한 객체입니다(중첩 금지). 모든 값은 비어 있으면 안 됩니다.

{{
  "{keys[0]}": {{
    {schema_lines}
  }},
  "{keys[1] if len(keys) > 1 else '일주2'}": {{ "...위와 동일한 {len(g['keys'])}개 키..." }}
}}"""


def _personality_group_coerce(entry: Any, field_keys: Tuple[str, ...]) -> Any:
    """그룹(6필드) 응답 정규화. 모델이 한 겹 더 감쌌으면(예: {"character": {...}}) 벗겨내고,
    공백 정리 + 번호/순번 표기 제거."""
    if isinstance(entry, dict) and len(entry) == 1:
        inner = next(iter(entry.values()))
        if isinstance(inner, dict) and any(k in inner for k in field_keys):
            entry = inner
    if not isinstance(entry, dict):
        return entry
    return {k: strip_enumeration(apply_text_fixups(v)) for k, v in entry.items()}


def _personality_group_valid(entry: Any, field_keys: Tuple[str, ...]) -> bool:
    return isinstance(entry, dict) and all(str(entry.get(k, "")).strip() for k in field_keys)


def _banmal_in_texts(texts) -> bool:
    hits = 0
    for blob in texts:
        for sent in _SENT_SPLIT.split(str(blob)):
            s = sent.strip().strip("\"'“”‘’()[]")
            if len(s) < 3 or _JONDAE_END.search(s):
                continue
            if _BANMAL_END.search(s):
                hits += 1
    return hits >= 2


def run_personality(args) -> None:
    out_path = args.out or PERSONALITY_DB_PATH
    db = _load_json(out_path)
    gapja = sixty_gapja()
    if args.only:
        if args.only not in gapja:
            print(f"[에러] --only 값이 60갑자가 아닙니다: {args.only!r}")
            sys.exit(2)
        gapja = [args.only]

    print(f"DB: {out_path}")
    print(f"기존 항목: {len(db)}개 / 목표 60 (일주별 character + aptitude 따로 생성)")

    if not args.batch or args.batch < 2:
        args.batch = 10

    if args.dry_run:
        for group in ("character", "aptitude"):
            need = [g for g in gapja
                    if args.overwrite or not _personality_group_valid(
                        db.get(g, {}).get(group), _PERSONALITY_GROUPS[group]["keys"])]
            print(f"[{group}] 대상 {len(need)}개: " + ", ".join(need[:20]) + (" ..." if len(need) > 20 else ""))
        print("dry-run 종료.")
        return

    keys = load_api_keys()
    if not keys:
        print("[에러] GEMINI_API_KEY / GEMINI_API_KEY_1.. 미설정")
        sys.exit(1)
    models = [args.model] if args.model else list(DAILY_BATCH_MODELS)

    for group in ("character", "aptitude"):
        gconf = _PERSONALITY_GROUPS[group]
        fkeys = gconf["keys"]
        todo = [(g, g) for g in gapja
                if args.overwrite or not _personality_group_valid(db.get(g, {}).get(group), fkeys)]
        if not todo:
            print(f"\n[{group}] 생성할 항목 없음 (모두 완료)")
            continue

        def _store(_db, _key, _entry, _model, _grp=group):
            slot = _db.setdefault(_key, {})
            slot[_grp] = _entry
            slot[f"_model_{_grp}"] = _model

        def _count(_db, _grp=group, _fk=fkeys):
            return sum(1 for v in _db.values() if _personality_group_valid(v.get(_grp), _fk))

        _run_batched(
            args, todo, db, out_path, keys,
            prompt_fn=(lambda items, _grp=group: _personality_group_prompt(_grp, items)),
            valid_fn=(lambda e, _fk=fkeys: _personality_group_valid(e, _fk)),
            coerce_fn=(lambda e, _fk=fkeys: _personality_group_coerce(e, _fk)),
            models=models, max_output_tokens=PERSONALITY_BATCH_MAX_OUTPUT_TOKENS, total=60,
            system_instruction=_PERSONALITY_SYSTEM,
            banmal_fn=(lambda e: _banmal_in_texts(e.values()) if isinstance(e, dict) else False),
            unit="일주", store_fn=_store, count_fn=_count,
            header=f"\n{'━' * 60}\n[{group}] {gconf['title']} — 대상 {len(todo)}개",
        )


# ─────────────────────────────── RELATIONSHIP (재회/짝사랑/결혼운)
#
# 조합: 60 일주(본인) × {상대 없음 | 60 일주(상대)} × 3 유형(reunion/crush/marriage)
#   = 상대 없음  60 × 3          = 180
#   + 상대 있음  60 × 60 × 3     = 10,800
#   = 총 10,980
# 키: "<본인>_<유형>"            (상대 없음, 예 "甲子_reunion")
#     "<본인>_<상대>_<유형>"     (상대 있음, 예 "甲子_乙丑_marriage")
# 날짜 의존 수치(3개월 실제 월, 결혼 10년 강도 창)는 런타임 엔진이 계산.
# 여기서는 AI 서술만 미리 생성한다. 3개월 전략은 "1/2/3개월차" 상대 순번으로.
RELATIONSHIP_DB_PATH = os.path.join(_ROOT, "domains", "relationship", "data", "relationship_db.json")
RELATIONSHIP_BATCH_MAX_OUTPUT_TOKENS = 65536
_REL_TYPES = ("reunion", "crush", "marriage")
_REL_TYPE_KO = {"reunion": "재회운", "crush": "짝사랑운", "marriage": "결혼운"}
_REL_FOCUS = {
    "reunion": "과거 인연이 다시 떠오르거나 연락이 닿을 흐름, 미련과 애정의 구분, 새 인연과의 비교, 먼저 움직여야 할지 관찰해야 할지",
    "crush": "상대에게 다가가는 방식, 고백·표현의 타이밍, 밀당보다 진심, 관계가 흐지부지되지 않게 하는 태도",
    "marriage": "결혼을 매듭짓기 좋은 시기의 '특징'(구체적 연도·나이는 말하지 않음), 그 전까지 관계 기반을 다지는 법, 서두름과 준비의 균형",
}

_RELATIONSHIP_SYSTEM = (
    "당신은 2030 세대를 위한 연애·결혼운 화자입니다. 제공된 '내 일주'(그리고 있으면 '상대 일주') "
    "데이터만 근거로 해석합니다. 사주 용어(십신·오행·합충·배우자성·도화 등)는 절대 노출하지 않고 "
    "상황·태도로만 드러냅니다. 말투는 예외 없이 친근한 존댓말('~해요/~예요/~입니다/~보세요/~편입니다'). "
    "반말·번호표기·목록기호는 쓰지 않습니다. 특정 날짜·연도·나이를 단정하지 않습니다. "
    "지정된 키를 모두 포함한 유효한 JSON 하나만 출력하고, Markdown 펜스나 설명 문장은 쓰지 않습니다."
)


def _rel_parse(key: str) -> Tuple[str, Optional[str], str]:
    """key -> (본인 일주, 상대 일주 or None, 유형)."""
    p = key.split("_")
    return (p[0], None, p[1]) if len(p) == 2 else (p[0], p[1], p[2])


def relationship_all_keys() -> List[str]:
    g = sixty_gapja()
    keys: List[str] = []
    for t in _REL_TYPES:                       # 상대 없음 (유형별 60)
        keys += [f"{a}_{t}" for a in g]
    offsets = list(range(1, 60)) + [0]         # 1..59, 0 (같은 일주 커플은 맨 뒤)
    for t in _REL_TYPES:                       # 상대 있음 (유형별 3600, offset·i 순)
        for off in offsets:
            for i in range(60):
                keys.append(f"{g[i]}_{g[(i + off) % 60]}_{t}")
    return keys


def _rel_item_block(key: str) -> str:
    a, b, t = _rel_parse(key)
    dm, dbc = a[0], a[1]
    lines = [
        f"── 키: {key} ──",
        persona_prompt(dm, dbc),
        f"- 내 일주: {a}  (일간 {dm}/{GAN_ELEM.get(dm)}, 일지 {dbc}/{JI_ELEM.get(dbc)})",
    ]
    if b:
        pm, pb = b[0], b[1]
        lines += [
            f"- 상대 일주: {b}  (일간 {pm}/{GAN_ELEM.get(pm)}, 일지 {pb}/{JI_ELEM.get(pb)})",
            f"- 두 사람 일지 관계: {branch_relation(dbc, pb)}",
            f"- 상대 일간이 나에게 주는 기운: {calculate_sipsin(dm, pm, is_gan=True)}",
            f"- 상대 일지가 나에게 주는 기운: {calculate_sipsin(dm, pb, is_gan=False)}",
        ]
    return "\n".join(lines)


def _rel_segment_prompt(mode: str, rtype: str, items: List[Tuple[str]]) -> str:
    keys = [it[0] for it in items]
    blocks = "\n\n".join(_rel_item_block(k) for k in keys)
    ko = _REL_TYPE_KO[rtype]
    who = "내 일주 하나" if mode == "solo" else "나와 상대, 두 사람의 일주"
    if mode == "couple" and rtype in ("reunion", "crush"):
        schema_body = """{
    "overall": "두 사람 관점의 종합 흐름 (친근한 존댓말, 8~12문장). 서로의 결이 어떻게 맞고 어긋나는지, 관계가 나아갈 방향",
    "strategy_3months": [
      "1개월차에 취하면 좋은 구체적 행동 전략 (한 문단)",
      "2개월차 — 1개월차와 다른 전략 (한 문단)",
      "3개월차 — 또 다른 전략, 관계를 매듭짓거나 다음 단계로 (한 문단)"
    ]
  }"""
        extra = "- strategy_3months 는 정확히 3개, 각 달마다 서로 다른 행동 전략입니다. 특정 월 이름은 쓰지 마세요('1개월차'처럼 순번으로)."
    elif mode == "couple" and rtype == "marriage":
        schema_body = """{
    "overall": "나 개인 관점의 결혼 시기 흐름 (친근한 존댓말, 8~12문장). 어떤 시기 특징에서 결혼을 매듭짓기 좋은지, 그 전까지 할 일",
    "couple_overall": "두 사람을 함께 봤을 때의 결혼 흐름 (친근한 존댓말, 6~10문장). 서로의 준비 상태와 관계 안정감이 언제 잘 맞는지"
  }"""
        extra = "- 구체적 연도·나이는 절대 단정하지 마세요. '어떤 시기의 특징'으로만 서술합니다."
    else:  # solo, 모든 유형
        schema_body = """{
    "overall": "종합 흐름과 조언 (친근한 존댓말, 8~12문장)"
  }"""
        extra = "- 상대가 없는 1인 기준입니다. 구체적 날짜·연도는 단정하지 마세요."

    return f"""아래 {len(items)}개 항목 각각에 대해 {ko}({who} 기준)를 씁니다.
각 항목은 완전히 독립입니다. 한 항목 내용을 다른 항목에 복사하지 말고 근거에 맞춰 개별적으로 씁니다.

[이 유형이 다루는 것] {_REL_FOCUS[rtype]}

[말투·형식 규칙 — 최우선]
- 친근한 존댓말만('~해요/~예요/~입니다/~보세요/~편입니다'). 반말 금지.
- 번호·순번·목록 기호("1.", "1)", "1/6", "[1]", "①", 문장 앞 "-")를 붙이지 않고 서술형 문장으로만 씁니다.
- 사주 용어 노출 금지: 십신·오행·합충·배우자성·도화는 물론, "일주"·"갑자일주"·"을축"·"간지"·"천간"·"지지" 같은 말도 쓰지 않습니다. 그냥 "나"와 "상대"로만 지칭하고, 성격은 태도·행동·감정으로만 묘사합니다.
- 특정 날짜·연도·나이를 단정하지 않고, "오늘"·"요즘"·"이번 주"·"지금 이 시기" 같은 시점 표현도 쓰지 않습니다(타고난 흐름 설명이므로).
{extra}

[생성할 항목 — 총 {len(items)}개]

{blocks}

[출력 형식 — 아래 JSON 객체 하나만, 마크다운 펜스나 설명 없이]
- 최상위 key 는 위 '키' 문자열을 그대로 사용합니다: {', '.join(keys)}
- 각 값 구조:

{{
  "{keys[0]}": {schema_body},
  "{keys[1] if len(keys) > 1 else '키2'}": {{ "...위와 동일 구조..." }}
}}"""


def _rel_clean(s: Any) -> Any:
    return strip_enumeration(apply_text_fixups(s, strip_time_words=True))


def _rel_coerce(entry: Any, mode: str, rtype: str) -> Any:
    if isinstance(entry, dict) and len(entry) == 1:
        inner = next(iter(entry.values()))
        if isinstance(inner, dict) and ("overall" in inner):
            entry = inner
    if not isinstance(entry, dict):
        return entry
    if isinstance(entry.get("overall"), str):
        entry["overall"] = _rel_clean(entry["overall"])
    if isinstance(entry.get("couple_overall"), str):
        entry["couple_overall"] = _rel_clean(entry["couple_overall"])
    s = entry.get("strategy_3months")
    if isinstance(s, dict):                       # {"1개월차": "..."} → 리스트
        s = [s[k] for k in sorted(s)]
    if isinstance(s, list):
        entry["strategy_3months"] = [_rel_clean(str(x)) for x in s if str(x).strip()]
    return entry


def _rel_valid(entry: Any, mode: str, rtype: str) -> bool:
    if not isinstance(entry, dict) or not str(entry.get("overall", "")).strip():
        return False
    if mode == "couple" and rtype in ("reunion", "crush"):
        s = entry.get("strategy_3months")
        if not (isinstance(s, list) and len([x for x in s if str(x).strip()]) >= 3):
            return False
    if mode == "couple" and rtype == "marriage":
        if not str(entry.get("couple_overall", "")).strip():
            return False
    return True


def _rel_texts(entry: Any) -> List[str]:
    if not isinstance(entry, dict):
        return []
    out = [str(entry.get("overall", "")), str(entry.get("couple_overall", ""))]
    s = entry.get("strategy_3months")
    if isinstance(s, list):
        out += [str(x) for x in s]
    return out


def _rel_mode_type(key: str) -> Tuple[str, str]:
    a, b, t = _rel_parse(key)
    return ("solo" if b is None else "couple"), t


def _rel_done_count(db: Dict[str, Any], all_keys: List[str]) -> int:
    return sum(1 for k in all_keys if _rel_valid(db.get(k), *_rel_mode_type(k)))


# ─────────────────────────────── COMPATIBILITY (궁합)
#
# 조합: 60 일주(본인) × 60 일주(상대) = 3,600  (relation_type=romantic 고정 — 프론트가 항상 romantic 만 전송)
# 키: "<본인 일주>_<상대 일주>"  예) "甲子_乙丑"
# 점수·한줄평·관계요소는 런타임 엔진(calculate_compatibility_interactions)이 전체 사주로 계산.
# 여기서는 일주쌍 기준의 AI 서술(report 7필드)만 미리 생성한다. (daily/personality 와 동일한 '일주 중심' 트레이드오프)
COMPATIBILITY_DB_PATH = os.path.join(_ROOT, "domains", "compatibility", "data", "compatibility_db.json")
COMPATIBILITY_BATCH_MAX_OUTPUT_TOKENS = 65536
_COMPAT_FIELDS = ("overall", "love", "communication", "conflict",
                  "conflict_resolution", "economy", "relationship_advice")

_COMPATIBILITY_SYSTEM = (
    "당신은 2030 세대를 위한 궁합 화자입니다. 제공된 두 사람의 관계 데이터만 근거로 해석합니다. "
    "사주 용어(십신·오행·합충·배우자성·도화 등)는 물론 '일주'·'천간'·'지지'·'간지'·'갑자'·'을축' 같은 말도 "
    "절대 쓰지 않고, 그냥 '나'와 '상대'로만 지칭하며 성격은 태도·행동·감정으로만 묘사합니다. "
    "말투는 예외 없이 친근한 존댓말('~해요/~예요/~입니다/~보세요/~편입니다'). 반말·번호표기·목록기호는 쓰지 않습니다. "
    "특정 날짜·나이·점수 숫자는 언급하지 않습니다. 지정된 키를 모두 포함한 유효한 JSON 하나만 출력하고, "
    "Markdown 펜스나 설명 문장은 쓰지 않습니다."
)

_CG_HAP = {frozenset(x) for x in (("甲", "己"), ("乙", "庚"), ("丙", "辛"), ("丁", "壬"), ("戊", "癸"))}
_CG_CHUNG = {frozenset(x) for x in (("甲", "庚"), ("乙", "辛"), ("丙", "壬"), ("丁", "癸"))}


def _compat_gan_relation(a_gan: str, b_gan: str) -> str:
    """두 일간의 관계를 사주 용어 없이 한국어로."""
    ea, eb = GAN_ELEM.get(a_gan, ""), GAN_ELEM.get(b_gan, "")
    tags: List[str] = []
    if frozenset((a_gan, b_gan)) in _CG_HAP:
        tags.append("서로 자연스레 끌어당기는 짝")
    if frozenset((a_gan, b_gan)) in _CG_CHUNG:
        tags.append("정면으로 부딪치기 쉬운 기질")
    if ea and eb:
        if ea == eb:
            tags.append("성향의 결이 비슷함")
        elif SHENG.get(ea) == eb or SHENG.get(eb) == ea:
            tags.append("한쪽이 다른 쪽을 북돋아 주는 흐름")
        elif KE.get(ea) == eb or KE.get(eb) == ea:
            tags.append("한쪽이 다른 쪽을 눌러 긴장이 생기는 흐름")
        else:
            tags.append("무난한 중립")
    return ", ".join(tags) or "중립"


def compat_all_keys() -> List[str]:
    """3,600개 (본인 일주 × 상대 일주) 순서쌍. 같은 일주 커플은 맨 뒤."""
    g = sixty_gapja()
    offsets = list(range(1, 60)) + [0]
    keys: List[str] = []
    for off in offsets:
        for i in range(60):
            keys.append(f"{g[i]}_{g[(i + off) % 60]}")
    return keys


def _compat_persona(gan: str, ji: str) -> str:
    """일간·일지 페르소나를 동물 비유·'일주' 표기 없이 한 줄로."""
    g = GAN_PERSONA.get(gan)
    j = JI_PERSONA.get(ji)
    if not g:
        return "존댓말 기본의 다정하고 현실적인 2030 감성"
    base = f"{g['페르소나']} ({g['말투']})"
    return f"{base}, {j['보정']}" if j else base


# 오행·십신·지지관계를 사주 용어 없이 '짧은 키워드'로만 준다.
# 서술구로 주면 flash-lite 가 그대로 문장에 붙여넣으므로(항목 나열식 recitation),
# 모델이 반드시 자기 문장으로 풀어 쓸 수밖에 없도록 최소 힌트만 남긴다.
_COMPAT_ELEM_TAG = {"목": "성장형", "화": "열정형", "토": "안정형",
                    "금": "결단형", "수": "유연형"}
_COMPAT_INFLUENCE_TAG = {
    "비겁": "승부욕 자극", "식상": "표현을 이끎", "재성": "성취욕 자극",
    "관성": "책임감 요구", "인성": "안정감을 줌",
}
_COMPAT_TOGETHER_TAG = {
    "복음": "리듬이 똑같아 편하나 새로움 부족", "육합": "손발이 잘 맞음",
    "충": "부딪침·변화 잦음", "파": "사소하게 삐걱댐",
    "해": "오해·뒷말로 꼬이기 쉬움", "형": "부대끼며 맞춰가야 함",
}


def _compat_together(aj: str, bj: str) -> str:
    raw = branch_relation(aj, bj)          # "육합(협력·인연)" / "복음(같은 지지) · 자형" / "무관" ...
    m = re.match(r"([가-힣]+)", raw)
    tag = _COMPAT_TOGETHER_TAG.get(m.group(1) if m else "", "끌림도 갈등도 약한 담백함")
    if "자형" in raw:
        tag += ", 닮아서 같은 약점 자극"
    return tag


def _compat_influence(dm: str, other_gan: str, other_ji: str) -> str:
    seen: List[str] = []
    for code in (calculate_sipsin(dm, other_gan, is_gan=True),
                 calculate_sipsin(dm, other_ji, is_gan=False)):
        tag = _COMPAT_INFLUENCE_TAG.get(sipsin_group(code))
        if tag and tag not in seen:
            seen.append(tag)
    return "·".join(seen) or "무난"


def _compat_item_block(key: str) -> str:
    a, b = key.split("_")
    ag, aj, bg, bj = a[0], a[1], b[0], b[1]
    me_tag = "/".join(dict.fromkeys([_COMPAT_ELEM_TAG.get(GAN_ELEM.get(ag), ""), _COMPAT_ELEM_TAG.get(JI_ELEM.get(aj), "")]))
    yo_tag = "/".join(dict.fromkeys([_COMPAT_ELEM_TAG.get(GAN_ELEM.get(bg), ""), _COMPAT_ELEM_TAG.get(JI_ELEM.get(bj), "")]))
    return "\n".join([
        f"── 키: {key} ──",
        f"- 나: {_compat_persona(ag, aj)}  [{me_tag}]",
        f"- 상대: {_compat_persona(bg, bj)}  [{yo_tag}]",
        f"- 관계 힌트(그대로 쓰지 말 것): 성향 궁합은 '{_compat_gan_relation(ag, bg)}', "
        f"함께 지내는 느낌은 '{_compat_together(aj, bj)}', "
        f"상대→나 {_compat_influence(ag, bg, bj)} / 나→상대 {_compat_influence(bg, ag, aj)}",
    ])


_COMPAT_SCHEMA_BODY = """{
    "overall": "두 사람의 전반적인 궁합과 관계가 나아갈 방향 (친근한 존댓말, 6~9문장)",
    "love": "애정·연애 궁합. 서로 사랑을 표현하고 받아들이는 방식이 어떻게 맞고 어긋나는지 (5~8문장)",
    "communication": "소통 궁합. 대화 스타일·속도·감정 전달 방식의 조화 (5~8문장)",
    "conflict": "주로 부딪히는 지점과 갈등이 드러나는 양상 (5~8문장)",
    "conflict_resolution": "갈등을 풀어가는 법. 상대의 어떤 기질을 인정하면 빨리 풀리는지 (5~8문장)",
    "economy": "돈에 대한 감각과 소비 성향의 궁합, 조율하는 법 (4~7문장)",
    "relationship_advice": "이 관계를 오래 건강하게 이어가기 위한 핵심 조언 (4~7문장)"
  }"""


def _compat_segment_prompt(items: List[Tuple[str]]) -> str:
    keys = [it[0] for it in items]
    blocks = "\n\n".join(_compat_item_block(k) for k in keys)
    return f"""아래 {len(items)}개 항목 각각에 대해 두 사람(나 기준)의 연애 궁합을 씁니다.
각 항목은 완전히 독립입니다. 한 항목 내용을 다른 항목에 복사하지 말고 근거에 맞춰 개별적으로 씁니다.

[말투·형식 규칙 — 최우선]
- 친근한 존댓말만('~해요/~예요/~입니다/~보세요/~편입니다'). 반말 금지.
- 번호·순번·목록 기호("1.", "1)", "[1]", "①", 문장 앞 "-")를 붙이지 않고 서술형 문장으로만 씁니다.
- 사주 용어 노출 절대 금지: 십신 이름(비견·겁재·식신·상관·정재·편재·정관·편관·정인·편인), 오행 이름(목·화·토·금·수)과 "○의 기운"·"바탕 기운", 지지 관계 용어(육합·복음·자형·충·형·파·해), 그리고 "일주"·"천간"·"지지"·"간지"·"갑자"·"을축" 같은 말을 한 번도 쓰지 않습니다. 그냥 "나"와 "상대"로만 지칭하고 성격은 태도·행동·감정으로만 묘사합니다.
- 참고 정보(대괄호 태그, "관계 힌트" 줄 등)는 두 사람을 이해하라고 준 메모입니다. 그 문구를 절대 그대로 옮기지 않습니다. 특히 다음을 금지합니다:
  · "나의 타고난 성향은 ~이고 몸에 밴 태도는 ~" 처럼 참고 항목을 나열·해설하는 문장
  · "성장·도전형", "안정·신뢰 지향" 처럼 가운뎃점(·)이나 슬래시(/)로 특성을 나열한 표현
  · "상대→나", "~ 자극", "관계 힌트" 등 메모의 라벨을 그대로 쓴 문장
  참고 정보는 완전히 소화한 뒤, 실제 연애 상담사가 대화하듯 100% 새 문장으로 풀어 씁니다.
- 상대나 나를 띠 동물에 빗대지 않습니다.
- 특정 날짜·나이·점수 숫자를 쓰지 않고, "오늘"·"요즘"·"이번 주"·"지금 이 시기" 같은 시점 표현도 쓰지 않습니다(타고난 궁합 설명이므로).
- 문장은 끝까지 완결해서 씁니다. "디한", "섬한"처럼 단어를 잘라 쓰지 않습니다.
- 두 사람 관계의 좋은 면과 조심할 면을 함께 담되, 마지막은 관계를 발전시키는 현실적인 방향으로 맺습니다.

[생성할 항목 — 총 {len(items)}개]

{blocks}

[출력 형식 — 아래 JSON 객체 하나만, 마크다운 펜스나 설명 없이]
- 최상위 key 는 위 '키' 문자열을 그대로 사용합니다: {', '.join(keys)}
- 각 값 구조:

{{
  "{keys[0]}": {_COMPAT_SCHEMA_BODY},
  "{keys[1] if len(keys) > 1 else '키2'}": {{ "...위와 동일 구조..." }}
}}"""


def _compat_clean(s: Any) -> Any:
    return strip_enumeration(apply_text_fixups(s, strip_time_words=True))


def _compat_coerce(entry: Any) -> Any:
    if isinstance(entry, dict) and len(entry) == 1:
        inner = next(iter(entry.values()))
        if isinstance(inner, dict) and ("overall" in inner):
            entry = inner
    if not isinstance(entry, dict):
        return entry
    return {k: _compat_clean(str(entry[k])) for k in _COMPAT_FIELDS if isinstance(entry.get(k), str)}


def _compat_valid(entry: Any) -> bool:
    return isinstance(entry, dict) and all(str(entry.get(k, "")).strip() for k in _COMPAT_FIELDS)


def _compat_texts(entry: Any) -> List[str]:
    if not isinstance(entry, dict):
        return []
    return [str(entry.get(k, "")) for k in _COMPAT_FIELDS]


def _compat_done_count(db: Dict[str, Any], all_keys: List[str]) -> int:
    return sum(1 for k in all_keys if _compat_valid(db.get(k)))


def run_compatibility(args) -> None:
    out_path = args.out or COMPATIBILITY_DB_PATH
    db = _load_json(out_path)
    all_keys = compat_all_keys()
    total = len(all_keys)                 # 3,600
    if args.only:
        all_keys = [k for k in all_keys if k == args.only or k.startswith(args.only + "_")]

    if not args.batch or args.batch < 2:
        args.batch = 10

    done = _compat_done_count(db, all_keys)
    print(f"DB: {out_path}")
    print(f"기존 완료: {done}/{total}  ({100 * done / total:.1f}%)  · 남음 {total - done}")
    budget = args.limit or len(all_keys)
    print(f"이번 청크 상한: {budget}개" + (f"  (--limit {args.limit})" if args.limit else ""))

    pending = [k for k in all_keys if args.overwrite or not _compat_valid(db.get(k))]
    seg = pending[:budget]

    if args.dry_run:
        print(f"이번 청크 대상 {len(seg)}개  예: {', '.join(seg[:6])}")
        print("dry-run 종료.")
        return
    if not seg:
        print("생성할 항목이 없습니다. (이번 범위 모두 완료)")
        return

    api_keys = load_api_keys()
    if not api_keys:
        print("[에러] GEMINI_API_KEY / GEMINI_API_KEY_1.. 미설정")
        sys.exit(1)
    models = [args.model] if args.model else list(DAILY_BATCH_MODELS)

    todo = [(k,) for k in seg]
    sub = argparse.Namespace(**vars(args))
    sub.limit = 0     # seg 에서 이미 잘랐으므로 내부 제한 없음
    _run_batched(
        sub, todo, db, out_path, api_keys,
        prompt_fn=_compat_segment_prompt,
        valid_fn=_compat_valid,
        coerce_fn=_compat_coerce,
        models=models, max_output_tokens=COMPATIBILITY_BATCH_MAX_OUTPUT_TOKENS,
        total=total, system_instruction=_COMPATIBILITY_SYSTEM,
        banmal_fn=(lambda e: _banmal_in_texts(_compat_texts(e))),
        unit="조합", count_fn=(lambda d: _compat_done_count(d, all_keys)),
        header=f"\n{'━' * 60}\n[궁합] 대상 {len(todo)}개",
    )


def run_relationship(args) -> None:
    out_path = args.out or RELATIONSHIP_DB_PATH
    db = _load_json(out_path)
    all_keys = relationship_all_keys()
    total = len(all_keys)                 # 10,980
    if args.only:
        all_keys = [k for k in all_keys if k == args.only or k.startswith(args.only + "_")]

    if not args.batch or args.batch < 2:
        args.batch = 10

    done = _rel_done_count(db, all_keys)
    print(f"DB: {out_path}")
    print(f"기존 완료: {done}/{total}  ({100 * done / total:.1f}%)  · 남음 {total - done}")
    budget = args.limit or len(all_keys)
    print(f"이번 청크 상한: {budget}개" + (f"  (--limit {args.limit})" if args.limit else ""))

    def _pending(mode: str, rtype: str) -> List[str]:
        return [k for k in all_keys
                if _rel_mode_type(k) == (mode, rtype)
                and (args.overwrite or not _rel_valid(db.get(k), mode, rtype))]

    # 이번 청크에서 처리할 (mode,rtype,keys) 슬라이스 목록. solo 3개 먼저, 그다음 couple 3유형 라운드로빈.
    plan: List[Tuple[str, str, List[str]]] = []
    left = budget
    for rtype in _REL_TYPES:
        p = _pending("solo", rtype)[:left]
        if p:
            plan.append(("solo", rtype, p)); left -= len(p)
    couple_pending = {rt: _pending("couple", rt) for rt in _REL_TYPES}
    while left > 0 and any(couple_pending.values()):
        progressed = False
        for rtype in _REL_TYPES:
            if left <= 0:
                break
            take = min(60, left, len(couple_pending[rtype]))   # 한 유형 최대 60개(=6배치)씩 라운드로빈
            if take <= 0:
                continue
            plan.append(("couple", rtype, couple_pending[rtype][:take]))
            couple_pending[rtype] = couple_pending[rtype][take:]
            left -= take
            progressed = True
        if not progressed:
            break

    if args.dry_run:
        from collections import Counter
        c = Counter((m, t) for m, t, ks in plan for _ in ks)
        print(f"이번 청크 대상 {sum(len(ks) for _, _, ks in plan)}개 구성: {dict(c)}")
        for m, t, ks in plan:
            print(f"  [{m} · {_REL_TYPE_KO[t]}] {len(ks)}개  예: {', '.join(ks[:4])}")
        print("dry-run 종료.")
        return
    if not plan:
        print("생성할 항목이 없습니다. (이번 범위 모두 완료)")
        return

    api_keys = load_api_keys()
    if not api_keys:
        print("[에러] GEMINI_API_KEY / GEMINI_API_KEY_1.. 미설정")
        sys.exit(1)
    models = [args.model] if args.model else list(DAILY_BATCH_MODELS)
    t0 = time.time()
    initial = len(db)

    for mode, rtype, seg in plan:
        todo = [(k,) for k in seg]
        sub = argparse.Namespace(**vars(args))
        sub.limit = 0     # plan 에서 이미 잘랐으므로 세그먼트 내부 제한 없음
        _run_batched(
            sub, todo, db, out_path, api_keys,
            prompt_fn=(lambda items, _m=mode, _t=rtype: _rel_segment_prompt(_m, _t, items)),
            valid_fn=(lambda e, _m=mode, _t=rtype: _rel_valid(e, _m, _t)),
            coerce_fn=(lambda e, _m=mode, _t=rtype: _rel_coerce(e, _m, _t)),
            models=models, max_output_tokens=RELATIONSHIP_BATCH_MAX_OUTPUT_TOKENS,
            total=total, system_instruction=_RELATIONSHIP_SYSTEM,
            banmal_fn=(lambda e: _banmal_in_texts(_rel_texts(e))),
            unit="조합", count_fn=(lambda d: _rel_done_count(d, all_keys)),
            header=f"\n{'━' * 60}\n[{mode} · {_REL_TYPE_KO[rtype]}] 대상 {len(todo)}개",
        )

    final_done = _rel_done_count(db, all_keys)
    made = len(db) - initial
    dt = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"이번 청크: {made}개 생성 · {dt:.0f}s 소요 · 개당 평균 {dt / max(made, 1):.1f}s")
    print(f"전체 진행: {final_done}/{total}  ({100 * final_done / total:.1f}%)  · 남음 {total - final_done}")


# ─────────────────────────────── REUNION CHARM (재회운 '상대에게 어필할 나의 매력')
# 재회 국면에서만 쓰는 사람 중심(본인 일주 60개) 서술 1필드.
# 키 = 일주 간지 한자 2자(예 "辛卯"). 값 = {"your_charm": str, "_model": str}.
# 궁합/관계 DB 와 별개 파일(reunion_charm_db.json)로 두고, 재회운 응답에만 병합한다.
REUNION_CHARM_DB_PATH = os.path.join(_ROOT, "domains", "relationship", "data", "reunion_charm_db.json")
REUNION_CHARM_MAX_OUTPUT_TOKENS = 16384

_REUNION_CHARM_SYSTEM = (
    "당신은 2030 세대를 위한 관계 상담가입니다. 제공된 성향 정보만 근거로 서술합니다. "
    "사주 용어(십신·오행·합충·일주·간지·천간·지지)는 절대 쓰지 않고 태도·행동·감정으로만 묘사합니다. "
    "친근한 존댓말만 씁니다. 유효한 JSON 만 출력합니다."
)


def _reunion_charm_block(ganji: str) -> str:
    dm, dbc = ganji[0], ganji[1]
    me_tag = "/".join(dict.fromkeys([
        _COMPAT_ELEM_TAG.get(GAN_ELEM.get(dm), ""), _COMPAT_ELEM_TAG.get(JI_ELEM.get(dbc), ""),
    ]))
    return "\n".join([
        f"── 키: {ganji} ──",
        _compat_persona(dm, dbc) + (f"  [{me_tag}]" if me_tag.strip("/") else ""),
    ])


def _reunion_charm_prompt(items: List[Tuple[str]]) -> str:
    keys = [it[0] for it in items]
    blocks = "\n\n".join(_reunion_charm_block(k) for k in keys)
    return f"""아래 {len(items)}개 항목 각각에 대해, "옛 인연이 당신에게 다시 끌리는 이유 — 재회 국면에서 상대의 마음을 다시 흔드는 당신만의 매력"을 씁니다.
각 항목은 완전히 독립입니다. 한 항목 내용을 다른 항목에 복사하지 말고 성향에 맞춰 개별적으로 씁니다.

[담아야 할 것]
- 헤어진 상대가 당신을 떠올렸을 때 가장 그리워할 법한 지점(대화·분위기·태도·감정을 다루는 방식 등)
- 다시 만났을 때 상대가 "역시 이 사람" 하고 느낄 당신의 강점
- 그 매력을 재회 과정에서 자연스럽게 드러내는 법 (연락·태도·거리 조절)
- 과하게 쓰면 오히려 부담이 되는 부분과 그 조절

[말투·형식 규칙 — 최우선]
- 친근한 존댓말만('~해요/~예요/~입니다/~보세요/~편입니다'). 반말 금지.
- 번호·순번·목록 기호("1.", "1)", "[1]", "①", 문장 앞 "-")를 붙이지 않고 서술형 문장으로만.
- 사주 용어 노출 금지: 십신·오행·합충·배우자성·도화는 물론 "일주"·"갑자일주"·"간지"·"천간"·"지지" 같은 말도 쓰지 않습니다. "나"와 "상대(옛 인연)"로만 지칭하고 성격은 태도·행동·감정으로만 묘사합니다.
- 특정 날짜·연도·나이를 단정하지 않고, "오늘"·"요즘"·"이번 주" 같은 시점 표현도 쓰지 않습니다(타고난 매력 설명이므로).
- 참고로 준 키워드([성장형] 등)를 문장에 그대로 붙여넣지 말고 반드시 자기 문장으로 풀어 씁니다.

[생성할 항목 — 총 {len(items)}개]

{blocks}

[출력 형식 — 아래 JSON 객체 하나만, 마크다운 펜스나 설명 없이]
- 최상위 key 는 위 '키' 문자열 그대로: {', '.join(keys)}
- 각 값 구조:

{{
  "{keys[0]}": {{ "your_charm": "위 내용을 담은 깊이 있고 풍성한 서술 (친근한 존댓말, 5~7문장)" }},
  "{keys[1] if len(keys) > 1 else '키2'}": {{ "your_charm": "..." }}
}}"""


def _reunion_charm_valid(entry: Any) -> bool:
    return isinstance(entry, dict) and len(str(entry.get("your_charm", "")).strip()) >= 120


def _reunion_charm_coerce(entry: Any) -> Any:
    if isinstance(entry, dict) and "your_charm" in entry:
        entry["your_charm"] = _rel_clean(str(entry["your_charm"]))
    return entry


def run_reunion_charm(args) -> None:
    out_path = args.out or REUNION_CHARM_DB_PATH
    db = _load_json(out_path)
    all_keys = sixty_gapja()
    total = len(all_keys)                 # 60
    if args.only:
        all_keys = [k for k in all_keys if k == args.only]

    if not args.batch or args.batch < 2:
        args.batch = 10

    done = sum(1 for k in all_keys if _reunion_charm_valid(db.get(k)))
    print(f"DB: {out_path}")
    print(f"기존 완료: {done}/{total}  ({100 * done / total:.1f}%)  · 남음 {total - done}")
    budget = args.limit or len(all_keys)

    pending = [k for k in all_keys if args.overwrite or not _reunion_charm_valid(db.get(k))]
    seg = pending[:budget]
    if args.dry_run:
        print(f"이번 청크 대상 {len(seg)}개  예: {', '.join(seg[:8])}")
        print("dry-run 종료.")
        return
    if not seg:
        print("생성할 항목이 없습니다. (이번 범위 모두 완료)")
        return

    api_keys = load_api_keys()
    if not api_keys:
        print("[에러] GEMINI_API_KEY / GEMINI_API_KEY_1.. 미설정")
        sys.exit(1)
    models = [args.model] if args.model else list(DAILY_BATCH_MODELS)

    todo = [(k,) for k in seg]
    sub = argparse.Namespace(**vars(args))
    sub.limit = 0
    _run_batched(
        sub, todo, db, out_path, api_keys,
        prompt_fn=_reunion_charm_prompt,
        valid_fn=_reunion_charm_valid,
        coerce_fn=_reunion_charm_coerce,
        models=models, max_output_tokens=REUNION_CHARM_MAX_OUTPUT_TOKENS,
        total=total, system_instruction=_REUNION_CHARM_SYSTEM,
        banmal_fn=(lambda e: _banmal_in_texts([str(e.get("your_charm", ""))])),
        unit="일주", count_fn=(lambda d: sum(1 for k in all_keys if _reunion_charm_valid(d.get(k)))),
        header=f"\n{'━' * 60}\n[재회운 매력] 대상 {len(todo)}개",
    )

    final_cnt = sum(1 for k in all_keys if _reunion_charm_valid(db.get(k)))
    print(f"\n{'=' * 60}")
    print(f"완료 {final_cnt}/{total}  ({100 * final_cnt / total:.1f}%)  → {out_path}")


def run_daily(args) -> None:
    out_path = args.out or DAILY_DB_PATH
    db = _load_json(out_path)
    print(f"DB: {out_path}")
    print(f"기존 항목: {len(db)}개 / 목표 3600개")

    models = _resolve_models(args)
    primary = models[0]
    env_m = primary  # 로그 표기용(“via <model>” 는 primary 와 다를 때만 붙임)

    targets = daily_keys(args.only)
    if args.regen_stale:
        # 이미 있으나 primary 모델이 아닌(또는 _model 없는) 항목만 다시 생성 = 일관성 정리
        todo = [t for t in targets
                if t[0] in db and db[t[0]].get("_model") != primary]
        stale_models = sorted({db[t[0]].get("_model") or "(없음)" for t in todo})
        print(f"[--regen-stale] primary={primary} 아닌 기존 항목만 재생성: {len(todo)}개"
              + (f"  (대상 모델: {', '.join(stale_models)})" if todo else ""))
    else:
        todo = [t for t in targets if args.overwrite or t[0] not in db]
        print(f"이번 실행 대상: {len(todo)}개"
              + (f" (--limit {args.limit})" if args.limit else "")
              + (" [--overwrite]" if args.overwrite else ""))
    if args.dry_run:
        for key, d, i in todo[: args.limit or 20]:
            print(f"  - {key}  ({d} 일주 / {i} 일진 / {branch_relation(d[1], i[1])})")
        print("dry-run 종료.")
        return
    if not todo:
        print("생성할 항목이 없습니다. (모두 완료)")
        return

    keys = load_api_keys()
    if not keys:
        print("[에러] GEMINI_API_KEY / GEMINI_API_KEY_1.. 미설정")
        sys.exit(1)

    if args.batch and args.batch > 1:
        run_daily_batched(args, todo, db, out_path, keys)
        return

    if args.workers and args.workers > 1:
        run_daily_concurrent(args, todo, db, out_path, models, keys)
        return

    rotator = Rotator(keys, models)
    model = make_model(rotator.current_model, rotator.current_key)
    print(f"API 키 {len(keys)}개 × 모델 {len(models)}개 → 슬롯 {len(rotator)}개 순환")
    print(f"모델 우선순위: {', '.join(models)}\n")

    made, failed, banmal = 0, [], []
    stopped_by_quota = False
    stopped_by_credits = False
    total_todo = len(todo)
    t0 = time.time()
    try:
        for idx, (key, d, i) in enumerate(todo, 1):
            if args.limit and made >= args.limit:
                print(f"\n--limit {args.limit} 도달 — 중단.")
                break
            entry = None
            gen_err: Optional[Exception] = None
            used_model: Optional[str] = None
            rl_streak = 0                       # 연속 단기(rate-limit) 회전 수
            attempts = 0
            max_attempts = len(rotator) * 3 + 10
            # 이 항목 생성. 슬롯 = (키 × 모델):
            #  - PerDay 소진 → 그 슬롯만 제외         (같은 키의 다른 모델은 계속)
            #  - 키 무효     → 그 키의 모든 슬롯 제외
            #  - 모델 404    → 그 모델의 모든 슬롯 제외
            #  - 단기 429    → 제외 없이 다음 슬롯으로 회전, 한 바퀴 다 돌면 잠깐 대기
            while attempts < max_attempts:
                attempts += 1
                try:
                    entry = generate_one(model, daily_prompt(d, i), args.max_retries, args.delay)
                    used_model = rotator.current_model
                    break
                except CreditsDepleted as e:
                    gen_err = e
                    stopped_by_credits = True
                    break
                except DailyQuotaExceeded as e:
                    gen_err = e
                    rl_streak = 0
                    slot = rotator.label
                    rotator.kill_current()
                    print(f"    ⚠ {slot} 오늘 소진(PerDay) → 슬롯 제외  [{rotator.status()}]")
                    if not rotator.advance():
                        stopped_by_quota = True
                        break
                    model = make_model(rotator.current_model, rotator.current_key)
                    continue
                except InvalidApiKey as e:
                    gen_err = e
                    rl_streak = 0
                    slot = rotator.label
                    rotator.kill_current_key()
                    print(f"    ⚠ {slot} 키 무효/권한없음 → 이 키 전체 제외  [{rotator.status()}]")
                    if not rotator.advance():
                        break
                    model = make_model(rotator.current_model, rotator.current_key)
                    continue
                except ModelUnavailable as e:
                    gen_err = e
                    rl_streak = 0
                    bad_model = rotator.current_model
                    rotator.kill_current_model()
                    print(f"    ⚠ 모델 {bad_model} 사용불가 → 이 모델 전체 제외  [{rotator.status()}]")
                    if not rotator.advance():
                        break
                    model = make_model(rotator.current_model, rotator.current_key)
                    continue
                except RateLimited as e:
                    gen_err = e
                    rl_streak += 1
                    if rl_streak >= max(rotator.alive_count, 1):
                        wait = min(max(e.retry_after or 15, 5), 60)
                        print(f"    ⏳ 살아있는 슬롯이 모두 단기 한도 → {wait}s 대기  [{rotator.status()}]")
                        time.sleep(wait)
                        rl_streak = 0
                    rotator.advance()
                    model = make_model(rotator.current_model, rotator.current_key)
                    continue
                except Exception as e:  # noqa: BLE001
                    gen_err = e
                    break

            if stopped_by_credits:
                print(f"\n[전체중단] 결제 프리페이 크레딧 소진 — 재시도 무의미: {str(gen_err)[:200]}")
                print(f"  → {key} 직전까지 저장됨. 충전 후 같은 명령으로 재실행하면 이어서 진행합니다.")
                break

            if rotator.alive_count == 0:
                if stopped_by_quota:
                    print(f"\n[전체 소진] 모든 (키 × 모델) 슬롯이 오늘 한도(PerDay)에 도달했습니다.")
                    print(f"  → {key} 직전까지 저장됨. 한도 리셋(태평양시 자정) 후 "
                          f"같은 명령으로 이어서 진행합니다.")
                else:
                    print(f"\n[중단] 사용 가능한 슬롯이 없습니다: {str(gen_err)[:180]}")
                break

            if entry is None:
                print(f"[{idx}/{total_todo}] {key}  ✗ 실패({attempts}회 시도): {str(gen_err)[:180]}")
                failed.append(key)
                continue

            if not daily_valid(entry):
                print(f"[{idx}/{total_todo}] {key}  ✗ 스키마 불량(키 누락 등) → 건너뜀")
                failed.append(key)
                continue

            if used_model:
                entry["_model"] = used_model      # 어떤 모델이 만든 항목인지 기록
            db[key] = entry
            _atomic_write_json(out_path, db)   # ← 매 항목마다 체크포인트 저장
            made += 1
            flag = ""
            if _has_banmal(entry):
                banmal.append(key)
                flag = "  ⚠ 반말 의심"
            mtag = f" via {used_model}" if used_model and used_model != env_m else ""
            print(f"[{idx}/{total_todo}] {key}  ✓ "
                  f"(전체 {entry['overall_score']} / 돈 {entry['money_score']} / "
                  f"애정 {entry['love_score']} / 일·학업 {entry['work_study_score']}){mtag}{flag}")

            if made % 25 == 0:
                elapsed = time.time() - t0
                rate = elapsed / max(made, 1)
                remain = (3600 - len(db)) * rate
                print(f"  ── 진행: DB {len(db)}/3600 완료 · 이번 실행 {made}개 "
                      f"· 평균 {rate:.1f}s/건 · 남은 예상 {remain / 3600:.1f}h ──")

            if not (args.limit and made >= args.limit):
                time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\n[중단] Ctrl-C — 여기까지 저장됨. 다시 실행하면 이어서 진행합니다.")

    dt = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"이번 실행: {made}개 생성 · 실패 {len(failed)}개 · 반말 의심 {len(banmal)}개 · {dt:.0f}s 소요")
    print(f"DB 총 {len(db)}/3600  ({100 * len(db) / 3600:.1f}%)  → {out_path}")
    if stopped_by_credits:
        print("상태: 결제 프리페이 크레딧 소진으로 중단됨. 충전 후 같은 명령으로 재실행하세요.")
    elif stopped_by_quota:
        print("상태: 일일 할당량으로 중단됨. 내일 재실행하세요.")
    elif len(db) >= 3600:
        print("상태: 전체 3600개 생성 완료 🎉")
    else:
        print("상태: 아직 미완료. 같은 명령을 다시 실행하면 이어서 진행합니다.")
    if failed:
        print(f"실패 키 {len(failed)}개(재실행 시 자동 재시도): " + ", ".join(failed[:30])
              + (" ..." if len(failed) > 30 else ""))
    if banmal:
        print(f"반말 의심 키 {len(banmal)}개(검토 후 필요 시 --overwrite --only 로 재생성): "
              + ", ".join(banmal[:30]) + (" ..." if len(banmal) > 30 else ""))


# ─────────────────────────────────────────────────────────── main

def main() -> None:
    p = argparse.ArgumentParser(description="사전 생성 콘텐츠 DB 빌더")
    p.add_argument("--domain",
                   choices=["daily", "personality", "relationship", "compatibility", "reunion_charm"],
                   default="daily",
                   help="생성 도메인 (기본: daily). personality=일주 60 성격/적성 · "
                        "relationship=재회/짝사랑/결혼운 10,980조합(--limit 으로 청크 진행) · "
                        "compatibility=궁합 3,600조합(일주쌍, --limit 으로 청크 진행) · "
                        "reunion_charm=재회운 '나의 매력' 일주 60")
    p.add_argument("--limit", type=int, default=0, help="이번 실행에서 새로 생성할 최대 개수 (0=제한 없음)")
    p.add_argument("--only", type=str, default=None,
                   help="특정 키만 생성 (daily: 戊辰_乙巳 / personality: 戊辰)")
    p.add_argument("--overwrite", action="store_true", help="이미 있는 키도 다시 생성")
    p.add_argument("--delay", type=float, default=1.0, help="호출 간 대기 초 (기본 1.0)")
    p.add_argument("--max-retries", type=int, default=5, help="호출당 최대 재시도 횟수 (기본 5)")
    p.add_argument("--out", type=str, default=None, help="출력 JSON 경로 (기본: 도메인별 기본 경로)")
    p.add_argument("--model", type=str, default=None,
                   help="이 모델 하나만 사용 (모델 순환 끔)")
    p.add_argument("--no-model-rotate", action="store_true",
                   help="모델 순환 없이 운영 모델(GEMINI_MODEL_NAME) 하나만 사용")
    p.add_argument("--regen-stale", action="store_true",
                   help="이미 있으나 최우선 모델(--model)로 만들어지지 않은 항목만 재생성 (일관성 정리)")
    p.add_argument("--workers", type=int, default=1,
                   help="병렬 워커 수 (기본 1=순차). 2 이상이면 워커마다 키 1개씩 고정 배정해 동시 생성 "
                        "(모델 로테이션 없이 --model/최우선 모델 고정)")
    p.add_argument("--batch", type=int, default=1,
                   help="1회 호출당 조합 개수 (기본 1). 2 이상이면 배치 비용절감 모드: "
                        f"모델 {DAILY_BATCH_MODELS[0]} 고정, 1회 호출로 여러 조합 생성. "
                        "권장 10. (--workers 보다 우선)")
    p.add_argument("--max-days", type=int, default=10,
                   help="배치 모드에서 모든 키가 일일 한도 소진 시, 태평양시 자정까지 대기 후 "
                        "재개하는 것을 최대 며칠까지 반복할지 (기본 10)")
    p.add_argument("--dry-run", action="store_true", help="생성 없이 대상 목록만 출력")
    args = p.parse_args()

    if args.domain == "daily":
        run_daily(args)
    elif args.domain == "personality":
        run_personality(args)
    elif args.domain == "relationship":
        run_relationship(args)
    elif args.domain == "compatibility":
        run_compatibility(args)
    elif args.domain == "reunion_charm":
        run_reunion_charm(args)


if __name__ == "__main__":
    main()
