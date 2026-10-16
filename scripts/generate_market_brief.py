"""아침 시황 LLM 브리핑.

재테크 API 요청 중에는 호출하지 않는다. 평일 09:05 KST 이후에 한 번 실행하면
그날 시장 포인트와 투자 조언 문장을 data/market_briefs 에 저장하고, 재테크 응답이 그 문장을 쓴다.
LLM 이 실패하면 파일을 쓰지 않아 요청 경로의 룰 문장이 유지된다.

예: python scripts/generate_market_brief.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import wealth_asof_date
from domains.market.briefing import collect_morning_facts, generate_llm_brief, save_brief
from domains.market.indicators import get_daily_market_direction


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD. 비우면 재테크 기준일(KST 09:00).")
    args = parser.parse_args()
    target = args.date or wealth_asof_date().isoformat()
    market = get_daily_market_direction(target)
    facts = collect_morning_facts(target, market)
    copy, used_llm = generate_llm_brief(facts)
    if not used_llm:
        print(f"{target}: LLM 요약을 만들지 못해 저장하지 않았습니다.")
        return 1
    save_brief(target, copy, source="llm", facts=facts)
    print(f"{target}: 아침 시황 브리핑을 저장했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
