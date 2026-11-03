"""대운 문단 37,800칸을 Gemini로 미리 채운다. 요청 경로에서는 호출하지 않는다.

이미 있는 키는 건너뛴다. 중단 후 같은 명령으로 이어 한다.

  python scripts/generate_daewoon_llm.py --limit 2
  python scripts/generate_daewoon_llm.py --workers 8 --batch 2
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402  dotenv
import google.generativeai as genai  # noqa: E402
from google.ai import generativelanguage as glm  # noqa: E402

from domains.daewoon.prose_catalog import AGE_BANDS, iter_keys, prompt_facts  # noqa: E402
from domains.daewoon.prose_db import jsonl_path, read_shard, shard_path  # noqa: E402
from scripts.generate_content_db import (  # noqa: E402
    DAILY_BATCH_MODELS,
    _atomic_write_json,
    _extract_json,
    _is_daily_quota,
    load_api_keys,
    make_model,
)

_BANNED = (
    "비겁", "식상", "재성", "관성", "인성", "신강", "신약", "용신", "기신", "격국", "십신",
    "비견", "겁재", "식신", "편재", "정재", "편관", "정관", "편인", "정인",
    "인성운", "상관운",
    "합격", "이직", "전학", "억 원",
)
_SCHOOL_BANNED = ("직장", "승진", "연봉", "재테크", "첫 직장", "자산")
_ADULT_BANNED = ("용돈", "반장", "초등학교")
_SPECIFIC_AGE = ("초등학교", "중학교", "고등학교", "대학교", "첫 직장", "수능")
_FIELDS = {
    "school": {
        "study_growth": ("school_life", "exam_luck", "aptitude_path"),
        "friendship": ("peer_relationship", "bond_with_others", "group_adaptation"),
        "family_environment": ("parent_relationship", "home_support", "home_atmosphere"),
    },
    "span": {
        "study_growth": ("school_life", "exam_luck", "aptitude_path"),
        "career_or_study": ("growth_flow", "study_style", "cautions"),
        "friendship": ("peer_relationship", "bond_with_others", "group_adaptation"),
        "family_environment": ("parent_relationship", "home_support", "home_atmosphere"),
    },
    "adult": {
        "career_or_study": ("core_change", "how_it_shows", "cautions"),
        "wealth_flow": ("earning_style", "cash_flow", "management_caution"),
        "relationship": ("flow",),
        "family": ("change_flow", "warning"),
    },
}
_AGE_GUIDE = {
    "school": "가정, 공부, 친구",
    "span": "공부, 진로, 사회 입문",
    "adult": "일, 돈, 사람, 가족",
}
_META_ECHO = (
    "단정하지", "쓰지 않", "넣지 마", "한 구간", "전체 구간", "나이 숫자", "학년 이름",
    "뒤로 갈수록", "생활의 중심", "고정하지", "한쪽으로", "베끼",
)
_DAEWOON_SYSTEM = (
    "당신은 사주 운세 앱의 대운 해설을 씁니다. 주어진 사실만 사용하고 사주를 다시 계산하지 않습니다. "
    "문장 끝은 합니다, 입니다, 하세요로 맞춥니다. 해요, 예요, 답니다는 쓰지 않습니다. "
    "나이 숫자, 학교 급, 합격, 이직, 전학, 결혼, 금액은 단정하지 않습니다. "
    "과거 글은 현재 문장의 어미만 바꾼 글이 아니라 같은 결을 회고로 다시 씁니다. "
    "나이 장면을 규칙으로 설명하지 않고, 그 시기에 하는 일만 씁니다. "
    "운세는 한 사람에게 읽어 준다. '여러분', '여러분은', '여러분의'처럼 여러 명을 부르지 않는다. "
    "JSON 하나만 출력합니다."
)
_TONE_BANNED = ("해요", "예요", "이에요", "답니다", "되어요", "거든요")
_AGE_ECHO = ("성인기", "학령", "나이대")


def _schema_hint(band: str) -> str:
    fields = _FIELDS[band]
    lines = []
    for section, names in fields.items():
        body = ", ".join(f'"{name}":"..."' for name in names)
        lines.append(f'"{section}":{{{body}}}')
    return "{" + ",".join(lines) + "}"


def _prompt(facts: Dict[str, Any]) -> str:
    relation = facts["relation"] or "없음"
    paired = facts["paired"]
    pair_line = "이 10년 다음에 같은 결이 10년 더 이어지지 않는다. overview는 빈 문자열로 둔다."
    if paired:
        pair_line = (
            f"다음 10년은 {facts['next_season']}의 {facts['next_theme']}이다. "
            "overview에는 20년 내내 유지되는 것만 쓰고, 다음 10년의 구체적 장면은 쓰지 않는다."
        )
    pressure = ""
    if relation in ("규제", "맞섬"):
        pressure = "순탄, 순하게 라는 말은 쓰지 않는다. 부담과 성과를 한 문장에 섞되 한쪽만 단정하지 않는다."
    return f"""아래 사실만 보고 한국어 대운 글을 쓴다. 사주를 다시 계산하지 않는다. 없는 합격·이직·전학·결혼·금액은 단정하지 않는다.

