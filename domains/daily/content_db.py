"""사전 생성된 '오늘의 운세' 정적 DB 접근 계층.

(내 일주 × 오늘 일진) = 60 × 60 = 3,600개 조합을 미리 Gemini 로 생성해
`domains/daily/data/daily_db.json` 에 저장해 둔다. 런타임(router)은 이 파일에서
즉시 조회만 하며 Gemini 를 호출하지 않는다.

키 형식: "<일주 간지>_<일진 간지>"  (한자 2자 + "_" + 한자 2자), 예) "戊辰_乙巳"
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("DAILY_DB_PATH", os.path.join(DATA_DIR, "daily_db.json"))

_lock = threading.Lock()
_cache: Optional[Dict[str, Any]] = None
_mtime: Optional[float] = None


def make_key(day_ganji: str, iljin_ganji: str) -> str:
    """(내 일주, 오늘 일진) -> DB 조회 키."""
    return f"{(day_ganji or '').strip()}_{(iljin_ganji or '').strip()}"


def load_db(force: bool = False) -> Dict[str, Any]:
    """daily_db.json 을 읽어 캐시한다. 파일이 갱신되면 자동으로 다시 읽는다."""
    global _cache, _mtime
    with _lock:
        try:
            mtime = os.path.getmtime(DB_PATH)
        except OSError:
            if _cache is None:
                _cache = {}
            return _cache

        if force or _cache is None or mtime != _mtime:
            try:
                with open(DB_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    _cache = loaded
                    _mtime = mtime
            except (OSError, ValueError):
                if _cache is None:
                    _cache = {}
        return _cache if _cache is not None else {}


def lookup(day_ganji: str, iljin_ganji: str) -> Optional[Dict[str, Any]]:
    """조합에 해당하는 사전 생성 운세(raw dict)를 반환. 없으면 None."""
    return load_db().get(make_key(day_ganji, iljin_ganji))


def stats() -> Dict[str, Any]:
    db = load_db()
    return {"path": DB_PATH, "count": len(db), "expected": 3600}
