"""운세 결과 캐시 헬퍼.

기획 규칙: "한번 계산된 점수는 다시 분석이 되어도 같은 점수로 일관성 유지".
같은 입력(content_type + 정규화된 입력)에 대해 저장된 결과를 그대로 돌려준다.
폴백(is_fallback=True) 결과는 저장하지 않는다 (AI 연동 후 정식 값으로 대체되도록).
"""
import hashlib
import json
import logging
from typing import Any, Callable, Dict, Tuple

logger = logging.getLogger(__name__)


def make_key(content_type: str, payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{content_type}:{digest}"


def get_or_create(
    content_type: str,
    key_payload: Dict[str, Any],
    generator: Callable[[], Tuple[dict, bool]],
) -> Tuple[dict, bool, bool]:
    """(result, is_fallback, from_cache) 반환."""
    cache_key = make_key(content_type, key_payload)
    try:
        from core.database import db_session, FortuneCache

        row = db_session.query(FortuneCache).filter_by(cache_key=cache_key).first()
        if row and row.result_json:
            return row.result_json, False, True
    except Exception as e:  # 테이블 미생성 등
        logger.debug(f"fortune cache 조회 실패: {e}")

    result, is_fallback = generator()

    if not is_fallback:
        try:
            from core.database import db_session, FortuneCache

            db_session.add(FortuneCache(
                cache_key=cache_key, content_type=content_type, result_json=result,
            ))
            db_session.commit()
        except Exception as e:
            logger.debug(f"fortune cache 저장 실패: {e}")
            try:
                from core.database import db_session
                db_session.rollback()
            except Exception:
                pass

    return result, is_fallback, False