[사실]
- 일간의 오행: {facts['day_master_element']}
- 강약 상태: {facts['strength']}
- 원국 성향: {facts['tendency']} (none이면 성향을 단정하지 않는다)
- 이 10년의 결: {facts['group_theme']}
- 계절: {facts['season']}
- 이 흐름의 무게: {facts['polarity']} (favorable=힘을 보탬, unfavorable=부담, neutral=크게 기울지 않음)
- 원국과의 관계: {relation}
- 나이: {_AGE_GUIDE[facts['age_band']]}
- {pair_line}
{pressure}

[문장]
- 문장 끝은 합니다, 입니다, 하세요. 해요, 예요, 답니다는 쓰지 않는다. 사주 용어와 십신 이름은 쓰지 않는다.
- present는 지금과 앞으로, past는 이미 지난 일을 다른 문장으로 회고한다. 같은 문장에 어미만 바꾸지 않는다.
- past의 행동 문장도 이미 한 선택으로 쓴다. 해보세요로 끝내지 않는다.
- 몇 세, 성인기, 학령처럼 나이 구간 이름은 문장에 넣지 않는다. 위의 지시문을 해설에 베끼지 않는다.
- decade는 4~6문장. tasks는 3개. 각 영역 칸은 2~3문장.
- 같은 말을 칸마다 반복하지 않는다.

