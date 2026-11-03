"""사전 생성된 대운 문단. 요청 중에는 이 파일만 읽는다."""
import json
import os
import threading
from typing import Any, Dict, Optional

from domains.daewoon.prose_catalog import age_band, prose_key, strength_state

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_LOCK = threading.Lock()
_CACHE: Dict[str, Dict[str, Any]] = {}


def shard_path(dm_elem: str) -> str:
    return os.path.join(DATA_DIR, f"daewoon_prose_{dm_elem}.json")


def jsonl_path(dm_elem: str) -> str:
    return os.path.join(DATA_DIR, f"daewoon_prose_{dm_elem}.jsonl")


def read_shard(dm_elem: str) -> Dict[str, Any]:
    """JSON 본문과, 아직 합쳐지지 않은 JSONL 한 줄을 함께 읽는다."""
    path = shard_path(dm_elem)
    data: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            data = loaded
    extra = jsonl_path(dm_elem)
    if os.path.exists(extra):
        with open(extra, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    data.update(obj)
    return data


def load_shard(dm_elem: str, force: bool = False) -> Dict[str, Any]:
    if not force and dm_elem in _CACHE:
        return _CACHE[dm_elem]
    data = read_shard(dm_elem)
    with _LOCK:
        _CACHE[dm_elem] = data
    return data


def get_prose(key: str) -> Optional[Dict[str, Any]]:
    dm = key.split("|", 1)[0]
    entry = load_shard(dm).get(key)
    return entry if isinstance(entry, dict) else None


def _block(entry: Optional[Dict[str, Any]], past: bool) -> Optional[Dict[str, Any]]:
    if not entry:
        return None
    block = entry.get("past" if past else "present")
    return block if isinstance(block, dict) else None


def _apply_domains(analysis: Dict[str, Any], domains: Any) -> None:
    if not isinstance(domains, dict):
        return
    for section, fields in domains.items():
        if not isinstance(fields, dict):
            continue
        target = analysis.get(section)
        if not isinstance(target, dict):
            target = {}
            analysis[section] = target
        for field, text in fields.items():
            if isinstance(text, str) and text.strip():
                target[field] = text.strip()


def _apply_tasks(block: Dict[str, Any], decade_tasks: list, action_guide: str) -> tuple:
    tasks = [item.strip() for item in (block.get("tasks") or []) if isinstance(item, str) and item.strip()]
    guide = block.get("action_guide") if isinstance(block.get("action_guide"), str) else ""
    return (tasks or decade_tasks), (guide.strip() or action_guide)


def overlay_saved_prose(
    saju: Dict[str, Any],
    facts: list,
    fact: Dict[str, Any],
    daewoon_num: int,
    current_age: int,
    domain_pipeline: Dict[str, Any],
    domain_analysis: Dict[str, Any],
    twenty_story: Optional[Dict[str, Any]],
    decade_tasks: list,
    action_guide: str,
) -> tuple:
    """저장된 칸이 있으면 그 문단만 바꾼다. 없으면 기존 문장을 그대로 둔다."""

    def at(start: int):
        for item in facts:
            item_start = daewoon_num + (item["step"] - 1) * 10
            if item_start == start:
                return item, item_start
        return None, start

    opened_start = daewoon_num + (fact["step"] - 1) * 10
    if twenty_story:
        front_fact, front_start = at((twenty_story.get("front_age_range") or [opened_start])[0])
        back_fact, back_start = at((twenty_story.get("back_age_range") or [opened_start])[0])
        front = _block(
            lookup_decade(saju, (front_fact or fact).get("ganji") or "", front_start),
            (front_start + 9) < current_age,
        )
        back = _block(
            lookup_decade(saju, (back_fact or {}).get("ganji") or "", back_start),
            (back_start + 9) < current_age,
        )
        if front and isinstance(front.get("overview"), str) and front["overview"].strip():
            twenty_story["overview"] = front["overview"].strip()
        if front and isinstance(front.get("decade"), str) and front["decade"].strip():
            twenty_story["front"] = front["decade"].strip()
        if back and isinstance(back.get("decade"), str) and back["decade"].strip():
            twenty_story["back"] = back["decade"].strip()
        opened = front if front_fact is fact else back
        if opened:
            _apply_domains(domain_analysis, opened.get("domains"))
            decade_tasks, action_guide = _apply_tasks(opened, decade_tasks, action_guide)
            if isinstance(opened.get("action_guide"), str) and opened["action_guide"].strip():
                twenty_story["action_guide"] = opened["action_guide"].strip()
        return domain_analysis, decade_tasks, action_guide

    entry = _block(lookup_decade(saju, fact.get("ganji") or "", opened_start), (opened_start + 9) < current_age)
    if not entry:
        return domain_analysis, decade_tasks, action_guide
    if isinstance(entry.get("decade"), str) and entry["decade"].strip():
        domain_pipeline["global_context"] = entry["decade"].strip()
    _apply_domains(domain_analysis, entry.get("domains"))
    decade_tasks, action_guide = _apply_tasks(entry, decade_tasks, action_guide)
    return domain_analysis, decade_tasks, action_guide


def lookup_decade(saju: Dict[str, Any], ganji: str, start_age: int) -> Optional[Dict[str, Any]]:
    """이 사주·이 10년이 떨어지는 칸. 파일이 없으면 None."""
    from core.constants import GAN_ELEM
    from domains.daewoon.natal_relation import agreed_natal_group

    strength = saju.get("strength") or {}
    dm = GAN_ELEM.get(saju.get("day_master") or "", "")
    if not dm or not ganji:
        return None
    key = prose_key(
        dm,
        strength_state(strength.get("verdict") or "", strength.get("elem_power") or {}),
        agreed_natal_group(saju) or "none",
        ganji,
        age_band(start_age),
    )
    return get_prose(key)
