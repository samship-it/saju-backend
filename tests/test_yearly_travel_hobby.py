"""여행·취미 통합: 여섯 섹션 분배, 혼자/함께 모순 제거, 정적 조회."""
import inspect
import time

from fastapi.testclient import TestClient

import main
from domains.yearly.service import _cached_travel_hobby, generate_travel_hobby
from domains.yearly.travel_hobby import _COMPANY, _OPENING, assemble, read_axes

client = TestClient(main.app)

BANNED = (
    "십신", "용신", "희신", "기신", "신강", "신약", "역마", "식상",
    "원국", "세운", "오행", "배우자", "육합", "삼합",
)
FIELDS = (
    "symbol",
    "section_1_overall_flow",
    "section_2_travel_style",
    "section_3_recommended_spot",
    "section_4_matched_activity",
    "section_5_solo_vs_together",
    "section_6_final_reward",
)


def _travel():
    return {
        "one_line": "TLINE",
        "keywords": ["이동", "바람"],
        "concept_object": "지도",
        "overall_flow": "TFLOW",
        "travel_style": "TSTYLE",
        "travel_luck": "TLUCK",
        "recommended_spots": "TSPOT",
    }


def _hobby(solo="혼자 걷는 시간이 필요해요. 함께보다 혼자예요."):
    return {
        "one_line": "HLINE",
        "keywords": ["몰입"],
        "concept_object": "그림",
        "overall_flow": "HFLOW",
        "active_activities": "HACT",
        "solo_vs_group": solo,
        "benefits": "HGAIN",
    }


def test_rule_copy_has_no_technical_terms():
    from domains.yearly.travel_hobby import _STYLE_CLOSE

    blob = " ".join(_OPENING.values()) + " " + " ".join(_COMPANY.values()) + " " + " ".join(_STYLE_CLOSE.values())
    for term in BANNED:
        assert term not in blob


def test_fields_do_not_reuse_the_same_source_paragraph():
    moved = assemble(_travel(), _hobby(), move_high=True, play_high=False, company="solo", timing_months=["4월", "9월"])
    assert "TFLOW" in moved["section_1_overall_flow"]
    assert "HFLOW" not in moved["section_1_overall_flow"]
    assert "TSTYLE" in moved["section_2_travel_style"]
    assert "TSPOT" in moved["section_3_recommended_spot"]
    assert "TLUCK" not in moved["section_3_recommended_spot"]
    assert "4월" in moved["section_3_recommended_spot"]
    assert "HACT" in moved["section_4_matched_activity"]
    assert "HFLOW" not in moved["section_4_matched_activity"]
    assert "TLUCK" in moved["section_6_final_reward"]
    assert "HGAIN" in moved["section_6_final_reward"]
    assert moved["symbol"]["keywords"][0] == "#이동"
    assert moved["symbol"]["object"] == "지도"
    assert moved["symbol"]["headline"] == "TLINE"

    both = assemble(_travel(), _hobby(), move_high=True, play_high=True, company="either", timing_months=["5월"])
    assert "TFLOW" in both["section_1_overall_flow"]
    assert "HFLOW" not in both["section_1_overall_flow"]
    assert "HFLOW" not in both["section_4_matched_activity"]

    stayed = assemble(_travel(), _hobby(), move_high=False, play_high=True, company="together", timing_months=["6월"])
    assert "HFLOW" in stayed["section_1_overall_flow"]
    assert "TFLOW" not in stayed["section_1_overall_flow"]
    assert stayed["symbol"]["headline"] == "HLINE"
    assert "HGAIN" in stayed["section_6_final_reward"]
    assert "TLUCK" in stayed["section_6_final_reward"]


def test_hobby_company_keeps_alone_and_together_without_travel():
    data = assemble(
        _travel(),
        _hobby(
            "동행은 말수 적은 친구가 좋아요. "
            "혼자 정리하는 저녁이 집중에 맞아요. "
            "동호회에서 같이 보면 이야기가 늘어요. "
            "상황에 맞춰 그날의 방식을 고르면 돼요."
        ),
        move_high=True, play_high=False, company="solo", timing_months=["3월"],
    )
    text = data["section_5_solo_vs_together"]
    assert "동행" not in text
    assert text.index("혼자 정리") < text.index("동호회") < text.index("상황에")
    assert "여행" not in text


