"""사전 생성된 '재회운 / 짝사랑운 / 결혼운' 정적 DB 접근 계층.

60 일주(본인) × {상대 없음 | 60 일주(상대)} × 3 유형(reunion/crush/marriage)
= 10,980개 조합의 AI 서술을 미리 생성해
`domains/relationship/data/relationship_db.json` 에 저장해 둔다. 런타임(service)은
이 파일에서 키로 즉시 조회만 하며 Gemini 를 호출하지 않는다.

날짜 의존 수치(다가오는 3개월의 실제 월, 결혼 10년 강도 창)는 런타임 엔진이 계산하고,
여기 저장된 것은 순수 AI 서술뿐이다. 3개월 전략도 특정 월이 아닌 "1/2/3개월차" 순번으로
생성돼 있어, service 가 엔진이 계산한 실제 월 라벨에 매핑한다.

배포에 포함되는 정적 파일이므로 프로세스당 최초 1회만 읽어 메모리에 둔다(약 18MB JSON).
DB 를 다시 생성했다면 프로세스를 재시작하거나 `reload()` 를 호출한다.

키 형식:
    "<본인 일주>_<유형>"            (상대 없음, 예 "甲子_reunion")
    "<본인 일주>_<상대 일주>_<유형>"  (상대 있음, 예 "甲子_乙丑_marriage")
값 스키마(유형·mode별):
    solo 전 유형            : {"overall": str}
    couple reunion/crush   : {"overall": str, "strategy_3months": [str, str, str]}
    couple marriage        : {"overall": str, "couple_overall": str}

재회운(reunion)은 별도 파일 `reunion_charm_db.json` 에서 '상대에게 어필할 나의 매력'
서술을 본인 일주(60개) 기준으로 조회해 응답의 your_charm 필드로 병합한다(solo/couple 공통).
"""
import json
import os
import threading
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("RELATIONSHIP_DB_PATH", os.path.join(DATA_DIR, "relationship_db.json"))
# 재회운 전용 '상대에게 어필할 나의 매력' — 본인 일주 60개 (사람 중심, 상대와 무관).
CHARM_DB_PATH = os.environ.get("REUNION_CHARM_DB_PATH", os.path.join(DATA_DIR, "reunion_charm_db.json"))

_VALID_TYPES = ("reunion", "crush", "marriage")

_lock = threading.Lock()
_cache: Optional[Dict[str, Any]] = None
_charm_cache: Optional[Dict[str, Any]] = None


def make_key(self_ganji: str, partner_ganji: Optional[str], rtype: str) -> str:
    """(본인 일주, 상대 일주 or None, 유형) -> DB 조회 키."""
    a = (self_ganji or "").strip()
    b = (partner_ganji or "").strip() if partner_ganji else ""
    return f"{a}_{b}_{rtype}" if b else f"{a}_{rtype}"


def load_db(force: bool = False) -> Dict[str, Any]:
    """relationship_db.json 을 최초 1회 읽어 메모리에 캐시한다(정적 파일)."""
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


def load_charm_db(force: bool = False) -> Dict[str, Any]:
    """reunion_charm_db.json 을 최초 1회 읽어 캐시한다(정적 파일, 약 60개)."""
    global _charm_cache
    if _charm_cache is not None and not force:
        return _charm_cache
    with _lock:
        if _charm_cache is not None and not force:
            return _charm_cache
        try:
            with open(CHARM_DB_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            _charm_cache = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            _charm_cache = {}
        return _charm_cache


def charm_lookup(self_ganji: str) -> Optional[str]:
    """재회운 '상대에게 어필할 나의 매력' 서술(본인 일주 기준). 없으면 None."""
    entry = load_charm_db().get((self_ganji or "").strip())
    if isinstance(entry, dict):
        entry = entry.get("your_charm")
    return entry if isinstance(entry, str) and entry.strip() else None


def reload() -> Dict[str, Any]:
    """DB 파일을 다시 생성한 뒤 메모리 캐시를 갱신할 때 호출(테스트/재생성용)."""
    load_charm_db(force=True)
    return load_db(force=True)


def lookup(self_ganji: str, partner_ganji: Optional[str], rtype: str) -> Optional[Dict[str, Any]]:
    """조합에 해당하는 사전 생성 서술(raw dict)을 반환. 없으면 None."""
    if rtype not in _VALID_TYPES:
        return None
    entry = load_db().get(make_key(self_ganji, partner_ganji, rtype))
    return entry if isinstance(entry, dict) and str(entry.get("overall", "")).strip() else None


def strategy_list(entry: Dict[str, Any]) -> List[str]:
    """couple reunion/crush 의 3개월 전략 문자열 3개. 부족하면 빈 리스트."""
    s = entry.get("strategy_3months")
    if isinstance(s, list):
        vals = [str(x).strip() for x in s if str(x).strip()]
        if len(vals) >= 3:
            return vals[:3]
    return []


def stats() -> Dict[str, Any]:
    db = load_db()
    return {"path": DB_PATH, "count": len(db), "expected": 10980}
