"""평생운세 생애단계 엔진(_build_stage_engine) 검증 — 결정적 계산 로직만, 실제 Gemini 호출 없음.

각 생애단계가 대운 흐름과 겹치는 햇수 기준으로 올바른 지배 간지/십신군을 고르는지,
순행/역행(성별)에 따라 대운 방향이 달라지는지, previous_diff 판단용 group_changed
플래그가 정확한지를 검증한다.
"""
import pytest

from core.saju_base import calculate_saju
from domains.lifelong.service import (
    _LIFE_STAGES,
    DOMINANT_GROUPS,
    _build_stage_engine,
    _dominant_ganji,
    _pillar_segments,
)
from scripts.generate_content_db import _strip_lifelong_jargon as _strip_jargon


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


# ------------------------------------------------------------------ 배치 생성 콤보 키 열거
from scripts.generate_content_db import (  # noqa: E402
    _lifelong_base_keys,
    _lifelong_stage_keys,
    coerce_lifelong_base,
    coerce_lifelong_stage,
    lifelong_base_valid,
    lifelong_stage_valid,
)


def test_lifelong_base_keys_are_exactly_60_ilju():
    keys = _lifelong_base_keys(only=None)
    assert len(keys) == 60
    assert len({k for k, _ in keys}) == 60  # 전부 유일
    for k, ilju in keys:
        assert k == ilju
        assert len(ilju) == 2


def test_lifelong_stage_keys_total_matches_combo_space():
    keys = _lifelong_stage_keys(only=None)
    # 60 일주 × [stage_1_19: 5(dominant)×1(prev=none) + 4개 단계: 5×5] = 60×(5+100) = 6300
    assert len(keys) == 60 * (len(DOMINANT_GROUPS) + 4 * len(DOMINANT_GROUPS) * len(DOMINANT_GROUPS))
    assert len(keys) == 6300
    assert len({k for k, *_ in keys}) == 6300  # 전부 유일


def test_lifelong_stage_keys_stage_1_19_has_no_previous():
    keys = _lifelong_stage_keys(only=None)
    stage1 = [t for t in keys if t[2] == "stage_1_19"]
    # 60개 일주 × dominant 5가지 (prev 없음 → 1가지만) = 300
    assert len(stage1) == 60 * len(DOMINANT_GROUPS)
    assert all(t[4] == "none" for t in stage1)


def test_lifelong_stage_keys_only_filter():
    all_keys = _lifelong_stage_keys(only=None)
    target = all_keys[123][0]
    filtered = _lifelong_stage_keys(only=target)
    assert len(filtered) == 1
    assert filtered[0][0] == target


# ------------------------------------------------------------------ 검증/정제 함수
# base 스키마는 life_theme 단독(성향 personality/life_domains 는 personality_db 재사용 및
# section3 로 이동해 base 테이블에서 제거됨 — domains/lifelong/service.py 모듈 docstring 참고).
def test_lifelong_base_valid_accepts_life_theme_only():
    assert lifelong_base_valid({"life_theme": "반복되는 인생 과제"}) is True


def test_lifelong_base_valid_rejects_empty_or_missing():
    assert lifelong_base_valid({"life_theme": ""}) is False
    assert lifelong_base_valid({}) is False
    assert lifelong_base_valid("not a dict") is False


def test_lifelong_stage_valid_requires_all_three_fields():
    assert lifelong_stage_valid({"description": "a", "daeun_influence": "b", "previous_diff": "c"}) is True
    assert lifelong_stage_valid({"description": "a", "daeun_influence": "b", "previous_diff": ""}) is False
    assert lifelong_stage_valid({"description": "a", "daeun_influence": "b"}) is False
    assert lifelong_stage_valid("not a dict") is False


def test_coerce_lifelong_stage_strips_jargon_in_place():
    entry = {
        "description": "관성 중심의 흐름으로 진행돼요.",
        "daeun_influence": "괜찮아요.",
        "previous_diff": "인성 중심의 평온한 흐름으로 전환됩니다.",
    }
    out = coerce_lifelong_stage(entry)
    assert "관성" not in out["description"]
    assert "인성" not in out["previous_diff"]


def test_coerce_lifelong_base_strips_jargon_in_life_theme():
    entry = {"life_theme": "재성 중심의 성향을 오가는 삶입니다."}
    out = coerce_lifelong_base(entry)
    assert "재성" not in out["life_theme"]


# ------------------------------------------------------------------ 조회 기반 서비스(라이브 API 호출 없음)
import domains.lifelong.content_db as content_db  # noqa: E402
from domains.lifelong.service import analyze_lifelong_fortune  # noqa: E402


def test_analyze_lifelong_fortune_uses_looked_up_content(monkeypatch):
    fake_base = {
        "core_nature": {"personality": "테스트 성격", "life_theme": "테스트 주제"},
        "life_domains": {
            "wealth": {"style": "w", "management_tip": "wt"},
            "career": {"best_fit_work": "c", "success_environment": "ce"},
            "family": {"relation_characteristics": "f", "harmony_key": "fh"},
            "social": {"connection_style": "s", "network_strategy": "sn"},
        },
    }
    fake_stage = {"description": "테스트 설명", "daeun_influence": "테스트 영향", "previous_diff": "테스트 변화"}

    monkeypatch.setattr(content_db, "lookup_base", lambda ilju: fake_base)
    monkeypatch.setattr(content_db, "lookup_stage", lambda ilju, stage, dom, prev: fake_stage)
    # analyze_lifelong_fortune 은 모듈 로드 시점에 lookup_base/lookup_stage 를 바인딩해 가져왔으므로 함께 패치.
    import domains.lifelong.service as svc
    monkeypatch.setattr(svc, "lookup_base", lambda ilju: fake_base)
    monkeypatch.setattr(svc, "lookup_stage", lambda ilju, stage, dom, prev: fake_stage)

    data, is_fallback = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    assert is_fallback is False
    assert data["data"]["core_nature"]["personality"] == "테스트 성격"
    assert set(data["data"]["life_stages"].keys()) == {
        "stage_1_19", "stage_20_29", "stage_30_49", "stage_50_69", "stage_70_plus",
    }
    for s in data["data"]["life_stages"].values():
        assert s["description"] == "테스트 설명"
        assert s["previous_diff"] == "테스트 변화"


def test_analyze_lifelong_fortune_falls_back_when_lookup_misses(monkeypatch):
    import domains.lifelong.service as svc
    monkeypatch.setattr(svc, "lookup_base", lambda ilju: None)
    monkeypatch.setattr(svc, "lookup_stage", lambda ilju, stage, dom, prev: None)

    data, is_fallback = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    assert is_fallback is True
    # 폴백이어도 스키마는 동일하게 완전해야 한다.
    assert set(data["data"]["life_stages"].keys()) == {
        "stage_1_19", "stage_20_29", "stage_30_49", "stage_50_69", "stage_70_plus",
    }
    for s in data["data"]["life_stages"].values():
        assert s["description"] and s["daeun_influence"] and s["previous_diff"]