def test_axes_separate_movement_and_company():
    solo = read_axes({
        "day_branch": "子",
        "sinsal": {"has_yeokma": True},
        "derived": {"group_power": {"식상": 0, "비겁": 0}},
        "sewoon_sipsin": {"gan": "정재", "ji": "정인"},
    }, "甲午")
    assert solo["move_high"] is True
    assert solo["company"] == "solo"

    together = read_axes({
        "day_branch": "子",
        "sinsal": {"has_yeokma": False},
        "derived": {"group_power": {"식상": 0, "비겁": 2}},
        "sewoon_sipsin": {"gan": "비견", "ji": "정인"},
    }, "乙丑")
    assert together["move_high"] is False
    assert together["company"] == "together"


def test_combined_view_drops_seasonal_repeats_and_ungrounded_claims():
    travel = _travel()
    travel["overall_flow"] = "올해는 숨통이 트이는 흐름이에요. 초봄에는 제주 동쪽 바닷가로 떠나요. 한여름에는 해외로 나가요."
    travel["travel_style"] = "짧은 일정으로 혼자 걷는 편이 맞아요. 오픈카를 타고 익스트림을 즐겨요."
    travel["recommended_spots"] = "서쪽 방위로 가면 좋아요. 조용한 곳이 마음에 맞아요."
    travel["travel_luck"] = "일정 끝을 비워 두면 예상 못 한 사람을 만나요."
    hobby = _hobby("혼자 하는 시간이 필요해요.")
    hobby["overall_flow"] = "취미는 깊이를 보는 해예요. 가을에는 전시회를 열어요."
    hobby["active_activities"] = "크로스핏과 웨이트가 잘 맞아요. 펜으로 그림을 그리는 시간이 잘 맞아요."
    data = assemble(travel, hobby, move_high=True, play_high=True, company="solo", timing_months=["4월"])
    blob = " ".join(str(data[key]) for key in FIELDS if key != "symbol")
    for word in ("제주", "동쪽", "서쪽", "해외", "오픈카", "익스트림", "크로스핏", "웨이트", "초봄", "한여름", "가을"):
        assert word not in blob
    assert "숨통이 트이는 흐름" in data["section_1_overall_flow"]
    assert "취미는 깊이를" not in data["section_1_overall_flow"]
    assert "혼자 걷는" in data["section_2_travel_style"]
    assert "4월" in data["section_3_recommended_spot"]
    assert "조용한 곳" in data["section_3_recommended_spot"]
    assert "그림을 그리는" in data["section_4_matched_activity"]
    assert "얕아져요" in data["section_1_overall_flow"]
    assert "얕아져요" not in data["section_6_final_reward"]


