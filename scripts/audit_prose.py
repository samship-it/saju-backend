"""저장된 운세 문장을 제품별로 센다. 파일은 고치지 않고, 조회 때 LLM을 부르지 않는다.

  python scripts/audit_prose.py C:\\path\\summary.json
"""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.fortune_catalog import audit_all  # noqa: E402


def main() -> None:
    report = audit_all()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in report["products"]:
        counts = row["counts"]
        print(
            f"{row['id']} strings={counts['strings']} typo={counts['typo']} "
            f"spacing={counts['spacing']} greeting={counts['greeting']} "
            f"dangling={counts['dangling']} off_voice={counts['off_voice']} "
            f"mix={counts['voice_mix']} duplicate={counts['duplicate']} tension={counts['tension']}"
        )
    print(
        "uncovered_files", len(report["uncovered_files"]),
        "uncovered_routes", len(report["uncovered_routes"]),
    )


if __name__ == "__main__":
    main()
