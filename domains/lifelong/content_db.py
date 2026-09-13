"""사전 생성된 '평생운세' 정적 DB 접근 계층.

세 개의 테이블로 나뉜다(키 공간을 최소화하기 위함 — domains/lifelong/service.py
모듈 docstring 및 대운 순번 축 설계 논의 참고):

- base_db: 일주(60) 당 1건 — life_theme(인생을 관통하는 반복 과제) 하나만.
  personality(타고난 성향)는 domains/personality/data/personality_db.json 을
  그대로 재사용하므로 여기서 다시 만들지 않는다.
- domains_db: (일주, 현재 대운의 지배 십신군, 대운 순번) 조합당 1건 — 삶의 4대 영역
  (재물/직업/가족/사회). 60×5×8 = 2,400건. 재물↔재성/직업↔관성/가족↔인성/사회↔비겁
  고정 앵커로 서로 겹치지 않게 한다.
- stage_db: (일주, 대운 순번, 지배 십신군, 충형관계) 조합당 1건 — 시기별 전환점
  (theme_line/event_narrative/previous_diff/next_hint). 60×(5×8×충형카테고리)
  = 14,000건. ⚠️ 2026-09-14 기준 재작성 진행 중(구 연령대 기반 스키마에서
  대운 순번 기반으로 전환) — 이 파일의 stage_* 함수는 아직 신 스키마 미반영.

세 파일 모두 배포에 포함되는 정적 산출물이므로, 프로세스 시작 후 최초 1회만 읽어
메모리에 둔다. DB 를 다시 생성했다면 프로세스를 재시작하거나 `reload()` 를 호출한다.

키 형식:
- base: "<일주>"                                    예) "甲子"
- domains: "<일주>_<dominant_group>_<순번>"          예) "甲子_재성_3"
- stage: (재작성 중)
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BASE_DB_PATH = os.environ.get("LIFELONG_BASE_DB_PATH", os.path.join(DATA_DIR, "lifelong_base_db.json"))
DOMAINS_DB_PATH = os.environ.get("LIFELONG_DOMAINS_DB_PATH", os.path.join(DATA_DIR, "lifelong_domains_db.json"))
STAGE_DB_PATH = os.environ.get("LIFELONG_STAGE_DB_PATH", os.path.join(DATA_DIR, "lifelong_stage_db.json"))

_lock = threading.Lock()
_base_cache: Optional[Dict[str, Any]] = None
_domains_cache: Optional[Dict[str, Any]] = None
_stage_cache: Optional[Dict[str, Any]] = None


def base_key(ilju: str) -> str:
    return (ilju or "").strip()


def domains_key(ilju: str, dominant_group: str, step: int) -> str:
    return f"{(ilju or '').strip()}_{dominant_group}_{step}"


def stage_key(ilju: str, dominant_group: str, branch_relation: str, step: int) -> str:
    return f"{(ilju or '').strip()}_{dominant_group}_{branch_relation}_{step}"


def _load(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def load_base_db(force: bool = False) -> Dict[str, Any]:
    global _base_cache
    if _base_cache is not None and not force:
        return _base_cache
    with _lock:
        if _base_cache is not None and not force:
            return _base_cache
        _base_cache = _load(BASE_DB_PATH)
        return _base_cache


def load_domains_db(force: bool = False) -> Dict[str, Any]:
    global _domains_cache
    if _domains_cache is not None and not force:
        return _domains_cache
    with _lock:
        if _domains_cache is not None and not force:
            return _domains_cache
        _domains_cache = _load(DOMAINS_DB_PATH)
        return _domains_cache


def load_stage_db(force: bool = False) -> Dict[str, Any]:
    global _stage_cache
    if _stage_cache is not None and not force:
        return _stage_cache
    with _lock:
        if _stage_cache is not None and not force:
            return _stage_cache
        _stage_cache = _load(STAGE_DB_PATH)
        return _stage_cache


def reload() -> None:
    """세 DB 파일을 다시 생성한 뒤 메모리 캐시를 갱신할 때 호출(테스트/재생성용)."""
    load_base_db(force=True)
    load_domains_db(force=True)
    load_stage_db(force=True)


def lookup_base(ilju: str) -> Optional[Dict[str, Any]]:
    return load_base_db().get(base_key(ilju))


def lookup_domains(ilju: str, dominant_group: str, step: int) -> Optional[Dict[str, Any]]:
    return load_domains_db().get(domains_key(ilju, dominant_group, step))


def lookup_stage(ilju: str, dominant_group: str, branch_relation: str, step: int) -> Optional[Dict[str, Any]]:
    return load_stage_db().get(stage_key(ilju, dominant_group, branch_relation, step))


def stats() -> Dict[str, Any]:
    return {
        "base_path": BASE_DB_PATH, "base_count": len(load_base_db()), "base_expected": 60,
        "domains_path": DOMAINS_DB_PATH, "domains_count": len(load_domains_db()), "domains_expected": 2400,
        "stage_path": STAGE_DB_PATH, "stage_count": len(load_stage_db()), "stage_expected": 14000,
    }
