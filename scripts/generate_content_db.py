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
    GAN_ELEM, JI_ELEM, JIJANGGAN,
)
from core.sipsin import calculate_sipsin  # noqa: E402
from shared.persona_map import persona_prompt  # noqa: E402
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

    # 공백 정규화: 일부 응답이 문장마다 \n 을 넣는다 → 한 줄 흐름으로 통일(런타임 paragraphize 가 처리)
    def _flat(s: Any) -> Any:
        return re.sub(r"\s+", " ", s).strip() if isinstance(s, str) else s
    if isinstance(entry.get("summary"), dict):
        entry["summary"] = {k: _flat(v) for k, v in entry["summary"].items()}
    if isinstance(entry.get("recommended_action"), str):
        entry["recommended_action"] = _flat(entry["recommended_action"])
    if isinstance(entry.get("keywords"), list):
        entry["keywords"] = [_flat(k) for k in entry["keywords"]]
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
    """그룹(6필드) 응답 정규화. 모델이 한 겹 더 감쌌으면(예: {"character": {...}}) 벗겨내고 공백 정리."""
    if isinstance(entry, dict) and len(entry) == 1:
        inner = next(iter(entry.values()))
        if isinstance(inner, dict) and any(k in inner for k in field_keys):
            entry = inner
    if not isinstance(entry, dict):
        return entry
    return {k: (re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)
            for k, v in entry.items()}


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
    p.add_argument("--domain", choices=["daily", "personality"], default="daily",
                   help="생성 도메인 (기본: daily). personality = 일주 60가지 성격/적성")
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


if __name__ == "__main__":
    main()
