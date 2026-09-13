"""평생운세 생애단계 엔진(_build_stage_engine) 검증 — 결정적 계산 로직만, 실제 Gemini 호출 없음.

각 생애단계가 대운 흐름과 겹치는 햇수 기준으로 올바른 지배 간지/십신군을 고르는지,
순행/역행(성별)에 따라 대운 방향이 달라지는지, previous_diff 판단용 group_changed
플래그가 정확한지를 검증한다.
"""
import pytest

from core.saju_base import calculate_saju
from domains.lifelong.service import (
    _LIFE_STAGES,
    _build_stage_engine,
    _dominant_ganji,
    _pillar_segments,
    _strip_jargon,
)


def test_stage_keys_match_spec_exactly():
    saju = calculate_saju(1990, 5, 15, 10, 0, gender="male", is_lunar=False)
    stages = _build_stage_engine(saju)
    assert set(stages.keys()) == {
        "stage_1_19", "stage_20_29", "stage_30_49", "stage_50_69", "stage_70_plus",
    }
    assert [k for k, *_ in _LIFE_STAGES] == list(stages.keys())


def test_stage_name_labels_are_fixed_python_values_not_ai_generated():
    saju = calculate_saju(1990, 5, 15, 10, 0, gender="male", is_lunar=False)
    stages = _build_stage_engine(saju)
    assert stages["stage_1_19"]["stage_name"] == "1~19세 학업/가정/교우"
    assert stages["stage_20_29"]["stage_name"] == "20~29세 독립/방향설정"
    assert stages["stage_30_49"]["stage_name"] == "30~49세 커리어/재물/배우자"
    assert stages["stage_50_69"]["stage_name"] == "50~69세 축적/재정비"
    assert stages["stage_70_plus"]["stage_name"] == "70세+ 역할전환/정리"


def test_male_and_female_same_birthdate_get_opposite_daewoon_direction():
    """양간 연주(庚, 1990년)라면 남자=순행, 여자=역행이어야 한다."""
    male = calculate_saju(1990, 5, 15, 10, 0, gender="male", is_lunar=False)
    female = calculate_saju(1990, 5, 15, 10, 0, gender="female", is_lunar=False)
    assert male["daewoon"]["direction"] == "순행"
    assert female["daewoon"]["direction"] == "역행"
    # 방향이 다르므로 같은 생년월일이라도 대운 흐름(따라서 지배 간지)이 달라야 한다.
    m_stages = _build_stage_engine(male)
    f_stages = _build_stage_engine(female)
    assert m_stages["stage_30_49"]["dominant_ganji"] != f_stages["stage_30_49"]["dominant_ganji"]


def test_dominant_ganji_picks_largest_overlap():
    # 인위적 flow: [0,19] 구간에 5~15세(壬午, 10년)와 15~25세(癸未, 起 4년만 겹침)가 걸침.
    flow = [
        {"start_age": 5, "ganji": "壬午"},
        {"start_age": 15, "ganji": "癸未"},
        {"start_age": 25, "ganji": "甲申"},
    ]
    segs = _pillar_segments(month_ganji="辛巳", flow=flow, daewoon_num=5)
    # [0,5) 월주 5년 vs [5,15) 壬午 10년 vs [15,20) 중 [15,19] 癸未 4년 → 壬午 승리
    assert _dominant_ganji(segs, 0, 19) == "壬午"


def test_open_ended_70_plus_resolves_to_last_covering_pillar():
    saju = calculate_saju(1990, 5, 15, 10, 0, gender="male", is_lunar=False)
    stages = _build_stage_engine(saju)
    assert stages["stage_70_plus"]["dominant_ganji"] is not None
    assert stages["stage_70_plus"]["age_range"] == [70, None]


def test_group_changed_flag_tracks_previous_stage_transitions():
    saju = calculate_saju(1990, 5, 15, 10, 0, gender="male", is_lunar=False)
    stages = _build_stage_engine(saju)
    assert stages["stage_1_19"]["prev_sipsin_group"] is None
    assert stages["stage_1_19"]["group_changed"] is False
    for i, key in enumerate(list(stages.keys())[1:], start=1):
        prev_key = list(stages.keys())[i - 1]
        expected_changed = stages[key]["dominant_sipsin_group"] != stages[prev_key]["dominant_sipsin_group"]
        assert stages[key]["group_changed"] == expected_changed
        assert stages[key]["prev_sipsin_group"] == stages[prev_key]["dominant_sipsin_group"]


def test_every_stage_has_a_reference_hint():
    saju = calculate_saju(1985, 11, 20, 3, 0, gender="female", is_lunar=False)
    stages = _build_stage_engine(saju)
    for key, s in stages.items():
        assert s["hint"], f"{key} missing hint for group {s['dominant_sipsin_group']}"


# ------------------------------------------------------------------ 사주 용어 노출 가드레일
# 실측: AI 가 previous_diff 등에서 "관성 중심의 흐름으로", "인성 중심의 흐름" 처럼
# 원시 십신 용어를 그대로 출력하는 경우가 있었음 — 이를 걸러내는 안전망 검증.
JARGON_LEAK_SAMPLES = [
    (
        "나를 표현하고 성과를 내기 바빴던 이전의 식상 중심 흐름에서 벗어나, 이제는 그 성과를 철저한 "
        "돈과 자산으로 구체화하는 재물 중심의 흐름으로 완전히 전환됩니다.",
        "식상",
    ),
    (
        "철저히 개인의 자산과 실속을 챙기던 재물 중심의 삶에서, 이제는 조직과 대중 앞에서 명예와 지위를 "
        "드높이며 리더로 추대받는 관성 중심의 흐름으로 완전히 탈바꿈합니다.",
        "관성",
    ),
    (
        "조직을 이끌며 치열하게 명예를 다투던 리더의 자리에서 내려와, 모든 것을 품어 안고 정신적 원로로서 "
        "인정받는 인성 중심의 평온한 흐름으로 전환됩니다.",
        "인성",
    ),
]


@pytest.mark.parametrize("text,leaked_term", JARGON_LEAK_SAMPLES)
def test_strip_jargon_removes_observed_leaks(text, leaked_term):
    cleaned = _strip_jargon(text)
    assert leaked_term not in cleaned
    # 제거 후에도 문장이 텅 비거나 어색하게 끊기지 않아야 한다(주변 문맥은 보존).
    assert len(cleaned) > len(text) - 20
    assert "흐름" in cleaned


def test_strip_jargon_leaves_clean_text_untouched():
    clean = "차분하게 자기 페이스를 지키며 신뢰를 쌓아가는 시기예요."
    assert _strip_jargon(clean) == clean


def test_strip_jargon_does_not_touch_plain_korean_words():
    # "재물"은 사주 전문용어가 아니라 일상어이므로 지워지면 안 된다.
    text = "재물 중심의 삶을 살아가는 시기예요."
    assert "재물" in _strip_jargon(text)
