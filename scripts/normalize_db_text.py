"""사전 생성 콘텐츠 DB의 모든 텍스트 값에서 번호·순번 표기를 제거(정규화)한다.

대상: "1.", "1)", "(1)", "[1]", "1/6", "①" 같은 열거 기호. 자연어 숫자("5분",
"100점", "웹3", "9시부터 6시")는 건드리지 않는다(scripts/generate_content_db.py 의
strip_enumeration 을 그대로 사용).

사용:
  # 미리보기(변경 안 함)
  python scripts/normalize_db_text.py --domain personality
  python scripts/normalize_db_text.py --domain daily

  # 실제 적용(원자적 저장)
  python scripts/normalize_db_text.py --domain personality --apply
  python scripts/normalize_db_text.py --path some/other_db.json --apply
"""
import argparse
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.generate_content_db import (  # noqa: E402
    strip_enumeration, _atomic_write_json, DAILY_DB_PATH, PERSONALITY_DB_PATH,
)

_META_KEYS = {"_model", "_model_character", "_model_aptitude"}


def _walk(node, path=""):
    """(경로, 원본문자열, 정규화문자열) 중 바뀐 것만 yield. dict 는 제자리 수정."""
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k in _META_KEYS:
                continue
            if isinstance(v, str):
                nv = strip_enumeration(v)
                if nv != v:
                    node[k] = nv
                    yield (f"{path}.{k}" if path else k, v, nv)
            else:
                yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                nv = strip_enumeration(v)
                if nv != v:
                    node[i] = nv
                    yield (f"{path}[{i}]", v, nv)
            else:
                yield from _walk(v, f"{path}[{i}]")


def _diff_snippet(before: str, after: str) -> str:
    i = 0
    while i < min(len(before), len(after)) and before[i] == after[i]:
        i += 1
    return f"…{before[max(0, i - 15):i + 25]!r}  →  {after[max(0, i - 15):i + 25]!r}…"


def main() -> None:
    p = argparse.ArgumentParser(description="콘텐츠 DB 텍스트 번호표기 정규화")
    p.add_argument("--domain", choices=["daily", "personality"])
    p.add_argument("--path", type=str, help="직접 JSON 경로 지정 (--domain 대신)")
    p.add_argument("--apply", action="store_true", help="실제로 파일에 저장 (없으면 미리보기)")
    args = p.parse_args()

    path = args.path or {"daily": DAILY_DB_PATH, "personality": PERSONALITY_DB_PATH}.get(args.domain)
    if not path:
        p.error("--domain 또는 --path 중 하나는 필요합니다.")
    with open(path, "r", encoding="utf-8") as f:
        db = json.load(f)

    changes = list(_walk(db))
    print(f"DB: {path}")
    print(f"검사한 최상위 항목: {len(db)}개")
    print(f"번호표기가 발견되어 정규화한 필드: {len(changes)}개\n")
    for loc, before, after in changes[:200]:
        print(f"  [{loc}]  {_diff_snippet(before, after)}")
    if len(changes) > 200:
        print(f"  ... 외 {len(changes) - 200}개")

    if not changes:
        print("\n변경할 내용이 없습니다. (이미 깨끗함)")
        return
    if args.apply:
        _atomic_write_json(path, db)
        print(f"\n✅ 적용 완료 → {path}")
    else:
        print("\n(미리보기) --apply 를 붙이면 실제로 저장합니다.")


if __name__ == "__main__":
    main()
