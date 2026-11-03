"""검수 캐시와 월간 사용량.

캐시 키에는 원문, 프롬프트 버전, 모델, 정책 버전이 들어간다.
원문이나 버전이 다르면 저장된 결과를 쓰지 않는다.
sqlite 를 열 수 없으면 프로세스 메모리만 사용하고 운세 응답은 계속한다.
"""
import hashlib
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from shared.proofread.settings import policy_version, prompt_version, store_mode

logger = logging.getLogger("proofread")
_LOCK = threading.Lock()
_MEMORY: Dict[str, Any] = {"cache": {}, "usage": {}}
_SQLITE: Optional[sqlite3.Connection] = None
_SQLITE_FAILED = False


def reset_for_tests() -> None:
    global _SQLITE, _SQLITE_FAILED
    with _LOCK:
        _MEMORY["cache"].clear()
        _MEMORY["usage"].clear()
        if _SQLITE is not None:
            _SQLITE.close()
            _SQLITE = None
        _SQLITE_FAILED = False


def cache_key(original: str, model: str) -> str:
    raw = "\n".join((prompt_version(), policy_version(), model, original))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached(original: str, model: str) -> Optional[str]:
    key = cache_key(original, model)
    row = _cache_row(key)
    if not row:
        return None
    if row.get("original") != original:
        return None
    if row.get("prompt_version") != prompt_version():
        return None
    if row.get("policy_version") != policy_version():
        return None
    if row.get("model") != model:
        return None
    corrected = row.get("corrected")
    return corrected if isinstance(corrected, str) else None


def put_cached(original: str, model: str, corrected: str) -> None:
    key = cache_key(original, model)
    row = {
        "key": key,
        "original": original,
        "corrected": corrected,
        "prompt_version": prompt_version(),
        "policy_version": policy_version(),
        "model": model,
    }
    with _LOCK:
        _MEMORY["cache"][key] = row
        conn = _connection()
        if conn is None:
            return
        try:
            conn.execute(
                """INSERT INTO proofread_cache
                   (cache_key, original, corrected, prompt_version, policy_version, model)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(cache_key) DO UPDATE SET
                     original=excluded.original,
                     corrected=excluded.corrected,
                     prompt_version=excluded.prompt_version,
                     policy_version=excluded.policy_version,
                     model=excluded.model""",
                (key, original, corrected, row["prompt_version"], row["policy_version"], model),
            )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[proofread] 캐시 저장 실패. 메모리 결과만 유지합니다: %s", type(exc).__name__)


def usage(month: str) -> Dict[str, float]:
    with _LOCK:
        row = dict(_MEMORY["usage"].get(month) or _empty_usage())
        conn = _connection()
        if conn is None:
            return row
        try:
            found = conn.execute(
                "SELECT input_tokens, output_tokens, cost_usd FROM proofread_usage WHERE month = ?",
                (month,),
            ).fetchone()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[proofread] 사용량 조회 실패: %s", type(exc).__name__)
            return row
        if not found:
            return row
        disk = {
            "input_tokens": int(found[0] or 0),
            "output_tokens": int(found[1] or 0),
            "cost_usd": float(found[2] or 0),
        }
        # 디스크 저장이 실패한 직후에도 메모리에 쌓인 사용량을 예산에 반영한다.
        if float(row["cost_usd"]) >= disk["cost_usd"]:
            return row
        return disk


def add_usage(month: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    with _LOCK:
        current = _MEMORY["usage"].get(month) or _empty_usage()
        current["input_tokens"] += int(input_tokens)
        current["output_tokens"] += int(output_tokens)
        current["cost_usd"] = round(float(current["cost_usd"]) + float(cost_usd), 8)
        _MEMORY["usage"][month] = current
        conn = _connection()
        if conn is None:
            return
        try:
            conn.execute(
                """INSERT INTO proofread_usage (month, input_tokens, output_tokens, cost_usd)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(month) DO UPDATE SET
                     input_tokens = input_tokens + excluded.input_tokens,
                     output_tokens = output_tokens + excluded.output_tokens,
                     cost_usd = cost_usd + excluded.cost_usd""",
                (month, int(input_tokens), int(output_tokens), float(cost_usd)),
            )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[proofread] 사용량 저장 실패. 메모리 합계만 유지합니다: %s", type(exc).__name__)


def _empty_usage() -> Dict[str, float]:
    return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


def _cache_row(key: str) -> Optional[dict]:
    with _LOCK:
        if key in _MEMORY["cache"]:
            return _MEMORY["cache"][key]
        conn = _connection()
        if conn is None:
            return None
        try:
            found = conn.execute(
                """SELECT original, corrected, prompt_version, policy_version, model
                   FROM proofread_cache WHERE cache_key = ?""",
                (key,),
            ).fetchone()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[proofread] 캐시 조회 실패: %s", type(exc).__name__)
            return None
        if not found:
            return None
        row = {
            "original": found[0],
            "corrected": found[1],
            "prompt_version": found[2],
            "policy_version": found[3],
            "model": found[4],
        }
        _MEMORY["cache"][key] = row
        return row


def _connection() -> Optional[sqlite3.Connection]:
    global _SQLITE, _SQLITE_FAILED
    if store_mode() == "memory" or _SQLITE_FAILED:
        return None
    if _SQLITE is not None:
        return _SQLITE
    path = Path(__file__).resolve().parents[2] / "proofread_cache.db"
    try:
        os.makedirs(path.parent, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS proofread_cache (
                cache_key TEXT PRIMARY KEY,
                original TEXT NOT NULL,
                corrected TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                model TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS proofread_usage (
                month TEXT PRIMARY KEY,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL
            )"""
        )
        conn.commit()
        _SQLITE = conn
        return conn
    except Exception as exc:  # noqa: BLE001
        _SQLITE_FAILED = True
        logger.warning("[proofread] 캐시 DB를 열지 못했습니다. 메모리만 사용합니다: %s", type(exc).__name__)
        return None