def test_sections_keep_one_direction():
    travel = _travel()
    travel["one_line"] = "화려한 해외여행"
    travel["overall_flow"] = "극적인 여행 장면이 연출돼요. 익숙한 길에서 조금 벗어나면 충분해요. 대담한 해외여행과 강렬한 액티비티가 맞아요."
    travel["travel_style"] = "짧게 다녀오는 여행이 맞아요. 하루에 여러 곳을 촘촘하게 돌아요. 일정은 꽉 채워서 아침부터 밤까지 돌아요. 자연과 도시와 액티비티를 함께 즐겨요."
    travel["recommended_spots"] = "봄과 여름과 가을과 겨울이 모두 좋아요. 남쪽이나 동쪽으로 가세요."
    travel["travel_luck"] = "운명적인 만남이 찾아와요."
    hobby = _hobby("함께 클라이밍을 하면 좋아요. 그룹으로 운동해요.")
    hobby["active_activities"] = "크로스핏으로 기록을 단축해요. 클라이밍으로 완등해요. 새로운 종목을 많이 시작해요."
    hobby["benefits"] = "근력이 올라요. 타인의 주목을 받아요."
    calm = assemble(travel, hobby, move_high=False, play_high=True, company="either", timing_months=["4월", "6월", "7월"])
    assert "HFLOW" in calm["section_1_overall_flow"]
    assert "대담" not in calm["section_1_overall_flow"]
    assert "극적" not in calm["section_1_overall_flow"]
    assert "액티비티" not in calm["section_1_overall_flow"]
    assert "짧게" in calm["section_2_travel_style"]
    assert "비워" not in calm["section_2_travel_style"]
    assert "여러 곳" not in calm["section_2_travel_style"]
    assert "촘촘" not in calm["section_2_travel_style"]
    assert "꽉 채" not in calm["section_2_travel_style"]
    spot = calm["section_3_recommended_spot"]
    assert "4월" in spot and "6월" in spot and "7월" in spot
    assert "남쪽" not in spot and "동쪽" not in spot and "겨울" not in spot
    assert "크로스핏" not in calm["section_4_matched_activity"]
    assert "클라이밍" not in calm["section_4_matched_activity"]
    assert "하나에" in calm["section_4_matched_activity"]
    assert "함께 클라이밍" in calm["section_5_solo_vs_together"]
    assert "혼자만" not in calm["section_5_solo_vs_together"]
    reward = calm["section_6_final_reward"]
    assert "운명" not in reward and "주목" not in reward and "근력" not in reward
    assert "깊이" in calm["section_4_matched_activity"]
    assert "일정을 계속 늘리면" not in reward

    active_travel = _travel()
    active_travel["one_line"] = "화려한 해외여행"
    active_travel["overall_flow"] = "서두르지 않아도 돼요. 익숙한 길만 걸어요."
    active_travel["travel_style"] = "하루에 여러 곳을 돌아요."
    active_travel["travel_luck"] = "타인의 주목을 받아요."
    active_hobby = _hobby()
    active_hobby["benefits"] = "완등으로 기록이 줄어요."
    active_hobby["active_activities"] = "악기를 배우는 시간이 맞아요."
    active = assemble(active_travel, active_hobby, move_high=True, play_high=False, company="solo", timing_months=[])
    assert "서두르지" not in active["section_1_overall_flow"]
    assert "여러 곳" not in active["section_2_travel_style"]
    assert "월" not in active["section_3_recommended_spot"]
    assert "TSPOT" in active["section_3_recommended_spot"]
    assert "악기" in active["section_4_matched_activity"]
    assert "해외" not in active["symbol"]["headline"]
    assert "주목" not in active["section_6_final_reward"]
    assert "완등" not in active["section_6_final_reward"]


def test_style_definition_comes_before_lodging_and_company():
    travel = _travel()
    travel["travel_style"] = (
        "숙소는 조용한 한옥이 맞아요. "
        "동행은 말수가 적은 사람이 좋아요. "
        "올해 여행 스타일은 아늑한 휴양형이에요."
    )
    data = assemble(travel, _hobby(), move_high=False, play_high=False, company="either", timing_months=["8월"])
    text = data["section_2_travel_style"]
    assert text.index("휴양형") < text.index("한옥")
    assert text.index("휴양형") < text.index("동행")

    travel["travel_style"] = "숙소는 조용한 한옥이 맞아요. 가족이나 연인과 함께 조용히 떠납니다."
    led = assemble(travel, _hobby(), move_high=False, play_high=False, company="either", timing_months=["8월"])
    body = led["section_2_travel_style"]
    assert body.index("조용히") < body.index("한옥")


def test_distinct_stored_sentences_stay_and_paraphrases_drop():
    travel = _travel()
    travel["overall_flow"] = (
        "골목의 불빛 아래에서 발걸음이 느려져요. "
        "골목의 불빛 아래에서 발걸음이 느려집니다. "
        "바닷바람이 부는 언덕에서 숨을 고르는 시간이 필요해요."
    )
    travel["recommended_spots"] = "호수가 고요한 곳이 마음에 맞아요. 남쪽으로 떠나야 해요."
    hobby = _hobby("친구와 전시를 보는 시간이 좋아요. 혼자 정리하는 저녁도 필요해요.")
    hobby["active_activities"] = (
        "수채화로 하루의 색을 남기는 시간이 맞아요. "
        "수채화로 하루의 색을 남기는 시간이 잘 맞아요. "
        "어두운 방에서 필름을 현상하는 과정이 집중을 되찾아 줘요."
    )
    data = assemble(travel, hobby, move_high=False, play_high=False, company="either", timing_months=["3월"])
    flow = data["section_1_overall_flow"]
    assert flow.count("골목의 불빛") == 1
    assert "바닷바람" in flow
    assert "남쪽" not in data["section_3_recommended_spot"]
    assert "호수가 고요한" in data["section_3_recommended_spot"]
    assert "3월" in data["section_3_recommended_spot"]
    hobby_text = data["section_4_matched_activity"]
    assert hobby_text.count("수채화") == 1
    assert "필름" in hobby_text
    company = data["section_5_solo_vs_together"]
    assert "전시" in company and "혼자 정리" in company


