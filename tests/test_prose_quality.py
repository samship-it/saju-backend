"""복콩 전체 문장 검사. 일부 카테고리만 통과해도 끝나지 않는다."""
import re
from pathlib import Path

from shared.fortune_catalog import (
    EXCLUDED_ROUTES,
    MENU_TO_PRODUCT,
    PRODUCTS,
    ROOT,
    audit_all,
    by_id,
    covered_data_files,
    covered_endpoints,
    discover_posts,
    disk_data_files,
    section_checker,
)
from shared.prose_quality import (
    finish_reading,
    hard_surface_reason,
    lead_names_activity,
    polish_text,
    review_text,
    tension_unbridged,
)

_YEARLY_SCREEN = {
    "travel_hobby": "travel_hobby",
    "business": "yearly_business",
    "career_change": "yearly_career_change",
    "health": "yearly_health",
    "travel": "yearly_travel",
    "hobby": "yearly_hobby",
    "study": "yearly_study",
    "wealth": "yearly_wealth",
    "love": "yearly_love",
}


def test_every_stored_file_and_route_belongs_to_a_product():
    assert set(disk_data_files()) == set(covered_data_files())
    posts = set(discover_posts())
    assert posts == set(covered_endpoints()) | set(EXCLUDED_ROUTES)
    assert not (set(covered_endpoints()) & set(EXCLUDED_ROUTES))
    ids = [product["id"] for product in PRODUCTS]
    assert len(ids) == len(set(ids))
    for product in PRODUCTS:
        assert product["sections"]
        assert product["topic_policy"] in ("field", "travel_sections")
        assert product["endpoints"]
        blob = "\n".join((ROOT / hook).read_text(encoding="utf-8") for hook in product["hooks"])
        assert "finish_reading" in blob, product["id"]


def test_menu_and_yearly_sections_match_the_catalog():
    menu = ROOT.parent / "today-score-magic" / "src" / "components" / "FortuneMenuSections.tsx"
    screen = ROOT.parent / "today-score-magic" / "src" / "components" / "YearlyResult.tsx"
    if not menu.exists() or not screen.exists():
        return
    categories = set(re.findall(r'category:\s*"([^"]+)"', menu.read_text(encoding="utf-8")))
    assert categories == set(MENU_TO_PRODUCT)
    assert set(MENU_TO_PRODUCT.values()) <= {product["id"] for product in PRODUCTS}

    text = screen.read_text(encoding="utf-8")
    overall = text.split("const SECTIONS:", 1)[1].split("const YEARLY_LABEL", 1)[0]
    assert list(by_id("yearly_overall")["sections"]) == re.findall(r'title:\s*"([^"]+)"', overall)
    block = text.split("const V2_FIELD_CONFIG", 1)[1].split("function StarRow", 1)[0]
    found = {}
    for name, body in re.findall(r"(\w+):\s*\[(.*?)\]", block, re.S):
        found[name] = re.findall(r'title:\s*"([^"]+)"', body)
    assert set(found) == set(_YEARLY_SCREEN)
    for name, titles in found.items():
        assert list(by_id(_YEARLY_SCREEN[name])["sections"]) == titles


def test_surface_fixes_do_not_thin_a_real_sentence():
    rich = "무거운 중량을 들어 올리면 몰입이 찾아옵니다. 운동이 끝난 뒤 해방감을 느낍니다."
    assert polish_text(rich) == rich
    fixed = polish_text("안녕하세요, 호랑이님! 오늘은  제테크를  천천히 보세요 .")
    assert "안녕" not in fixed
    assert "제테크" not in fixed
    assert "재테크" in fixed
    assert "  " not in fixed
    assert " ." not in fixed
    payload, flag = finish_reading({"one_line": "오늘은  제테크예요.", "nickname": "제테크왕"}, False)
    assert payload["one_line"] == "오늘은 재테크예요."
    assert payload["nickname"] == "제테크왕"
    assert flag is False
    assert hard_surface_reason("오늘은 조금 더 움직여야 하고") == "dangling"
    assert hard_surface_reason("오늘은 움직이면 좋아요.") == ""
    repeated = "같은 문장을 그대로 한 번 더 적었습니다. 같은 문장을 그대로 한 번 더 적었습니다."
    assert review_text(repeated) == ["duplicate"]


def test_tension_needs_a_bridge_and_hobby_lead_names_the_activity():
    assert tension_unbridged("강행군으로 가고, 충분히 쉬어야 합니다.")
    assert not tension_unbridged("강행군으로 가되, 다만 충분히 쉬어야 합니다.")
    assert not lead_names_activity("무거운 중량을 들어 올리면 몰입이 찾아옵니다.")
    assert lead_names_activity("올해 잘 맞는 취미는 웨이트 트레이닝이에요. 몰입이 찾아옵니다.")
    assert lead_names_activity("이미 손이 가는 것 하나에 머무는 편이 맞아요.")
    checker = section_checker("travel_hobby")
    assert checker("hobby_gain", "일정을 계속 늘리면 다녀와도 남지 않아요.", "hobby_gain") is False
    assert checker("hobby_gain", "그림을 그리며 표현이 분명해져요.", "hobby_gain") is True
    assert section_checker("yearly_love") is None


def test_audit_reads_every_product():
    report = audit_all()
    assert report["uncovered_files"] == []
    assert report["extra_files"] == []
    assert report["uncovered_routes"] == []
    assert report["unknown_exclusions"] == []
    rows = {row["id"]: row for row in report["products"]}
    assert set(rows) == {product["id"] for product in PRODUCTS}
    for product in PRODUCTS:
        row = rows[product["id"]]
        assert row["counts"]["strings"] > 0, product["id"]
        assert row["sections"] == list(product["sections"])
