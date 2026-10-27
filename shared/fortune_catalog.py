"""복콩에 실제로 나가는 운세 목록.

메뉴에 없는 홈 운세와, 메뉴는 합쳐 보여도 API가 따로 있는 결과도 포함한다.
새 라우트나 새 JSON이 생기면 이 목록과 어긋나 테스트가 실패한다.
대운 문단 파일은 오행이 늘어도 daewoon_prose_*.json 으로 자동 포함된다.
"""
import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

from shared.prose_quality import (
    hard_surface_reason,
    raw_surface_issue,
    repeated_sentence_count,
    tension_unbridged,
    voice_flag,
    walk_strings,
)

ROOT = Path(__file__).resolve().parents[1]

# 운세 문장이 아닌 라우트. 이유를 적지 않으면 테스트가 빈칸을 실패로 본다.
EXCLUDED_ROUTES = {
    "/api/v1/saju/chart": "만세력 명식은 간지 계산이라 운세 문장이 아니다.",
}

# 홈 그리드 밖이지만 서비스에 있는 결과.
# daily: 홈의 오늘의 운세. ideal_partner: 연애 배너.
# yearly_travel, yearly_hobby: 메뉴는 여행·취미 통합만 보여도 단독 API가 남아 있다.

def _p(pid, label, group, endpoints, sections, voice, files, hooks, topic_policy="field", globs=(), code=(), documents=()):
    return {
        "id": pid,
        "label": label,
        "group": group,
        "endpoints": tuple(endpoints),
        "sections": tuple(sections),
        "voice": voice,
        "files": tuple(files),
        "globs": tuple(globs),
        "code": tuple(code),
        "documents": tuple(documents),
        "hooks": tuple(hooks),
        "topic_policy": topic_policy,
    }


