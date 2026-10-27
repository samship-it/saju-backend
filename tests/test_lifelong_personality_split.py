"""평생 사주는 저장된 성격 원문을 그대로 두고, 성격운세만 행동 설명을 덧붙인다."""
from domains.lifelong.service import analyze_lifelong_fortune
from domains.personality.content_db import lookup
from domains.personality.service import analyze_aptitude, analyze_character

_BIRTHS = (
    (1990, 2, 6, 14, 0, "female"),
    (1990, 5, 15, 10, 0, "male"),
    (1983, 5, 14, 14, 0, "female"),
)
_AGE_GUIDE = (
    "활동 무대가 차례로",
    "용돈과 살림의 감각을 익히고",
    "22세 전후를 기점으로",
)


def test_lifelong_core_uses_the_stored_character_essay():
    for birth in _BIRTHS:
        life, is_fallback = analyze_lifelong_fortune(*birth, False)
        character, _ = analyze_character(*birth, False)
        assert is_fallback is False
        stored = lookup(character["saju_info"]["day_ganji"], "character")
        core = life["data"]["core_nature"]
        assert core["personality"] == stored["base_nature"]
        assert core["weaknesses"] == stored["weaknesses"]
        assert core["life_theme"]
        assert list(core.keys()) == ["personality", "life_theme", "weaknesses", "tip"]
        for phrase in _AGE_GUIDE:
            assert phrase not in core["personality"]
            assert phrase not in core["weaknesses"]
        assert set(life["data"]["life_domains"]) >= {"wealth", "career", "family", "social"}
        for period in ("early_life", "middle_life", "late_life"):
            assert life["data"][period]
        assert len(life["data"]["life_stages"]) == 8


def test_character_report_keeps_the_longer_behavior_text():
    data, is_fallback = analyze_character(1990, 2, 6, 14, 0, "female", False)
    assert is_fallback is False
    stored = lookup(data["saju_info"]["day_ganji"], "character")
    report = data["report"]
    assert set(report) == {
        "base_nature", "strengths", "weaknesses", "supplement", "relationships", "work_style",
    }
    assert stored["base_nature"][:20] in report["base_nature"]
    assert len(report["base_nature"]) > len(stored["base_nature"])
    assert "전체가 어떤 구조인지" in report["base_nature"]
    aptitude, _ = analyze_aptitude(1990, 2, 6, 14, 0, "female", False)
    assert "전체가 어떤 구조인지" not in aptitude["report"]["fit_task"]


def test_character_lookup_cache_is_not_rewritten():
    data, _ = analyze_character(1990, 2, 6, 14, 0, "female", False)
    ilju = data["saju_info"]["day_ganji"]
    before = lookup(ilju, "character")["base_nature"]
    analyze_character(1990, 2, 6, 14, 0, "female", False)
    assert lookup(ilju, "character")["base_nature"] == before


def test_missing_character_row_uses_the_original_fallback(monkeypatch):
    import domains.lifelong.service as svc

    monkeypatch.setattr(svc, "lookup_personality", lambda ilju, group: None)
    data, is_fallback = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    assert is_fallback is True
    core = data["data"]["core_nature"]
    assert core["personality"] == "안정적인 흐름 속에서 자기 페이스를 지키는 성향입니다."
    assert core["weaknesses"] == "한번 자리 잡은 방식을 바꾸는 데 시간이 걸려 변화의 타이밍을 놓치기 쉽습니다."