[출력]
present와 past가 같은 구조다. domains는 정확히 이 모양이다.
{_schema_hint(facts['age_band'])}
JSON만 출력한다.
{{"present":{{"overview":"...","decade":"...","action_guide":"...","tasks":["","",""],"domains":{{...}}}},"past":{{"overview":"...","decade":"...","action_guide":"...","tasks":["","",""],"domains":{{...}}}}}}
"""


def _texts(block: Dict[str, Any]) -> List[str]:
    found = []
    for key in ("overview", "decade", "action_guide"):
        if isinstance(block.get(key), str):
            found.append(block[key])
    for item in block.get("tasks") or []:
        if isinstance(item, str):
            found.append(item)
    domains = block.get("domains") or {}
    if isinstance(domains, dict):
        for fields in domains.values():
            if isinstance(fields, dict):
                found.extend(value for value in fields.values() if isinstance(value, str))
    return found


def reject_reason(entry: Any, facts: Dict[str, Any]) -> str:
    if not isinstance(entry, dict):
        return "schema"
    band = facts["age_band"]
    for tense in ("present", "past"):
        block = entry.get(tense)
        if not isinstance(block, dict):
            return "schema"
        if facts["paired"]:
            if not str(block.get("overview") or "").strip():
                return "overview"
        elif str(block.get("overview") or "").strip():
            return "overview"
        decade = str(block.get("decade") or "").strip()
        if not decade or not str(block.get("action_guide") or "").strip():
            return "schema"
        if not any(mark in decade for mark in ("합니다", "입니다", "습니다")):
            return "tone"
        tasks = block.get("tasks")
        if not isinstance(tasks, list) or len([item for item in tasks if str(item).strip()]) < 3:
            return "tasks"
        domains = block.get("domains")
        if not isinstance(domains, dict):
            return "domain"
        for section, names in _FIELDS[band].items():
            fields = domains.get(section)
            if not isinstance(fields, dict):
                return "domain"
            for name in names:
                if not str(fields.get(name) or "").strip():
                    return "domain"
        blob = " ".join(_texts(block))
        if any(word in blob for word in _BANNED):
            return "banned"
        if any(word in blob for word in _SPECIFIC_AGE) or any(word in blob for word in _AGE_ECHO):
            return "age"
        if any(word in blob for word in _META_ECHO):
            return "echo"
        if re.search(r"\d+\s*세", blob):
            return "age"
        if band == "school" and any(word in blob for word in _SCHOOL_BANNED):
            return "age"
        if band == "adult" and any(word in blob for word in _ADULT_BANNED):
            return "age"
        if any(word in blob for word in _TONE_BANNED):
            return "tone"
        if facts["relation"] in ("규제", "맞섬") and ("순탄" in blob or "순하게" in blob):
            return "pressure"
    past = entry["past"]["decade"]
    present = entry["present"]["decade"]
    folded = past
    for src, dst in (("었", ""), ("았", ""), ("였", ""), ("했", "하"), ("됐", "되")):
        folded = folded.replace(src, dst)
    if past == present or folded == present or not any(mark in past for mark in ("었", "였", "했", "됐")):
        return "tense"
    if SequenceMatcher(None, present, past).ratio() > 0.72:
        return "tense"
    return ""


def _balance(text: str) -> str:
    stack = []
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()
    if in_str:
        text += '"'
    text = re.sub(r",\s*$", "", text)
    return text + "".join(reversed(stack))


def _generate(model, prompt: str) -> dict:
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            resp = model.generate_content(prompt, request_options={"timeout": 300})
            text = resp.text or ""
            try:
                return _extract_json(text)
            except json.JSONDecodeError:
                return _extract_json(_balance(text))
        except Exception as exc:
            last = exc
            if _is_daily_quota(exc):
                raise
            if attempt >= 2:
                break
            wait = 2.0 * (2 ** attempt)
            print(
                f"    ↻ 재시도 {attempt + 1}/2 ({type(exc).__name__}, {wait:.0f}s 대기): {str(exc)[:160]}",
                flush=True,
            )
            time.sleep(wait)
    raise RuntimeError(f"max_retries 초과: {last}")


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    keys = load_api_keys()
    if not keys:
        raise SystemExit("GEMINI_API_KEY 가 없습니다.")
    model_name = args.model or DAILY_BATCH_MODELS[0]
    os.makedirs(os.path.dirname(shard_path("목")), exist_ok=True)
    shards = {elem: read_shard(elem) for elem in ("목", "화", "토", "금", "수")}
    done = {key for data in shards.values() for key in data}
    todo = [key for key in iter_keys() if key not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"대상 {len(todo)}편 · 이미 {len(done)}편 · 모델 {model_name} · 키 {len(keys)}개", flush=True)
    if not todo:
        return
    work = [todo[i:i + max(1, args.batch)] for i in range(0, len(todo), max(1, args.batch))]
    lock = threading.Lock()
    made = 0
    failed = 0
    t0 = time.time()

    since_flush = {elem: 0 for elem in shards}

    def _append(elem: str, key: str, entry: Dict[str, Any]) -> None:
        line = json.dumps({key: entry}, ensure_ascii=False) + "\n"
        path = jsonl_path(elem)
        for attempt in range(8):
            try:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
                return
            except PermissionError:
                time.sleep(0.2 * (attempt + 1))
        raise PermissionError(path)

    def _flush(elem: str) -> None:
        if not shards[elem]:
            return
        _atomic_write_json(shard_path(elem), shards[elem])
        extra = jsonl_path(elem)
        if os.path.exists(extra):
            with open(extra, "w", encoding="utf-8") as handle:
                handle.write("")
        since_flush[elem] = 0

    def store(key: str, entry: Dict[str, Any]) -> None:
        elem = key.split("|", 1)[0]
        with lock:
            shards[elem][key] = entry
            _append(elem, key, entry)
            since_flush[elem] += 1
            if since_flush[elem] >= 40:
                _flush(elem)

    def run(worker: int, chunks: List[List[str]]) -> None:
        nonlocal made, failed
        api_key = keys[worker % len(keys)]
        model = make_model(
            model_name, api_key, max_output_tokens=65536, system_instruction=_DAEWOON_SYSTEM,
        )
        for chunk in chunks:
            facts = [prompt_facts(key) for key in chunk]
            prompt = "\n\n".join(
                f"조합키: {item['key']}\n{_prompt(item)}" for item in facts
            )
            if len(chunk) > 1:
                prompt += (
                    "\n\n최상위 키는 조합키 문자열이다. "
                    + ", ".join(chunk)
                )
            try:
                raw = _generate(model, prompt)
            except Exception as exc:
                if _is_daily_quota(exc):
                    print(f"워커#{worker} 오늘 한도. 이 묶음은 다음 실행에서 이어 한다.", flush=True)
                    return
                print(f"워커#{worker} 실패 {chunk[0]} {exc}", flush=True)
                with lock:
                    failed += len(chunk)
                continue
            payload = raw
            if len(chunk) > 1 and not any(key in raw for key in chunk):
                payload = {chunk[0]: raw}
            for item in facts:
                entry = payload.get(item["key"], payload if len(chunk) == 1 else None)
                if isinstance(entry, dict):
                    from shared.prose_quality import polish_tree
                    entry = polish_tree(entry)
                reason = reject_reason(entry, item)
                if not reason:
                    store(item["key"], entry)
                    with lock:
                        made += 1
                        current = made
                    if current % 10 == 0:
                        elapsed = time.time() - t0
                        left = (len(todo) - current) * (elapsed / current)
                        print(f"완료 {current}/{len(todo)} · 남은 약 {left / 3600:.1f}시간", flush=True)
                else:
                    with lock:
                        failed += 1
                    print(f"검사 탈락 {item['key']} {reason}", flush=True)

    groups: List[List[List[str]]] = [[] for _ in range(args.workers)]
    for index, chunk in enumerate(work):
        groups[index % args.workers].append(chunk)
    threads = [
        threading.Thread(target=run, args=(index, group), daemon=True)
        for index, group in enumerate(groups) if group
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with lock:
        for elem in shards:
            if since_flush[elem]:
                _flush(elem)
    print(f"저장 {made}편 · 탈락 {failed}편 · {time.time() - t0:.0f}초", flush=True)
    if args.limit:
        return
    done_now = set()
    for elem in ("목", "화", "토", "금", "수"):
        done_now.update(read_shard(elem))
    left = [key for key in iter_keys() if key not in done_now]
    if not left:
        print("37,800편 저장이 끝났습니다.", flush=True)
        return
    if made == 0:
        print(f"남은 {len(left)}편. 오늘 한도로 멈췄습니다. 30분 후 이어 합니다.", flush=True)
        time.sleep(1800)
    else:
        print(f"남은 {len(left)}편을 바로 이어 합니다.", flush=True)
    main()


if __name__ == "__main__":
    main()
