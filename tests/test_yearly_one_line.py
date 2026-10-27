"""반복된 열정 표현만 바꾸고, 저장된 한줄평의 나머지와 본문은 유지한다."""
from domains.yearly import content_db
from domains.yearly.one_line_voice import rewrite_repeated_phrase, vary_repeated_phrase
from domains.yearly.service import _yearly_static, _yearly_study_static, _yearly_v2_static
from shared.text_format import paragraphize

_CATS = (
    "overall", "health", "study", "career_change", "business",
    "wealth", "love", "travel", "hobby",
)


def _group(line: str) -> dict:
    return {category: line for category in _CATS}


def test_a_shared_heat_phrase_changes_only_in_the_other_categories():
    stored = "뜨거운 열정과 경쟁심으로 빛나는 성과를 거둬요."
    group = _group("뜨거운 열정이 있는 해")
    assert rewrite_repeated_phrase("overall", "뜨거운 열정이 가득한 해", group) == "뜨거운 열정이 가득한 해"
    assert rewrite_repeated_phrase("career_change", stored, group) == (
        "추진력이 살아나는 흐름과 경쟁심으로 빛나는 성과를 거둬요."
    )
    health = "뜨거운 열정과 함께 폭발적인 에너지를 발휘하며 활기차게 달리는 건강한 한 해입니다."
    rewritten = rewrite_repeated_phrase("health", health, group)
    assert rewritten.startswith("활력이 넘치는 기운과 함께")
    assert "건강한 한 해" in rewritten
    assert "폭발" not in rewritten
    assert "뜨거운" not in rewritten


def test_two_categories_do_not_count_as_repetition():
    group = {
        "overall": "뜨거운 열정이 가득한 해",
        "health": "뜨거운 열정과 함께 달리는 해",
        "love": "평온하게 깊어지는 사랑",
    }
    assert rewrite_repeated_phrase("health", group["health"], group) == group["health"]


def test_service_keeps_the_essay_and_only_varies_the_repeated_line():
    saju = {"day_ganji": "丁巳", "day_master": "丁", "birth_time_known": True, "age": 35}
    health, health_fb = _yearly_v2_static("health", 2026, saju, [], [], [])
    career, career_fb = _yearly_v2_static("career_change", 2026, saju, [], [], [])
    love, love_fb = _yearly_v2_static("love", 2026, saju, [], [], [])
    study, study_fb = _yearly_study_static(2026, saju, [], [], [])
    overall, overall_fb = _yearly_static("overall", 2026, saju, [], [], [])
    assert not any((health_fb, career_fb, love_fb, study_fb, overall_fb))

    stored_health = content_db.lookup("health", "丁巳", "丙午", required=("one_line",))
    stored_overall = content_db.lookup("overall", "丁巳", "丙午", required=("one_line",))
    stored_study = content_db.lookup(
        "study", "丁巳", "丙午", required=("one_line",), key="丁巳_丙午_s30_plus",
    )
    assert "뜨거운" in stored_health["one_line"]
    assert overall["one_line"] == stored_overall["one_line"]
    assert health["one_line"] == vary_repeated_phrase("health", "丁巳", "丙午", stored_health["one_line"])
    assert "활력이 넘치는 기운" in health["one_line"]
    assert "건강한 한 해" in health["one_line"]
    assert "경쟁심" in career["one_line"] and "추진력" in career["one_line"]
    assert "사랑" in love["one_line"] and "마음이 살아나는 흐름" in love["one_line"]
    assert "전문 지식" in study["one_line"] and "열정" not in study["one_line"]
    assert health["overall_flow"] == paragraphize(stored_health["overall_flow"])
    lines = [
        overall["one_line"], health["one_line"], career["one_line"],
        love["one_line"], study["one_line"],
    ]
    assert len(set(lines)) == len(lines)
    assert sum("뜨거운 열정" in line for line in lines) == 1
