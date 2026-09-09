"""사전 생성된 '궁합' 정적 DB 접근 계층.

60 일주(본인) × 60 일주(상대) = 3,600개 순서쌍의 AI 서술(report 7필드)을 미리 생성해
`domains/compatibility/data/compatibility_db.json` 에 저장해 둔다. 런타임(service)은
이 파일에서 일주쌍 키로 즉시 조회만 하며 Gemini 를 호출하지 않는다.

점수·한줄평·관계 요소(positive/negative factors 등)는 런타임 엔진
(`calculate_compatibility_interactions`)이 두 사람의 전체 사주로 계산하고,
여기 저장된 것은 일주쌍 기준의 순수 AI 서술뿐이다. (daily/personality/relationship 과
동일한 '일주 중심' 트레이드오프.)

배포에 포함되는 정적 파일이므로 프로세스당 최초 1회만 읽어 메모리에 둔다.
DB 를 다시 생성했다면 프로세스를 재시작하거나 `reload()` 를 호출한다.

키 형식: "<본인 일주>_<상대 일주>"  (한자 2자 + "_" + 한자 2자), 예) "甲子_乙丑".
        본인(person1) 시점 서술이라 순서가 있다 — "甲子_乙丑" ≠ "乙丑_甲子".
값 스키마: {"overall", "love", "communication", "conflict",
           "conflict_resolution", "economy", "relationship_advice"}  (+ "_model")
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("COMPATIBILITY_DB_PATH", os.path.join(DATA_DIR, "compatibility_db.json"))

FIELDS = ("overall", "love", "communication", "conflict",
          "conflict_resolution", "economy", "relationship_advice")

_lock = threading.Lock()
_cache: Optional[Dict[str, Any]] = None


def make_key(self_ganji: str, partner_ganji: str) -> str:
    """(본인 일주, 상대 일주) -> DB 조회 키. 예) "甲子_乙丑"."""
    return f"{(self_ganji or '').strip()}_{(partner_ganji or '').strip()}"


def load_db(force: bool = False) -> Dict[str, Any]:
    """compatibility_db.json 을 최초 1회 읽어 메모리에 캐시한다(정적 파일)."""
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


def lookup(self_ganji: str, partner_ganji: str) -> Optional[Dict[str, Any]]:
    """일주쌍에 해당하는 사전 생성 서술(7필드 dict)을 반환. 없거나 불완전하면 None."""
    entry = load_db().get(make_key(self_ganji, partner_ganji))
    if not isinstance(entry, dict):
        return None
    return entry if all(str(entry.get(k, "")).strip() for k in FIELDS) else None


def stats() -> Dict[str, Any]:
    db = load_db()
    return {"path": DB_PATH, "count": len(db), "expected": 3600}
