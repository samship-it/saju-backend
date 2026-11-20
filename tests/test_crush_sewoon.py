"""단독 짝사랑 종합운은 원국과 그해 세운으로 연애운을 가른다."""
import datetime

from core.saju_base import calculate_saju
from domains.relationship import content_db
from domains.relationship.crush_brief import build_crush_brief
from domains.relationship.service import (
    analyze_crush,
    analyze_marriage,
    analyze_reunion,
)

_PERSON = {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}
_PARTNER = {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"}


def test_db_has_fifteen_sentences():
    db = content_db.load_crush_sewoon_db(force=True)
    assert set(db) == {
        "비겁", "식상", "재성", "관성", "인성",
        "비겁+식상", "비겁+재성", "비겁+관성", "비겁+인성",
        "식상+재성", "식상+관성", "식상+인성",
        "재성+관성", "재성+인성", "관성+인성",
    }
    assert all(isinstance(text, str) and text.strip() for text in db.values())
    assert len({text for text in db.values()}) == 15


def test_key_ignores_stem_branch_order():
    assert content_db.crush_sewoon_key("인성", "비겁") == "비겁+인성"
    assert content_db.crush_sewoon_key("비겁", "인성") == "비겁+인성"
    assert content_db.crush_sewoon_lookup("인성+비겁") is None
    assert content_db.crush_sewoon_lookup("비겁+인성")
    assert content_db.crush_sewoon_key("비겁", "비겁") == "비겁"
    assert content_db.crush_sewoon_key("미정", "비겁") is None


def test_two_factors_pick_one_of_five_and_one_factor_stays_weak():
    from domains.relationship.crush_year_flow import HOLD, OUTWARD, STAY, _TEXT, assess

    seen = {STAY: set(), HOLD: set(), OUTWARD: set()}
    weak = 0
    for year, month, day, gender in (
        (1990, 1, 9, "female"),
        (1990, 1, 9, "male"),
        (1988, 11, 2, "female"),
        (1983, 5, 14, "male"),
        (1992, 7, 8, "female"),
    ):
        for target in (datetime.date(2026, 6, 1), datetime.date(2032, 6, 1)):
            saju = calculate_saju(
                year, month, day, 14, 0, gender=gender, target_date=target,
            )
            reading = assess(saju)
            assert reading is not None
            assert sum(reading["factors"].values()) >= 2 or reading["love"] is False
            if reading["love"]:
                assert reading["text"] in _TEXT[reading["flow"]]
                assert sum(reading["factors"].values()) >= 2
                seen[reading["flow"]].add(reading["text"])
            else:
                weak += 1
                assert reading["text"] is None
    assert weak
    assert any(seen.values())


def test_same_chart_keeps_the_sentence_inside_a_year():
    from domains.relationship.crush_year_flow import assess

    early = calculate_saju(1992, 7, 8, 14, 0, gender="female", target_date=datetime.date(2026, 1, 1))
    late = calculate_saju(1992, 7, 8, 14, 0, gender="female", target_date=datetime.date(2026, 12, 31))
    assert assess(early)["text"] == assess(late)["text"]
    assert assess(early)["love"] == assess(late)["love"]


def test_target_date_year_selects_the_sentence_and_day_branch_does_too():
    births = {}
    day = datetime.date(1990, 1, 1)
    while len(births) < 10 and day.year == 1990:
        saju = calculate_saju(day.year, day.month, day.day, 12, 0, target_date=datetime.date(2026, 6, 1))
        births.setdefault(saju["day_master"], (day, saju["day_branch"]))
        day += datetime.timedelta(days=1)
    assert len(births) == 10

    stem, (birth, branch) = "甲", births["甲"]
    other = None
    day = datetime.date(1990, 1, 1)
    while other is None and day.year == 1990:
        saju = calculate_saju(day.year, day.month, day.day, 12, 0, target_date=datetime.date(2026, 6, 1))
        if saju["day_master"] == stem and saju["day_branch"] != branch:
            other = day
        day += datetime.timedelta(days=1)
    assert other is not None

    def person(when):
        return {
            "year": when.year, "month": when.month, "day": when.day,
            "hour": 12, "minute": 0, "gender": "female",
        }

    first, fallback_first = analyze_crush(person(birth), None, "2026-06-01")
    second, fallback_second = analyze_crush(person(other), None, "2026-06-01")
    early, fallback_early = analyze_crush(person(birth), None, "2026-01-01")
    late, fallback_late = analyze_crush(person(birth), None, "2026-12-31")
    previous, fallback_previous = analyze_crush(person(birth), None, "2025-06-01")
    assert fallback_first is False
    assert fallback_second is False
    assert fallback_early is False
    assert fallback_late is False
    assert first["overall"] == early["overall"] == late["overall"]
    chart = calculate_saju(
        birth.year, birth.month, birth.day, 12, 0, target_date=datetime.date(2026, 6, 1),
    )
    other_chart = calculate_saju(
        other.year, other.month, other.day, 12, 0, target_date=datetime.date(2026, 6, 1),
    )
    from domains.relationship.crush_year_flow import assess

    stored = assess(chart)
    other_stored = assess(other_chart)
    assert stored["text"] is None or stored["text"].replace(" ", "") in first["overall"].replace(" ", "").replace("\n", "")
    if not stored["love"]:
        assert "흐름이 크게 요동" in first["overall"]
    assert other_stored is not None
    previous_chart = calculate_saju(
        birth.year, birth.month, birth.day, 12, 0, target_date=datetime.date(2025, 6, 1),
    )
    previous_stored = assess(previous_chart)
    assert fallback_previous is False
    if previous_stored["love"]:
        assert previous_stored["text"].replace(" ", "") in previous["overall"].replace(" ", "").replace("\n", "")
    else:
        assert "흐름이 크게 요동" in previous["overall"]
    assert previous_chart["seewoon_10years"][0]["ganji"] != chart["seewoon_10years"][0]["ganji"]
    assert previous["target_date"] == "2025-06-01"
    assert first["target_date"] == "2026-06-01"


def test_partner_crush_reunion_marriage_and_other_sections_stay():
    couple, couple_fallback = analyze_crush(_PERSON, _PARTNER, "2026-06-01")
    self_saju = calculate_saju(1992, 7, 8, 14, 0, gender="female", target_date=datetime.date(2026, 6, 1))
    partner_saju = calculate_saju(1990, 3, 15, 10, 30, gender="male", target_date=datetime.date(2026, 6, 1))
    stored = content_db.lookup(self_saju["day_ganji"], partner_saju["day_ganji"], "crush")
    assert couple_fallback is False
    assert stored["overall"][:24] in couple["overall"].replace("\n", "")
    assert "strategy_3months" in couple
    solo, solo_fallback = analyze_crush(_PERSON, None, "2026-06-01")
    assert solo_fallback is False
    assert stored["overall"][:24] not in solo["overall"]
    old_solo = content_db.lookup(self_saju["day_ganji"], None, "crush")
    assert old_solo["overall"][:24] not in solo["overall"]
    assert "마음에 드는 상대가 생겼다면" in content_db.lookup("甲子", None, "crush")["overall"]

    brief = build_crush_brief(self_saju["day_ganji"], None)
    assert [row["title"] for row in solo["crush_sections"]] == [row["title"] for row in brief["sections"]]
    assert solo["crush_sections"][0]["text"] == brief["sections"][0]["text"]
    assert solo["crush_sections"][1]["text"] == brief["sections"][1]["text"]
    assert solo["headline"] == brief["headline"]
    charm = content_db.charm_lookup(self_saju["day_ganji"], "crush")
    assert charm[:24] in solo["your_charm"].replace("\n", "")

    reunion, reunion_fallback = analyze_reunion(_PERSON, None, "2026-06-01")
    reunion_stored = content_db.lookup(self_saju["day_ganji"], None, "reunion")
    assert reunion_fallback is False
    assert reunion_stored["overall"][:24] in reunion["overall"].replace("\n", "")
    assert "crush_sections" not in reunion

    marriage, marriage_fallback = analyze_marriage(_PERSON, None, 2026, "2026-06-01")
    marriage_stored = content_db.lookup(self_saju["day_ganji"], None, "marriage")
    assert marriage_fallback is False
    assert marriage_stored["overall"][:24] in marriage["overall"].replace("\n", "")


def test_weak_year_uses_the_existing_sentence_without_a_type():
    from domains.relationship.crush_year_flow import assess

    found = None
    day = datetime.date(1990, 1, 1)
    while found is None and day.year == 1990:
        saju = calculate_saju(day.year, day.month, day.day, 12, 0, gender="female", target_date=datetime.date(2026, 6, 1))
        reading = assess(saju)
        if reading and not reading["love"]:
            found = day
        day += datetime.timedelta(days=1)
    assert found is not None
    data, is_fallback = analyze_crush(
        {"year": found.year, "month": found.month, "day": found.day, "hour": 12, "minute": 0, "gender": "female"},
        None,
        "2026-06-01",
    )
    assert is_fallback is False
    assert "흐름이 크게 요동" in data["overall"]
    stored = content_db.lookup(
        calculate_saju(found.year, found.month, found.day, 12, 0, gender="female")["day_ganji"],
        None,
        "crush",
    )
    assert stored["overall"][:24] not in data["overall"]
    couple, couple_fallback = analyze_crush(_PERSON, _PARTNER, "2026-06-01")
    assert couple_fallback is False
    assert "흐름이 크게 요동" not in couple["overall"]
