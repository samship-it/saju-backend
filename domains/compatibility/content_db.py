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


# 경제 카드만 다듬는다. 다른 필드는 일주 해설 그대로다.
_ECONOMY_REPLACEMENTS = (
    ("스타식", "스타일"),
    ("보름자리", "보금자리"),
    ("아주 탄탄한 경제력을 갖추게 될 거예요", "돈을 맞춰 가기가 한결 수월해질 거예요"),
    ("부러울 것 없는 탄탄한 경제력을 갖추게 됩니다", "돈을 맞춰 가는 기준을 세우기 쉽습니다"),
    ("탄탄한 경제력을 구축할 수 있습니다", "돈을 맞춰 가는 기준을 세우기 쉽습니다"),
    ("낭비 없는 완벽한 자산 운용이 가능해진답니다", "자산을 함께 살펴보기에 무리가 없는 편이에요"),
    ("낭비 없는 완벽한 자산 관리가 가능해집니다", "자산을 함께 살펴보기에 무리가 없는 편입니다"),
    ("낭비 없는 완벽한 경제적 안정을 누릴 수 있답니다", "돈을 헤프지 않게 맞춰 가기에 좋은 편이에요"),
    ("낭비 없는 완벽한 경제적 합을 이뤄요", "돈을 헤프지 않게 맞춰 가기 좋은 편이에요"),
    ("낭비 없는 완벽한 재정 팀을 결성할 수 있어요", "돈 문제를 함께 보기 좋은 편이에요"),
    ("완벽한 자산 증식 조합이 완성됩니다", "자산을 함께 살펴보기 좋은 조합입니다"),
    ("완벽한 자산 증식을 이뤄낼 수 있습니다", "자산을 함께 살펴볼 만합니다"),
    ("완벽한 자산 관리 파트너가 될 수 있어요", "자산을 함께 살펴보기 좋은 편이에요"),
    ("완벽한 자산 관리가 가능합니다", "자산을 함께 살펴보기 좋은 편입니다"),
    ("완벽한 자산 관리를 추구해요", "자산을 차근차근 살펴보는 편이에요"),
    ("언제나 풍족하고 평화로운 경제생활을 누릴 수 있을 거예요", "부담을 덜고 이야기를 이어 가기 쉬울 거예요"),
    ("언제나 풍족하고 평화로운 일상을 누릴 수 있을 거예요", "부담을 덜고 이야기를 이어 가기 쉬울 거예요"),
    ("알뜰살뜰하게 살림을 불려나갈 수 있어요", "알뜰살뜰하게 살림을 맞춰 가기 좋은 편이에요"),
    ("살림을 불려나갈 수 있습니다", "살림을 맞춰 가기 좋은 편입니다"),
    ("살림을 불려나가는", "살림을 맞춰 가는"),
    ("살림을 불려 나가는", "살림을 맞춰 가는"),
    ("만들어갈 수 있는 최고의 궁합입니다", "만들어 가기에 좋은 조합입니다"),
)


def polish_economy(text: str) -> str:
    """일주 해설의 경제 문장만 오타를 고치고, 재산·성공을 단정하는 말만 누그러뜨린다."""
    if not text:
        return text
    out = text
    for bad, good in _ECONOMY_REPLACEMENTS:
        if bad in out:
            out = out.replace(bad, good)
    return out


def lookup(self_ganji: str, partner_ganji: str) -> Optional[Dict[str, Any]]:
    """일주쌍에 해당하는 사전 생성 서술(7필드 dict)을 반환. 없거나 불완전하면 None."""
    entry = load_db().get(make_key(self_ganji, partner_ganji))
    if not isinstance(entry, dict):
        return None
    return entry if all(str(entry.get(k, "")).strip() for k in FIELDS) else None


def stats() -> Dict[str, Any]:
    db = load_db()
    return {"path": DB_PATH, "count": len(db), "expected": 3600}
