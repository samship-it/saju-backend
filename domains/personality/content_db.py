"""사전 생성된 '나의 성격 / 나의 적성' 정적 DB 접근 계층.

일주(일간·일지) = 60갑자 각각에 대해 성격(character 6필드) + 적성(aptitude 6필드)을
미리 생성해 `domains/personality/data/personality_db.json` 에 저장해 둔다. 런타임은
일주 간지로 조회만 하며 Gemini 를 호출하지 않는다. DB 생성은
`scripts/generate_content_db.py --domain personality` 참고.

배포에 포함되는 정적 파일이므로 프로세스당 최초 1회만 읽어 메모리에 둔다.

키 형식: 일주 간지(한자 2자), 예) "戊辰".
값: {"character": {6필드}, "aptitude": {6필드}, "_model_character": ..., "_model_aptitude": ...}
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("PERSONALITY_DB_PATH", os.path.join(DATA_DIR, "personality_db.json"))

_lock = threading.Lock()
_cache: Optional[Dict[str, Any]] = None


def load_db(force: bool = False) -> Dict[str, Any]:
    """personality_db.json 을 최초 1회 읽어 메모리에 캐시한다(정적 파일)."""
    global _cache
    if _cache is not None and not force:
        return _cache
    with _lock:
        if _cache is not None and not force:
            return _cache
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            _cache = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            _cache = {}
        return _cache


def reload() -> Dict[str, Any]:
    """DB 파일을 다시 생성한 뒤 메모리 캐시를 갱신할 때 호출(테스트/재생성용)."""
    return load_db(force=True)


def lookup(day_ganji: str, group: str) -> Optional[Dict[str, Any]]:
    """일주 간지 + group('character'|'aptitude') -> 해당 6필드 dict. 없으면 None."""
    entry = load_db().get((day_ganji or "").strip())
    if not isinstance(entry, dict):
        return None
    sub = entry.get(group)
    return sub if isinstance(sub, dict) else None


def stats() -> Dict[str, Any]:
    db = load_db()
    return {"path": DB_PATH, "count": len(db), "expected": 60}
