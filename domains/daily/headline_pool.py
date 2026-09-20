"""사전 생성된 headline/today_energy 문구 풀(셀당 다수 변형) 접근 계층.

woon_modifier.py 의 HEADLINE_TABLE/TODAY_ENERGY_TABLE 은 셀(개별 십신×관계버킷,
10×6=60개)당 문구가 1개뿐이라, 같은 셀이 다시 나오면(예: 같은 십신이 10일 뒤
재등장) 정확히 같은 문장이 다시 나간다. 이 모듈은
`scripts/generate_content_db.py --domain daily_headline_pool`(및
`daily_today_energy_pool`)로 셀당 다수(기본 20개) 미리 생성해 둔 변형 문구를 읽어,
날짜(target_date)를 시드로 그 안에서 결정적으로 로테이션한다.

런타임 Gemini 호출은 여전히 없다 — 정적 JSON 파일을 읽기만 한다. 풀에 해당 셀이
없으면(아직 생성 전 등) None을 반환하고, 호출자(woon_modifier.py)가 기존
HEADLINE_TABLE/TODAY_ENERGY_TABLE 고정 문구로 폴백한다.
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HEADLINE_POOL_PATH = os.environ.get(
    "DAILY_HEADLINE_POOL_PATH", os.path.join(DATA_DIR, "headline_pool.json")
)
TODAY_ENERGY_POOL_PATH = os.environ.get(
    "DAILY_TODAY_ENERGY_POOL_PATH", os.path.join(DATA_DIR, "today_energy_pool.json")
)

_lock = threading.Lock()
_headline_cache: Optional[Dict[str, Any]] = None
_energy_cache: Optional[Dict[str, Any]] = None


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def load_headline_pool(force: bool = False) -> Dict[str, Any]:
    global _headline_cache
    if _headline_cache is not None and not force:
        return _headline_cache
    with _lock:
        if _headline_cache is not None and not force:
            return _headline_cache
        _headline_cache = _read_json(HEADLINE_POOL_PATH)
        return _headline_cache


def load_today_energy_pool(force: bool = False) -> Dict[str, Any]:
    global _energy_cache
    if _energy_cache is not None and not force:
        return _energy_cache
    with _lock:
        if _energy_cache is not None and not force:
            return _energy_cache
        _energy_cache = _read_json(TODAY_ENERGY_POOL_PATH)
        return _energy_cache


def reload() -> None:
    """풀 JSON을 다시 생성한 뒤 메모리 캐시를 갱신할 때 호출(테스트/재생성용)."""
    load_headline_pool(force=True)
    load_today_energy_pool(force=True)


def _cell_key(sipsin: str, bucket: str) -> str:
    return f"{sipsin}_{bucket}"


def _pick(pool: Dict[str, Any], sipsin: Optional[str], bucket: Optional[str], day_ordinal: int) -> Optional[str]:
    if not sipsin or not bucket:
        return None
    entry = pool.get(_cell_key(sipsin, bucket))
    if not isinstance(entry, dict):
        return None
    variants = entry.get("variants")
    if not isinstance(variants, list) or not variants:
        return None
    return variants[day_ordinal % len(variants)]


def pick_headline(sipsin: Optional[str], bucket: Optional[str], day_ordinal: int = 0) -> Optional[str]:
    """(개별 십신, 관계버킷) 셀의 변형 문구 풀에서 day_ordinal 기준으로 하나 고른다.
    풀에 해당 셀이 없으면 None(호출자가 static HEADLINE_TABLE로 폴백)."""
    return _pick(load_headline_pool(), sipsin, bucket, day_ordinal)


def pick_today_energy(sipsin: Optional[str], bucket: Optional[str], day_ordinal: int = 0) -> Optional[str]:
    return _pick(load_today_energy_pool(), sipsin, bucket, day_ordinal)


def stats() -> Dict[str, Any]:
    hp, ep = load_headline_pool(), load_today_energy_pool()

    def _summ(pool: Dict[str, Any], expected_cells: int) -> Dict[str, Any]:
        counts = [len(v.get("variants", [])) for v in pool.values() if isinstance(v, dict)]
        return {
            "cells": len(pool),
            "expected_cells": expected_cells,
            "total_variants": sum(counts),
            "min_variants_per_cell": min(counts) if counts else 0,
        }

    return {
        "headline_pool": {"path": HEADLINE_POOL_PATH, **_summ(hp, 60)},
        "today_energy_pool": {"path": TODAY_ENERGY_POOL_PATH, **_summ(ep, 60)},
    }