def test_style_label_leads_and_harvest_splits_travel_from_hobby():
    travel = _travel()
    travel["travel_style"] = (
        "일정은 아침부터 밤까지 강행군이에요. "
        "동행은 즉흥적인 스케줄을 따라오는 에너지 넘치는 친구가 좋아요. "
        "나에게 어울리는 올해의 여행 스타일은 한계에 도전하는 액티브형과 열정적인 도시형의 조합이에요. "
        "이번 여행은 한계를 넘는 원정대 타임이에요."
    )
    travel["travel_luck"] = "낯선 사람에게 길을 배워요. 해낸 일의 성취감이 남아요. 열정적으로 부딪치면 문이 열려요."
    hobby = _hobby("혼자 정리하는 저녁이 집중에 맞아요. 동호회에서 같이 보면 이야기가 늘어요. 상황에 맞춰 방식을 고르면 돼요.")
    hobby["benefits"] = "거침없이 몰입한 끝에 자신감이 붙어요. 매 순간 모든 에너지를 쏟아붓는 대담함이 필요해요."
    data = assemble(travel, hobby, move_high=False, play_high=False, company="either", timing_months=["2월"])
    style = data["section_2_travel_style"]
    assert style.index("액티브형") < style.index("원정대") < style.index("동행")
    assert "강행군" not in style
    reward = data["section_6_final_reward"]
    assert reward.index("여행에서 얻는 수확") < reward.index("성취감")
    assert reward.index("취미에서 얻는 수확") < reward.index("자신감")
    assert "모든 에너지" not in reward
    assert "열정적으로" not in reward
    assert "회복" in data["section_1_overall_flow"]
    assert "회복" not in reward
    assert "억지로 판을 키우면" not in reward
    assert "경로가 바뀌는 즉흥" not in reward


def test_rest_and_impulse_closings_are_not_the_same_sentence():
    rest = _travel()
    rest["travel_style"] = "올해 여행 스타일은 아늑한 휴양형이에요. 숙소는 한옥이 맞아요."
    impulse = _travel()
    impulse["travel_style"] = "올해 여행 스타일은 즉흥적인 탐험형이에요. 숙소는 호스텔이 맞아요."
    rest_data = assemble(rest, _hobby(), move_high=False, play_high=False, company="either")
    impulse_data = assemble(impulse, _hobby(), move_high=True, play_high=False, company="either")
    assert "충분히 쉬는" in rest_data["section_2_travel_style"]
    assert "이동만 늘리" in impulse_data["section_2_travel_style"]
    assert "충분히 쉬는" not in rest_data["section_6_final_reward"]
    assert "이동만 늘리" not in impulse_data["section_6_final_reward"]
    assert "억지로 판을 키우면" not in rest_data["section_6_final_reward"]
    assert "일정을 계속 늘리면" not in impulse_data["section_6_final_reward"]


