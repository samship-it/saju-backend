"""사전 생성된 '연간 운세' 정적 DB 접근 계층.

나의 일주(60) × 올해 세운 간지(60) = 3,600개 조합의 AI 서술을 카테고리별 파일로
미리 생성해 `domains/yearly/data/yearly_<category>_db.json` 에 저장해 둔다.
런타임(service)은 키로 즉시 조회만 하며 Gemini 를 호출하지 않는다.

세운 간지는 60갑자 순환이라 (일주, 세운)만으로 결정된다 → 연도 무관 재사용
(2026년 丙午 = 2086년 丙午 → 같은 일주면 같은 데이터). 12개월 월운 강도·베스트/주의
월은 원국 전체 강약에 따라 달라지므로 런타임 엔진이 계산한다(정적 텍스트엔 특정 월 없음).

키 형식: "<나의 일주>_<올해 세운 간지>"  예) "辛卯_丙午".

현재 파일:
    overall  : {"one_line", "keywords"[3], "overall_flow", "first_half", "second_half", "advice"}
    (나머지 8종은 순차 추가 예정)
"""
import json
import os
import threading
from typing import Any, Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _path(category: str) -> str:
    env = os.environ.get(f"YEARLY_{category.upper()}_DB_PATH")
    return env or os.path.join(DATA_DIR, f"yearly_{category}_db.json")


_lock = threading.Lock()
_cache: Dict[str, Dict[str, Any]] = {}


def make_key(self_ganji: str, seyun_ganji: str) -> str:
    return f"{(self_ganji or '').strip()}_{(seyun_ganji or '').strip()}"


def load_db(category: str, force: bool = False) -> Dict[str, Any]:
    cached = _cache.get(category)
    if cached is not None and not force:
        return cached
    with _lock:
        cached = _cache.get(category)
        if cached is not None and not force:
            return cached
        try:
            with open(_path(category), "r", encoding="utf-8") as f:
                loaded = json.load(f)
            _cache[category] = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            _cache[category] = {}
        return _cache[category]


def reload() -> None:
    for cat in list(_cache):
        load_db(cat, force=True)


# 6필드 스키마(총운·분야 8종 공통). 총운만 여기에 4필드(기회/주의달·치트키·쥐약)가 더 붙는다.
_SIXFIELD = ("one_line", "overall_flow", "first_half", "second_half", "advice")


def lookup(
    category: str, self_ganji: str, seyun_ganji: str,
    required: Optional[tuple] = None, key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """조합에 해당하는 사전 생성 서술(dict). 없거나 불완전하면 None.

    `required` 를 주면 그 필드들로 완전성을 검사한다(분야 v2 스키마처럼
    6필드가 아닌 카테고리용). 기본은 구 6필드 스키마(총운/재물/애정).
    `key` 를 주면 make_key 대신 그대로 조회 키로 쓴다(학업운의
    "<일주>_<세운>_<생애단계>" 처럼 3-파트 키).
    """
    entry = load_db(category).get(key or make_key(self_ganji, seyun_ganji))
    if not isinstance(entry, dict):
        return None
    need = required if required is not None else _SIXFIELD
    if not all(str(entry.get(k, "")).strip() for k in need):
        return None
    return entry


def stats(category: str = "overall") -> Dict[str, Any]:
    db = load_db(category)
    return {"path": _path(category), "count": len(db), "expected": 3600}
