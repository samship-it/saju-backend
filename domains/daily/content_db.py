"""사전 생성된 '오늘의 운세' 정적 DB 접근 계층.

(내 일주 × 오늘 일진) = 60 × 60 = 3,600개 조합을 미리 Gemini 로 생성해
`domains/daily/data/daily_db.json` 에 저장해 둔다. 런타임(router)은 이 파일에서
키로 즉시 조회만 하며 Gemini 를 호출하지 않는다.

이 파일은 배포에 포함되는 정적 산출물이므로, 프로세스 시작 후 최초 1회만 읽어
메모리에 둔다(약 11MB JSON 을 매 요청마다 재파싱하지 않기 위함). DB 를 다시
생성했다면 프로세스를 재시작하거나 `reload()` 를 호출한다.

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


def make_key(day_ganji: str, iljin_ganji: str) -> str:
    """(내 일주, 오늘 일진) -> DB 조회 키. 예) "戊辰_乙巳"."""
    return f"{(day_ganji or '').strip()}_{(iljin_ganji or '').strip()}"


def load_db(force: bool = False) -> Dict[str, Any]:
    """daily_db.json 을 최초 1회 읽어 메모리에 캐시한다(정적 파일)."""
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


def lookup(day_ganji: str, iljin_ganji: str) -> Optional[Dict[str, Any]]:
    """조합에 해당하는 사전 생성 운세(raw dict)를 반환. 없으면 None."""
    return load_db().get(make_key(day_ganji, iljin_ganji))


def stats() -> Dict[str, Any]:
    db = load_db()
    return {"path": DB_PATH, "count": len(db), "expected": 3600}
