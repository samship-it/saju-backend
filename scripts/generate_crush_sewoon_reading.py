"""단독 짝사랑 종합운. 60갑자 × 요청 연도 세운.

요청 경로에서 호출하지 않는다. 년주·월주·시주·신강·대운은 같은 일주의 사람마다
달라서 이 키에 넣지 않는다. 결과는 domains/relationship/data/crush_year_reading_db.json.

  python scripts/generate_crush_sewoon_reading.py --year 2026
  python scripts/generate_crush_sewoon_reading.py --year 2026 --limit 5
"""
import argparse
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402,F401
from core.constants import GAN_ELEM, GAN_YANG, JI_ELEM, JI_YANG
from core.daewoon import branch_relation, get_seewoon_list
from core.saju_base import sipsin_of_ganji
from core.sipsin import calculate_sipsin, sipsin_group
from scripts.generate_content_db import (  # noqa: E402
    CreditsDepleted,
    DailyQuotaExceeded,
    InvalidApiKey,
    ModelUnavailable,
    RateLimited,
    generate_one,
    load_api_keys,
    make_model,
    sixty_gapja,
)

_DATA = os.path.join(_ROOT, "domains", "relationship", "data", "crush_year_reading_db.json")
_WORK = os.path.join(_ROOT, "scripts", "_crush_year_work.json")
_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
)
_LEANINGS = ("진전", "새인연", "자중")
_ANALYSIS_SYSTEM = (
    "당신은 명리 계산 결과를 짝사랑의 올해 심리로 읽는 분석가입니다. "
    "고객 문장은 쓰지 않습니다. 입력된 사실만 사용합니다.\n"
    "이 키는 일주 하나입니다. 년주, 월주, 시주, 원국 전체의 오행 개수와 가중치, "
    "신강, 신약, 대운은 같은 일주의 사람마다 달라 여기에 없습니다. 추정하지 않습니다.\n"
    "세운 간지의 오행을 뜨거움, 차가움, 열정으로 바꾸지 않습니다.\n"
    "십신 하나를 하나의 행동에 고정하지 않습니다. "
    "식신은 말이 많아지는 것, 재성은 약속, 관성은 신중함, 인성은 기다림, 비겁은 내 속도가 아닙니다.\n"
    "지지 관계를 사건으로 바꾸지 않습니다. "
    "육합은 둘만의 시간이 아니고, 충과 해는 시간표가 어긋나는 장면이 아닙니다. "
    "관계가 무관이면 관계에서 나온 막힘이나 풀림을 만들지 않습니다.\n"
    "십신의 개수로 연애가 좋은지 나쁜지 점수를 매기지 않습니다. "
    "일지 십신과 세운 십신이 같은 계열인지 다른 계열인지만 대조합니다.\n"
    "기울기는 다음 순서로만 고릅니다. 좋고 나쁨이 아니라 시선이 어디에 걸리는지입니다. "
    "관계가 충, 파, 해이면 자중입니다. "
    "관계가 자형이나 같은 지지이면, 일지 계열과 세운 계열이 같을 때 진전, 다를 때 자중입니다. "
    "관계가 육합이면 진전입니다. 만남이 생긴다는 뜻이 아닙니다. "
    "관계가 무관이고 일지 계열과 세운 계열이 같으면 진전, 다르면 새인연입니다. "
    "무관인데 자중을 고르지 않습니다. "
    "진전은 이미 마음에 둔 사람 쪽으로 시선이 머무는 해이고, 상대가 받아 준다는 뜻이 아닙니다. "
    "새인연은 마음에 둔 사람이 있어도 새로운 사람이 생길 가능성이 있는 해입니다. "
    "이미 마음이 옮겨 갔거나 좋아하는 사람에게서 벗어났다고 쓰지 않습니다. "
    "새 사람이 보이지 않아도 마음에 둔 사람은 그대로라는 말이 남아야 합니다. "
    "자중은 마음이 있어도 그 마음을 앞으로 밀지 않는 해입니다.\n"
    "JSON만 출력합니다. 키는 leaning, relation_role, reasoning 입니다. "
    "relation_role 은 none, limits, overlaps 중 하나입니다. 무관이면 none 입니다. "
    "reasoning 은 2~4문장이고 용어를 써도 됩니다. 약속, 만남, 고백, 상대의 호감은 쓰지 않습니다."
)
_WRITER_SYSTEM = (
    "당신은 2030이 읽는 짝사랑 글의 작성자입니다. 분석가가 고른 기울기와 사실만 고객 문단으로 옮깁니다. "
    "분석을 다시 하지 않습니다.\n"
    "한 문단입니다. 보통 3~5문장이고, 같은 말을 반복해서 늘리거나 짧게 자르지 않습니다. "
    "첫 문장을 '올해는'으로 시작하지 않습니다. "
    "어미는 해요, 예요, 이에요만 씁니다. "
    "입니다, 합니다, 습니다, 하세요, 됩니다, 거든요, 답니다, 네요, 보세요는 쓰지 않습니다.\n"
    "사주 용어, 간지, 오행 이름, 신강, 신약, 용신을 쓰지 않습니다. "
    "뜨거움, 열정, 타오름, 에너지, 흐름, 기류, 결을 쓰지 않습니다. "
    "둘만의 시간, 시간표, 접점, 일정이 어긋남, 부딪힘, 온기, 두 사람 사이를 쓰지 않습니다.\n"
    "상대가 나를 좋아한다, 시선을 준다, 고백이 통한다, 사귀게 된다, 만남이 생긴다는 말을 쓰지 않습니다. "
    "아직 없는 사건을 만들지 않습니다. 누군가 나타나거나, 일이 어긋나거나, 거리가 좁혀지거나, 마음이 상대에게 닿는 장면은 쓰지 않습니다. 내 시선과 내 마음만 씁니다.\n"
    "기울기가 진전이면 이미 마음에 둔 사람 쪽으로 마음이 움직이는 쪽임을 드러냅니다. "
    "새인연이면 새로운 사람이 생길 가능성을 쓰고, 이미 관심이 옮겨 갔다고 쓰지 않습니다. "
    "눈에 들어오는 사람이 없을 때는 마음에 둔 사람이 그대로라는 말도 남깁니다. "
    "자중이면 나서지 못하고 지키거나 멈추는 쪽임을 드러냅니다. "
    "앞 문장이 뒤 문장의 이유가 되게 잇습니다. 한 문단 안에서 다가가는 마음과 멈추는 마음을 이유 없이 같이 두지 않습니다. "
    "일간의 성격 소개로 시작하지 않습니다. "
    "조언으로 끝내지 않습니다. '편이', '필요해요', '방법이에요', '길이에요', '유익해요', '마음 편해요'를 쓰지 않습니다. "
    "'지켜보는 편', '제자리', '관망', '한 걸음', '가만히', '추이', '조심스러'를 쓰지 않습니다.\n"
    "JSON만 출력합니다. 키는 overall 하나입니다."
)
_REVIEW_SYSTEM = (
    "당신은 이 글을 쓰지 않은 교정자입니다. 점수나 칭찬은 쓰지 않습니다. "
    "문제가 있으면 글에 실제로 있는 구절을 quote 로 옮기고, 없으면 problems 를 빈 배열로 둡니다.\n"
    "볼 것: 기울기와 글의 방향이 같은지, 없는 사건이나 상대의 마음이 있는지, "
    "앞뒤 심리가 이유 없이 충돌하는지, 사주 용어와 번역투와 비문이 있는지, "
    "같은 뜻이 반복되는지, 뜨거운 감정이나 시간표나 둘만의 시간으로 번역됐는지.\n"
    "JSON만 출력합니다. 키는 pass, direction, direction_sentence, problems 입니다. "
    "direction 은 진전, 새인연, 자중 중 하나입니다. "
    "direction_sentence 는 overall 안의 문장을 그대로 옮깁니다. "
    "problems 의 각 항목은 quote, why 입니다."
)
_TERMS = (
    "비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "정인", "편인",
    "비겁", "식상", "재성", "관성", "인성", "신강", "신약", "중화", "용신", "희신", "기신",
    "십신", "오행", "일주", "간지", "천간", "지지", "세운", "원국", "대운",
    "육합", "삼합", "반합", "방합", "자형", "복음", "도화",
    "에너지", "흐름", "기류", "결이", "뜨겁", "열정", "타오", "둘만", "단둘",
    "시간표", "접점", "일정이 어긋",
)
_GANJI = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
_PREDICT = (
    "성사", "사귀게", "이루어질", "고백을 받", "좋아해 줄", "호감을 느",
    "상대가 나를", "상대의 마음", "상대도 마음", "시선을 기다", "만나게 돼",
)
_VOICE = ("입니다", "합니다", "습니다", "하세요", "됩니다", "거든요", "답니다", "네요", "저도", "보세요", "해보세요")
_MARK = {
    "진전": ("마음에 둔", "마음에 품", "그 사람", "좋아하는 사람"),
    "새인연": ("다른 사람", "새 사람", "새로운 사람", "새로운 인연"),
    "자중": ("밀지 않", "밀지 못", "두지 않", "삼키", "말을 아", "멈추", "멈춰", "자중"),
}
_TEMPLATE = (
    "지켜보는 편", "제자리", "마음 편", "유익해", "가장 좋은", "관망",
    "한 걸음", "조심스러", "가만히", "추이를", "편이", "필요해요", "방법이에요", "길이에요",
    "부딪", "마찰", "자극", "정적", "좁혀", "상대에게 닿", "다가오는 사람", "온기", "두 사람",
    "들어온", "불쑥", "어긋나는 일", "뜻대로 움직", "제 마음", "제 시선", "제 모습",
)
_HANGUL = re.compile(r"[가-힣]")