PRODUCTS = (
    _p(
        "daily", "오늘의 운세", "DAILY",
        ("/api/v1/daily/fortune",),
        ("한줄평", "Today Insight", "Money Flow", "Love Radar", "Today Level Up", "Social Network", "오늘의 에너지"),
        "any",
        (
            "domains/daily/data/daily_db.json",
            "domains/daily/data/headline_pool.json",
            "domains/daily/data/today_energy_pool.json",
        ),
        ("domains/daily/service.py",),
        code=("domains/daily/woon_modifier.py", "domains/daily/social_template.py", "domains/daily/status_variants.py"),
    ),
    _p(
        "wealth", "오늘의 재테크", "DAILY",
        ("/api/v1/wealth/analysis",),
        ("시장 포인트", "투자운", "소비운", "돈의 흐름", "주의할 점"),
        "hamnida",
        (),
        ("domains/wealth/service.py",),
        code=("domains/wealth/fragments.py", "domains/wealth/engine.py", "domains/market/briefing.py"),
    ),
    _p(
        "tarot", "타로", "DAILY",
        ("/api/v1/tarot/read",),
        ("오늘의 타로", "재테크 타로", "애정운 타로", "한 줄", "카드 의미", "조언", "오늘의 메시지"),
        "any",
        ("domains/tarot/data/tarot_love_db.json",),
        ("domains/tarot/service.py",),
        documents=("domains/tarot/타로카드 설명.docx",),
    ),
    _p(
        "lifelong", "평생운세", "PERSONAL",
        ("/api/v1/lifelong/analysis",),
        ("사주 풍경", "타고난 성향", "재물", "직업", "가족", "사회", "초년", "중년", "말년", "대운 단계", "하이라이트"),
        "any",
        (
            "domains/lifelong/data/lifelong_base_db.json",
            "domains/lifelong/data/lifelong_domains_db.json",
            "domains/lifelong/data/lifelong_stage_db.json",
            "domains/lifelong/data/lifelong_stage_detail_db.json",
        ),
        ("domains/lifelong/service.py",),
        code=(
            "domains/lifelong/landscape.py",
            "domains/lifelong/life_periods.py",
            "domains/lifelong/highlight.py",
            "domains/lifelong/spouse_outlook.py",
        ),
    ),
    _p(
        "daewoon", "10년 대운", "PERSONAL",
        ("/api/v1/daewoon/analysis",),
        ("이 10년의 풍경", "사주와의 관계", "핵심 영역", "10년 이야기", "행동 지침", "20년 이야기"),
        "hamnida",
        ("domains/daewoon/data/twenty_year_arc_db.json",),
        ("domains/daewoon/service.py",),
        globs=("domains/daewoon/data/daewoon_prose_*.json",),
        code=("domains/daewoon/content.py", "domains/daewoon/twenty_year.py"),
    ),
    _p(
        "personality_character", "나의 성격", "PERSONAL",
        ("/api/v1/personality/character",),
        ("풍경", "연결 문장", "성격 본문"),
        "any",
        ("domains/personality/data/personality_db.json",),
        ("domains/personality/service.py",),
    ),
    _p(
        "personality_aptitude", "나의 적성", "PERSONAL",
        ("/api/v1/personality/aptitude",),
        ("풍경", "연결 문장", "적성 본문"),
        "any",
        ("domains/personality/data/personality_db.json",),
        ("domains/personality/service.py",),
    ),
    _p(
        "compatibility", "궁합", "PERSONAL",
        ("/api/v1/compatibility/analyze",),
        ("종합운", "애정 궁합", "소통", "갈등 요소", "갈등 해결법", "경제 궁합", "관계 조언"),
        "any",
        ("domains/compatibility/data/compatibility_db.json",),
        ("domains/compatibility/service.py",),
    ),
    _p(
        "reunion", "재회운", "PERSONAL",
        ("/api/v1/relationship/reunion",),
        ("총운", "매력", "3개월 전략"),
        "any",
        ("domains/relationship/data/relationship_db.json", "domains/relationship/data/reunion_charm_db.json"),
        ("domains/relationship/service.py",),
    ),
    _p(
        "crush", "짝사랑운", "PERSONAL",
        ("/api/v1/relationship/crush",),
        ("총운", "매력", "3개월 전략"),
        "any",
        ("domains/relationship/data/relationship_db.json", "domains/relationship/data/crush_charm_db.json"),
        ("domains/relationship/service.py",),
    ),
    _p(
        "marriage", "결혼운", "PERSONAL",
        ("/api/v1/relationship/marriage",),
        ("총운", "커플 총평", "시기", "배우자 유형", "준비"),
        "any",
        ("domains/relationship/data/relationship_db.json",),
        ("domains/relationship/service.py",),
    ),
    _p(
        "ideal_partner", "운명의 인연", "PERSONAL",
        ("/api/v1/love/ideal-partner",),
        ("나의 진단", "보완 상대", "상대 성향", "함께할 때의 흐름"),
        "haeyo",
        (),
        ("domains/love/service.py",),
        code=("domains/love/engine.py",),
    ),
    _p(
        "yearly_overall", "총운", "YEARLY",
        ("/api/v1/yearly/overall",),
        ("올해 전체 흐름", "상반기 흐름", "하반기 흐름", "올해 꼭 기억할 조언"),
        "any",
        ("domains/yearly/data/yearly_overall_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_wealth", "재물운", "YEARLY",
        ("/api/v1/yearly/wealth",),
        ("올해 재물 전체 흐름", "올해 나의 수입 스타일", "소비 패턴·절약 포인트", "올해 투자·재테크 운"),
        "any",
        ("domains/yearly/data/yearly_wealth_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_love", "연애운", "YEARLY",
        ("/api/v1/yearly/love",),
        ("올해 연애 전체 흐름", "새로운 인연이 오는 방식", "관계가 깊어지는 방식", "올해 연애에서 조심할 점"),
        "any",
        ("domains/yearly/data/yearly_love_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_business", "사업운", "YEARLY",
        ("/api/v1/yearly/business",),
        ("올해 사업 전체 흐름", "올해 나의 사업가 기질", "올해 사업 방향성", "확장하기 좋은 시기", "사업 파트너·협업운"),
        "any",
        ("domains/yearly/data/yearly_business_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_career_change", "직장·이직운", "YEARLY",
        ("/api/v1/yearly/career_change",),
        ("올해 직장운 전체 흐름", "올해 이직 평가", "이직 기회가 오는 방식", "나에게 맞는 직장 환경", "이직·승진 타이밍 흐름"),
        "any",
        ("domains/yearly/data/yearly_career_change_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_study", "학업운", "YEARLY",
        ("/api/v1/yearly/study",),
        ("올해 학업·배움 전체 흐름", "나에게 맞는 학습 방식", "집중력과 성취운", "도전하면 좋은 분야"),
        "any",
        ("domains/yearly/data/yearly_study_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_health", "건강운", "YEARLY",
        ("/api/v1/yearly/health",),
        ("올해 컨디션 전체 흐름", "올해 신경 쓸 관리 포인트", "나에게 맞는 회복법"),
        "any",
        ("domains/yearly/data/yearly_health_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_travel", "여행운", "YEARLY",
        ("/api/v1/yearly/travel",),
        ("올해 이동·여행 전체 흐름", "나에게 맞는 여행 스타일", "여행 중 들어오는 행운", "추천 장소·여행 시기"),
        "any",
        ("domains/yearly/data/yearly_travel_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "yearly_hobby", "취미운", "YEARLY",
        ("/api/v1/yearly/hobby",),
        ("올해 취미·여가 전체 흐름", "올해 잘 맞는 활동", "혼자 vs 함께, 올해 맞는 쪽", "취미로 올해 얻게 되는 것"),
        "any",
        ("domains/yearly/data/yearly_hobby_db.json",),
        ("domains/yearly/service.py",),
    ),
    _p(
        "travel_hobby", "여행·취미", "YEARLY",
        ("/api/v1/yearly/travel-hobby",),
        (
            "올해의 여가운", "여행 스타일", "다녀오기 좋은 시기", "잘 맞는 취미",
            "올해 내 취미는 혼자 vs 함께", "올해 얻게 될 수확",
        ),
        "any",
        ("domains/yearly/data/yearly_travel_db.json", "domains/yearly/data/yearly_hobby_db.json"),
        ("domains/yearly/service.py",),
        topic_policy="travel_sections",
    ),
)

MENU_TO_PRODUCT = {
    "financial": "wealth",
    "tarot": "tarot",
    "financial_tarot": "tarot",
    "love_tarot": "tarot",
    "lifetime": "lifelong",
    "decade_daewoon": "daewoon",
    "personality": "personality_character",
    "aptitude": "personality_aptitude",
    "compatibility": "compatibility",
    "reunion": "reunion",
    "crush": "crush",
    "marriage": "marriage",
    "general": "yearly_overall",
    "wealth": "yearly_wealth",
    "love": "yearly_love",
    "business": "yearly_business",
    "job": "yearly_career_change",
    "study": "yearly_study",
    "health": "yearly_health",
    "travel_hobby": "travel_hobby",
}


def by_id(product_id: str) -> dict:
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    raise KeyError(product_id)


def section_checker(product_id: str):
    """섹션 의미를 걸러 내는 조립기가 있으면 그 함수를 돌려준다."""
    if by_id(product_id)["topic_policy"] != "travel_sections":
        return None
    from domains.yearly.travel_hobby import fits_section
    return fits_section


def disk_data_files() -> List[str]:
    found = []
    for path in (ROOT / "domains").rglob("*.json"):
        found.append(path.relative_to(ROOT).as_posix())
    return sorted(found)


def covered_data_files() -> List[str]:
    found = set()
    for product in PRODUCTS:
        found.update(product["files"])
        for pattern in product["globs"]:
            for path in ROOT.glob(pattern):
                found.add(path.relative_to(ROOT).as_posix())
    return sorted(found)


def discover_posts() -> List[str]:
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    alias = {
        name: module.replace(".", "/") + ".py"
        for module, name in re.findall(
            r"from (domains\.\w+\.router) import router as (\w+)", main
        )
    }
    posts = []
    for name, prefix in re.findall(r'include_router\(\s*(\w+)\s*,\s*prefix="([^"]+)"', main):
        text = (ROOT / alias[name]).read_text(encoding="utf-8")
        for route in re.findall(r'@router\.post\(\s*"([^"]+)"', text):
            full = prefix + route
            if full.endswith("/{category}"):
                from domains.yearly.service import CATEGORIES
                base = full[: -len("/{category}")]
                posts.extend(f"{base}/{category}" for category in CATEGORIES)
            else:
                posts.append(full)
    return posts


def covered_endpoints() -> List[str]:
    found = []
    for product in PRODUCTS:
        found.extend(product["endpoints"])
    return found


def _empty_counts() -> Dict[str, int]:
    return {
        "strings": 0,
        "typo": 0,
        "spacing": 0,
        "greeting": 0,
        "dangling": 0,
        "off_voice": 0,
        "voice_mix": 0,
        "duplicate": 0,
        "tension": 0,
    }


def _consume(text: str, voice: str, counts: Dict[str, int]) -> None:
    if not isinstance(text, str) or len(text) < 8:
        return
    counts["strings"] += 1
    issue = raw_surface_issue(text)
    if issue:
        counts[issue] += 1
    dangling = hard_surface_reason(text)
    if dangling:
        counts[dangling] += 1
    flag = voice_flag(text, voice)
    if flag:
        counts[flag] += 1
    if repeated_sentence_count(text):
        counts["duplicate"] += 1
    if tension_unbridged(text):
        counts["tension"] += 1


def _consume_tree(value: Any, voice: str, counts: Dict[str, int]) -> None:
    for text in walk_strings(value):
        _consume(text, voice, counts)


def _code_strings(path: Path) -> Iterable[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def audit_all() -> Dict[str, Any]:
    """저장된 문장과 룰베이스 문장을 제품마다 한 번씩 센다. 파일을 고치지 않는다."""
    rows = []
    seen_files = set()
    for product in PRODUCTS:
        counts = _empty_counts()
        opened = []
        for rel in list(product["files"]) + [
            path.relative_to(ROOT).as_posix()
            for pattern in product["globs"]
            for path in ROOT.glob(pattern)
        ]:
            if rel in seen_files and rel not in product["files"]:
                # 글로브가 처음 연 파일은 세고, 다른 제품이 같은 파일을 또 열 때는 다시 센다.
                pass
            path = ROOT / rel
            opened.append(rel)
            seen_files.add(rel)
            with path.open(encoding="utf-8") as handle:
                _consume_tree(json.load(handle), product["voice"], counts)
        for rel in product["code"]:
            opened.append(rel)
            for text in _code_strings(ROOT / rel):
                _consume(text, product["voice"], counts)
        for rel in product["documents"]:
            opened.append(rel)
            if product["id"] == "tarot":
                from domains.tarot.content import load_card_content
                cards = load_card_content()
                if not cards:
                    raise RuntimeError(f"타로 원문을 읽지 못했다: {rel}")
                _consume_tree(cards, product["voice"], counts)
        rows.append({
            "id": product["id"],
            "label": product["label"],
            "group": product["group"],
            "voice": product["voice"],
            "topic_policy": product["topic_policy"],
            "sections": list(product["sections"]),
            "opened": opened,
            "counts": counts,
        })
    disk = disk_data_files()
    covered = set(covered_data_files())
    posts = discover_posts()
    endpoints = set(covered_endpoints())
    return {
        "products": rows,
        "uncovered_files": sorted(set(disk) - covered),
        "extra_files": sorted(covered - set(disk)),
        "uncovered_routes": sorted(set(posts) - endpoints - set(EXCLUDED_ROUTES)),
        "unknown_exclusions": sorted(set(EXCLUDED_ROUTES) - set(posts)),
    }
