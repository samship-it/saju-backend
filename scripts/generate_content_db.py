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
import re
import sys
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
except Exception as e:  # pragma: no cover
    print(f"google-generativeai 임포트 실패: {e}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────── 공통

DAILY_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "domains", "daily", "data", "daily_db.json",
)

_SYSTEM = (
    "당신은 2030 세대를 위한 사주 운세 앱의 화자입니다. "
    "제공된 '내 일주'와 '오늘 일진' 관계 데이터만 근거로 오늘의 운세를 생성합니다. "
    "말투는 예외 없이 '친근한 존댓말'로만 씁니다. 모든 문장은 '~해요', '~예요', '~입니다', "
    "'~보세요', '~됩니다' 같은 존댓말 어미로 끝냅니다. '~해', '~야', '~봐', '~자', '~거야' 같은 "
    "반말 어미는 단 한 번도 쓰지 않습니다. "
    "반드시 아래에 지정된 키를 하나도 빠짐없이 포함한 유효한 JSON 하나만 출력하고, "
    "Markdown 펜스(```)나 그 밖의 설명 문장은 절대 쓰지 않습니다."
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

def make_model(model_name: str, api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=_SYSTEM,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.0,
            "top_p": 1.0,
        },
    )


def generate_one(model, prompt: str, max_retries: int, base_delay: float) -> dict:
    """성공 시 dict 반환, 끝까지 실패하면 예외 raise (폴백 저장 방지)."""
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            # 응답 없이 무한 대기하는 것을 막는다(별칭이 무거운 모델로 연결된 경우 등).
            resp = model.generate_content(prompt, request_options={"timeout": 90})
            return _extract_json(resp.text)
        except Exception as e:  # noqa: BLE001
            last_err = e
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

    rotator = Rotator(keys, models)
    model = make_model(rotator.current_model, rotator.current_key)
    print(f"API 키 {len(keys)}개 × 모델 {len(models)}개 → 슬롯 {len(rotator)}개 순환")
    print(f"모델 우선순위: {', '.join(models)}\n")

    made, failed, banmal = 0, [], []
    stopped_by_quota = False
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
    if stopped_by_quota:
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
    p.add_argument("--domain", choices=["daily"], default="daily", help="생성 도메인 (기본: daily)")
    p.add_argument("--limit", type=int, default=0, help="이번 실행에서 새로 생성할 최대 개수 (0=제한 없음)")
    p.add_argument("--only", type=str, default=None, help="특정 키만 생성 (예: 戊辰_乙巳)")
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
    p.add_argument("--dry-run", action="store_true", help="생성 없이 대상 목록만 출력")
    args = p.parse_args()

    if args.domain == "daily":
        run_daily(args)


if __name__ == "__main__":
    main()