def _has_term(text: str, term: str) -> bool:
    if len(term) >= 3:
        return term in text
    return re.search(rf"(?<![가-힣]){re.escape(term)}", text) is not None
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _save_json(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _expected_leaning(facts: dict) -> str:
    """시선이 걸리는 위치. 십신을 행동으로 바꾸거나 좋고 나쁨을 점수 내지는 않는다."""
    relation = facts["relation"]
    same = facts["branch_group"] == facts["sewoon_gan_group"]
    if relation.startswith(("충", "파", "해")):
        return "자중"
    if "자형" in relation or relation.startswith("복음"):
        return "진전" if same else "자중"
    if relation.startswith("육합"):
        return "진전"
    return "진전" if same else "새인연"


def _facts(ganji: str, year: int, sewoon: str) -> dict:
    stem, branch = ganji[0], ganji[1]
    se = sipsin_of_ganji(stem, sewoon)
    branch_god = calculate_sipsin(stem, branch, is_gan=False)
    return {
        "day_ganji": ganji,
        "stem": stem,
        "stem_elem": GAN_ELEM.get(stem, ""),
        "stem_yy": "양" if GAN_YANG.get(stem, True) else "음",
        "branch": branch,
        "branch_elem": JI_ELEM.get(branch, ""),
        "branch_yy": "양" if JI_YANG.get(branch, True) else "음",
        "branch_sipsin": branch_god,
        "branch_group": sipsin_group(branch_god),
        "sewoon": sewoon,
        "sewoon_gan_sipsin": se.get("gan") or "",
        "sewoon_ji_sipsin": se.get("ji") or "",
        "sewoon_gan_group": sipsin_group(se.get("gan") or ""),
        "sewoon_ji_group": sipsin_group(se.get("ji") or ""),
        "relation": branch_relation(branch, sewoon[1]),
        "year": year,
        "omitted": ["년주", "월주", "시주", "오행 총합", "오행 가중치", "신강", "신약", "대운"],
    }


def _analysis_prompt(facts: dict) -> str:
    same = "같다" if facts["branch_group"] == facts["sewoon_gan_group"] else "다르다"
    return f"""요청 연도 {facts['year']}. 세운 {facts['sewoon']}.
일주 {facts['day_ganji']}.
일간 {facts['stem']} / {facts['stem_elem']} / {facts['stem_yy']}.
일지 {facts['branch']} / {facts['branch_elem']} / {facts['branch_yy']}.
일지 십신 {facts['branch_sipsin']} (계열 {facts['branch_group']}).
세운 천간 십신 {facts['sewoon_gan_sipsin']} (계열 {facts['sewoon_gan_group']}).
세운 지지 십신 {facts['sewoon_ji_sipsin']} (계열 {facts['sewoon_ji_group']}).
일지와 세운 지지의 관계: {facts['relation']}.
일지 계열과 세운 천간 계열은 {same}.
이 키의 기울기: {_expected_leaning(facts)}. 다른 기울기를 고르지 마세요.
없는 데이터: {', '.join(facts['omitted'])}.
"""


def _writer_prompt(facts: dict, analysis: dict, avoid: str = "") -> str:
    extra = f"\n이전 문장은 거절됐다. 이유에 나온 말을 빼고 다시 쓰세요.\n{avoid}\n" if avoid else ""
    return _analysis_prompt(facts) + (
        f"\n분석 leaning: {analysis.get('leaning')}\n"
        f"분석 relation_role: {analysis.get('relation_role')}\n"
        f"분석 reasoning: {analysis.get('reasoning')}\n"
        "이 기울기 하나만 고객 문단에 남기세요. 용어는 빼세요.\n"
        + extra
    )


def _review_prompt(facts: dict, analysis: dict, overall: str) -> str:
    return (
        f"기대 기울기: {analysis.get('leaning')}\n"
        f"관계: {facts['relation']}\n"
        f"없는 데이터: {', '.join(facts['omitted'])}\n"
        f"overall:\n{overall}\n"
    )


def _spell(text: str) -> str:
    text = text.replace("되어요", "돼요")
    return re.sub(r"(?<![예이])에요", "예요", text)


def _sentences(text: str):
    return [part.strip() for part in _SENTENCE.findall(text or "") if part.strip()]


def _corpus():
    banned = []
    sewoon_path = os.path.join(_ROOT, "domains", "relationship", "data", "crush_sewoon_db.json")
    rel_path = os.path.join(_ROOT, "domains", "relationship", "data", "relationship_db.json")
    for text in _load_json(sewoon_path, {}).values():
        if isinstance(text, str):
            banned.append(text)
    for key, entry in _load_json(rel_path, {}).items():
        if key.endswith("_crush") and isinstance(entry, dict) and isinstance(entry.get("overall"), str):
            banned.append(entry["overall"])
    compact = []
    for text in banned:
        raw = re.sub(r"\s+", "", text)
        compact.extend(raw[i:i + 18] for i in range(0, max(0, len(raw) - 17)))
    return set(compact)


_CORPUS = None


def _problems(text: str, facts: dict, leaning: str) -> list:
    global _CORPUS
    found = []
    count = len(_sentences(text))
    if count < 2 or count > 6:
        found.append(f"문장 수 {count}")
    if len(text) < 70 or len(text) > 520:
        found.append(f"길이 {len(text)}")
    if leaning not in _LEANINGS:
        found.append("기울기 없음")
    elif not any(mark in text for mark in _MARK[leaning]):
        found.append("기울기가 문장에 없음")
    if leaning == "새인연":
        if "가능성" not in text:
            found.append("새인연 가능성 없음")
        for word in ("벗어나", "눈을 돌려", "옮겨가", "눈에 들어오기 시작"):
            if word in text:
                found.append(f"이미 옮긴 말 {word}")
                break
    if text.startswith("올해는"):
        found.append("올해는 으로 시작")
    for word in _TERMS:
        if _has_term(text, word):
            found.append(f"용어 {word}")
            break
    if re.search(r"(?<![예이])에요", text):
        found.append("에요 표기")
    for char in _GANJI:
        if char in text:
            found.append("간지")
            break
    for word in _PREDICT + _VOICE + _TEMPLATE:
        if word in text:
            found.append(f"금지 {word}")
            break
    if _expected_leaning(facts) != leaning:
        found.append("기울기 불일치")
    moves = any(word in text for word in ("다가서요", "다가가게", "다가가고 싶"))
    if moves and any(word in text for word in ("멈추", "멈춰", "나서지")):
        if not any(word in text for word in ("하지만", "그래도", "그래서", "다만", "그런데", "지만", "면서")):
            found.append("다가감과 멈춤이 연결되지 않음")
    if str(facts.get("relation", "")).startswith("무관") and any(word in text for word in ("부딪", "시간표", "접점")):
        found.append("무관인데 관계를 사건으로 씀")
    if _CORPUS is None:
        _CORPUS = _corpus()
    compact = re.sub(r"\s+", "", text)
    for index in range(0, max(0, len(compact) - 17)):
        if compact[index:index + 18] in _CORPUS:
            found.append("기존 문장과 겹침")
            break
    return found


def _analysis_ok(facts: dict, analysis: dict) -> str:
    if not isinstance(analysis, dict):
        return "분석 JSON 아님"
    if analysis.get("leaning") not in _LEANINGS:
        return "leaning"
    if facts["relation"].startswith("무관") and analysis.get("relation_role") != "none":
        return "무관인데 관계를 씀"
    if analysis.get("leaning") != _expected_leaning(facts):
        return f"기울기는 {_expected_leaning(facts)}"
    reasoning = str(analysis.get("reasoning") or "")
    if len(reasoning) < 20:
        return "분석이 짧음"
    for word in ("뜨겁", "열정", "둘만", "시간표", "접점", "사귀게", "성사"):
        if word in reasoning:
            return f"분석 금지 {word}"
    return ""


class _Pool:
    def __init__(self, keys):
        self.keys = keys
        self.mi = 0
        self.ki = 0
        self.dead = set()

    def _advance(self, daily: bool):
        if daily:
            self.dead.add((self.mi, self.ki))
        for _ in range(len(self.keys) * len(_MODELS)):
            self.ki += 1
            if self.ki >= len(self.keys):
                self.ki = 0
                self.mi = (self.mi + 1) % len(_MODELS)
            if (self.mi, self.ki) not in self.dead:
                return
        raise SystemExit("사용 가능한 모델과 키가 없습니다.")

    def ask(self, system: str, prompt: str, temperature: float) -> tuple:
        last = "호출 실패"
        for _ in range(len(self.keys) * len(_MODELS)):
            model = make_model(_MODELS[self.mi], self.keys[self.ki], 2048, system, temperature=temperature)
            try:
                raw = generate_one(model, prompt, 1, 2.0, timeout=45)
                return raw, _MODELS[self.mi]
            except CreditsDepleted as exc:
                raise SystemExit(str(exc)[:200]) from exc
            except DailyQuotaExceeded:
                last = "일일 한도"
                self._advance(True)
            except (InvalidApiKey, ModelUnavailable):
                last = "모델 또는 키 불가"
                self._advance(True)
            except RateLimited as exc:
                last = "짧은 제한"
                time.sleep(min(max(exc.retry_after or 5, 3), 20))
                self._advance(False)
            except Exception as exc:  # noqa: BLE001
                last = str(exc)[:120]
                self._advance(False)
        raise RuntimeError(last)


def _work_load():
    payload = _load_json(_WORK, {"items": {}})
    payload.setdefault("items", {})
    return payload


def _accept_review(overall: str, leaning: str, review) -> str:
    if not isinstance(review, dict):
        return "검수 JSON 아님"
    if review.get("direction") != leaning:
        return "검수 기울기가 다름"
    problems = review.get("problems")
    if problems:
        quote = ""
        if isinstance(problems, list) and problems and isinstance(problems[0], dict):
            quote = str(problems[0].get("quote") or "")
        if quote and quote not in overall:
            return ""
        why = ""
        if isinstance(problems, list) and problems and isinstance(problems[0], dict):
            why = str(problems[0].get("why") or "")
        return f"검수 실패: {why[:80]}"
    if review.get("pass") is not True:
        return "검수 통과 표시 없음"
    return ""


def generate(year: int, limit: int, only: str) -> None:
    keys = load_api_keys()
    if not keys:
        raise SystemExit("GEMINI_API_KEY 가 없습니다.")
    sewoon = get_seewoon_list(year, 1)[0]["ganji"]
    pillars = [part.strip() for part in only.split(",") if part.strip()] if only else sixty_gapja()
    if limit and not only:
        pillars = pillars[:limit]
    work = _work_load()
    if work.get("year") not in (None, year) or work.get("sewoon") not in (None, sewoon):
        work = {"items": {}}
    work["year"] = year
    work["sewoon"] = sewoon
    pool = _Pool(keys)
    for ganji in pillars:
        item = work["items"].get(ganji) or {}
        if item.get("status") == "pass":
            print(ganji, "skip")
            continue
        facts = _facts(ganji, year, sewoon)
        if item.get("overall") and item.get("analysis"):
            spelled = _spell(item["overall"])
            if not _problems(spelled, facts, item["analysis"].get("leaning")):
                item["overall"] = spelled
                item["status"] = "pass"
                item["error"] = ""
                work["items"][ganji] = item
                print(ganji, "kept")
                continue
        item["facts"] = facts
        analysis = item.get("analysis") if _analysis_ok(facts, item.get("analysis")) == "" else None
        if analysis is None:
            raw, model = pool.ask(_ANALYSIS_SYSTEM, _analysis_prompt(facts), 0.4)
            error = _analysis_ok(facts, raw if isinstance(raw, dict) else {})
            if error:
                raw, model = pool.ask(
                    _ANALYSIS_SYSTEM,
                    _analysis_prompt(facts) + f"\n이전 분석은 거절됐다. 이유: {error}\n",
                    0.3,
                )
            if _analysis_ok(facts, raw if isinstance(raw, dict) else {}):
                print(ganji, "analysis failed")
                item["status"] = "analysis_failed"
                work["items"][ganji] = item
                _save_json(_WORK, work)
                continue
            analysis = raw
            item["analysis_model"] = model
        overall = ""
        error = "시작"
        model = item.get("model") or ""
        avoid = ""
        for _ in range(3):
            raw, model = pool.ask(_WRITER_SYSTEM, _writer_prompt(facts, analysis, avoid), 0.7)
            overall = _spell(str(raw.get("overall") or "").strip()) if isinstance(raw, dict) else ""
            error = "; ".join(_problems(overall, facts, analysis["leaning"]))
            if error:
                avoid = f"거절 이유: {error}\n{overall}"
                continue
            review, _review_model = pool.ask(_REVIEW_SYSTEM, _review_prompt(facts, analysis, overall), 0.1)
            error = _accept_review(overall, analysis["leaning"], review)
            item["review"] = review
            if not error:
                break
        item["analysis"] = analysis
        item["overall"] = overall
        item["model"] = model
        item["error"] = error
        item["status"] = "pass" if not error else "fail"
        work["items"][ganji] = item
        _save_json(_WORK, work)
        print(ganji, analysis["leaning"], item["status"], error)
    _dedupe(work, pool)
    _save_json(_WORK, work)
    export_db(work)


def _dedupe(work, pool) -> None:
    items = work["items"]
    used = []
    for ganji in sixty_gapja():
        item = items.get(ganji)
        if not item or item.get("status") != "pass":
            continue
        text = item["overall"]
        twin = ""
        for prev, prev_text in used:
            if SequenceMatcher(None, text, prev_text).ratio() >= 0.78:
                twin = prev_text
                break
        if twin:
            facts = item["facts"]
            analysis = item["analysis"]
            raw, model = pool.ask(
                _WRITER_SYSTEM,
                _writer_prompt(facts, analysis, twin),
                0.8,
            )
            overall = _spell(str(raw.get("overall") or "").strip()) if isinstance(raw, dict) else ""
            error = "; ".join(_problems(overall, facts, analysis["leaning"]))
            if not error:
                review, _model = pool.ask(_REVIEW_SYSTEM, _review_prompt(facts, analysis, overall), 0.1)
                error = _accept_review(overall, analysis["leaning"], review)
            if not error:
                item["overall"] = overall
                item["model"] = model
                item["error"] = ""
                text = overall
                print(ganji, "deduped")
            else:
                print(ganji, "dedupe kept")
        if item.get("status") == "pass":
            used.append((ganji, text))


def export_db(work) -> None:
    year = str(work["year"])
    bucket = {}
    failed = []
    for ganji in sixty_gapja():
        item = work["items"].get(ganji)
        if not item or item.get("status") != "pass":
            if ganji in work["items"] or len(work["items"]) >= 60:
                failed.append(ganji)
            continue
        bucket[ganji] = {
            "overall": item["overall"],
            "sewoon": work["sewoon"],
            "leaning": item["analysis"]["leaning"],
            "_model": item.get("model") or "",
        }
    if len(work["items"]) >= 60 and failed:
        print("export skipped", ",".join(failed))
        return
    if len(bucket) < 60 and len(work["items"]) < 60:
        print("partial", len(bucket))
        return
    db = _load_json(_DATA, {})
    if not isinstance(db, dict):
        db = {}
    db[year] = bucket
    _save_json(_DATA, db)
    print("wrote", _DATA, year, len(bucket))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    if args.export_only:
        export_db(_work_load())
        return
    generate(args.year, args.limit, args.only)


if __name__ == "__main__":
    main()