def _between(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    body = text.split(start, 1)[1]
    if end and end in body:
        body = body.split(end, 1)[0]
    return body


def test_section_meaning_keeps_only_fitting_sentences():
    """여행 조언·취미 조언·공통 마무리가 다른 섹션으로 넘어가지 않는다."""
    travel_plan = "일정을 계속 늘리면 다녀와도 남지 않아요. 한 번 움직인 뒤에는 쉬는 시간이 필요해요."
    hobby_skill = "매일 연습해서 그림 실력이 늘고 자신감이 붙어요."
    hobby_rest = "그림을 그리며 마음이 쉬어지고 감정을 표현하게 돼요."
    travel_meet = "일정 끝에 만난 사람 덕분에 골목이 새롭게 보여요."

    mixed = _travel()
    mixed["travel_luck"] = f"{travel_meet} {hobby_skill}"
    mixed_hobby = _hobby()
    mixed_hobby["benefits"] = f"{hobby_rest} {travel_plan} 작품을 마치며 표현이 분명해져요."
    mixed_hobby["active_activities"] = "HACT"
    data = assemble(mixed, mixed_hobby, move_high=True, play_high=False, company="either", timing_months=["4월"])
    reward = data["section_6_final_reward"]
    travel_part = _between(reward, "여행에서 얻는 수확", "취미에서 얻는 수확")
    hobby_part = _between(reward, "취미에서 얻는 수확", "")
    assert "골목" in travel_part
    assert "실력" not in travel_part
    assert "쉬어지고" in hobby_part
    assert "표현이 분명" in hobby_part
    assert "일정을 계속 늘리면" not in hobby_part
    assert "일정을 계속 늘리면" in data["section_2_travel_style"]
    assert "HACT" not in reward
    assert travel_plan not in data["section_4_matched_activity"]
    assert hobby_skill not in data["section_2_travel_style"]

    empty = _travel()
    empty["travel_luck"] = hobby_skill
    empty["travel_style"] = "TSTYLE"
    empty_hobby = _hobby()
    empty_hobby["benefits"] = travel_plan
    empty_hobby["active_activities"] = "붓으로 색을 쌓는 시간이 맞아요."
    bare = assemble(empty, empty_hobby, move_high=False, play_high=True, company="solo", timing_months=["3월"])
    bare_reward = bare["section_6_final_reward"]
    assert "실력" not in _between(bare_reward, "여행에서 얻는 수확", "취미에서 얻는 수확")
    assert "일정을 계속 늘리면" not in _between(bare_reward, "취미에서 얻는 수확", "")
    assert "붓으로" not in _between(bare_reward, "여행에서 얻는 수확", "취미에서 얻는 수확")
    assert "TSTYLE" not in _between(bare_reward, "취미에서 얻는 수확", "")


def test_real_years_do_not_put_travel_plans_in_hobby_harvest():
    from domains.yearly.service import generate_travel_hobby
    from domains.yearly.travel_hobby import _sentences, fits_section

    for year in (2026, 2027, 2028):
        for day in (6, 15):
            data, fallback = generate_travel_hobby(1990, 2 if day == 6 else 5, day, 14, 0, "female", target_year=year)
            assert fallback is False
            reward = data["section_6_final_reward"]
            for sentence in _sentences(_between(reward, "취미에서 얻는 수확", "")):
                assert fits_section("hobby_gain", sentence, "hobby_gain"), (year, day, sentence)
                assert "일정을 계속 늘리면" not in sentence
                assert "한 번 움직인 뒤" not in sentence
                assert "이동만 늘" not in sentence
            for sentence in _sentences(_between(reward, "여행에서 얻는 수확", "취미에서 얻는 수확")):
                assert fits_section("travel_gain", sentence, "travel_gain"), (year, day, sentence)
                assert not _skill_leak(sentence)


def _skill_leak(sentence: str) -> bool:
    from domains.yearly.travel_hobby import fits_section
    return not fits_section("travel_gain", sentence, "travel_gain")


def test_no_runtime_llm_on_the_module():
    import domains.yearly.travel_hobby as mod
    source = inspect.getsource(mod)
    assert "gemini" not in source.lower()
    assert "call_gemini" not in source


def test_endpoint_returns_six_sections_from_static_db():
    res = client.post(
        "/api/v1/yearly/travel-hobby",
        json={"year": 1990, "month": 5, "day": 15, "hour": 14, "minute": 30, "gender": "female", "target_year": 2026},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["is_fallback"] is False
    assert body["category"] == "travel_hobby"
    assert body["target_year"] == 2026
    for key in FIELDS:
        assert body[key]
    assert all(word.startswith("#") for word in body["symbol"]["keywords"])
    kept = client.post(
        "/api/v1/yearly/travel",
        json={"year": 1990, "month": 5, "day": 15, "hour": 14, "gender": "female", "target_year": 2026},
    )
    assert kept.status_code == 200
    assert kept.json()["category"] == "travel"
    assert "travel_style" in kept.json()


def test_p95_under_20ms_after_warmup():
    _cached_travel_hobby.cache_clear()
    args = dict(year=1992, month=11, day=3, hour=9, minute=0, gender="male", target_year=2026)
    first, fb = generate_travel_hobby(**args)
    assert fb is False
    assert first["section_1_overall_flow"]
    samples = []
    for _ in range(40):
        started = time.perf_counter()
        again, _ = generate_travel_hobby(**args)
        samples.append(time.perf_counter() - started)
        assert again["symbol"]["keywords"] == first["symbol"]["keywords"]
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 0.02, p95
