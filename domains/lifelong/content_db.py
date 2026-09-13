"""사전 생성된 '평생운세' 정적 DB 접근 계층.

daily_db.json 과 달리 두 개의 테이블로 나뉜다(키 공간을 최소화하기 위함):

- base_db: 일주(60) 당 1건 — core_nature(타고난 본질) + life_domains(평생 재물/직업/
  가족/대인관계 성향). 일주만으로 결정되는, 시점과 무관한 값.
- stage_db: (일주, 생애단계, 그 단계의 지배 십신군, 직전 단계의 지배 십신군) 조합당
  1건 — description/daeun_influence/previous_diff. 실제 개인의 정확한 대운 간지가
  아니라 '십신 5분류'로 추상화해 키 공간을 줄인다(daily 의 일주×일진 트레이드오프와
  동일한 성격의 단순화 — domains/lifelong/service.py 의 _build_stage_engine 참고).
  stage_1_19 는 직전 단계가 없으므로 prev_group="none" 고정.

이 두 파일 모두 배포에 포함되는 정적 산출물이므로, 프로세스 시작 후 최초 1회만 읽어
메모리에 둔다. DB 를 다시 생성했다면 프로세스를 재시작하거나 `reload()` 를 호출한다.

키 형식:
- base: "<일주>"                                           예) "甲子"
- stage: "<일주>_<stage>_<dominant_group>_<prev_group>"    예) "甲子_stage_30_49_재성_식상"
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BASE_DB_PATH = os.environ.get("LIFELONG_BASE_DB_PATH", os.path.join(DATA_DIR, "lifelong_base_db.json"))
STAGE_DB_PATH = os.environ.get("LIFELONG_STAGE_DB_PATH", os.path.join(DATA_DIR, "lifelong_stage_db.json"))

_lock = threading.Lock()
_base_cache: Optional[Dict[str, Any]] = None
_stage_cache: Optional[Dict[str, Any]] = None


def base_key(ilju: str) -> str:
    return (ilju or "").strip()


def stage_key(ilju: str, stage: str, dominant_group: str, prev_group: Optional[str]) -> str:
    return f"{(ilju or '').strip()}_{stage}_{dominant_group}_{prev_group or 'none'}"


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
    """두 DB 파일을 다시 생성한 뒤 메모리 캐시를 갱신할 때 호출(테스트/재생성용)."""
    load_base_db(force=True)
    load_stage_db(force=True)


def lookup_base(ilju: str) -> Optional[Dict[str, Any]]:
    return load_base_db().get(base_key(ilju))


def lookup_stage(ilju: str, stage: str, dominant_group: str, prev_group: Optional[str]) -> Optional[Dict[str, Any]]:
    return load_stage_db().get(stage_key(ilju, stage, dominant_group, prev_group))


def stats() -> Dict[str, Any]:
    return {
        "base_path": BASE_DB_PATH, "base_count": len(load_base_db()), "base_expected": 60,
        "stage_path": STAGE_DB_PATH, "stage_count": len(load_stage_db()), "stage_expected": 6300,
    }
