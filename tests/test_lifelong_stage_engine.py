"""평생운세(대운 순번 축) 검증 — 결정적 계산 로직 + 조회 기반 서비스, 실제 Gemini 호출 없음."""
import pytest

from core.daewoon import daewoon_step_facts
from domains.lifelong.service import DOMINANT_GROUPS, STAGE_LABELS, _current_step, hint_for_step
from scripts.generate_content_db import _strip_lifelong_jargon as _strip_jargon


# ------------------------------------------------------------------ daewoon_step_facts (core/daewoon.py)
def test_daewoon_step_facts_returns_8_steps_with_all_fields():
    facts = daewoon_step_facts("庚", "辰", "辛巳", True, count=8)
    assert len(facts) == 8
    assert [f["step"] for f in facts] == list(range(1, 9))
    for f in facts:
        assert f["ganji"] and len(f["ganji"]) == 2
        assert f["sipsin"]
        assert f["sipsin_group"] in DOMINANT_GROUPS
        assert f["branch_relation"]


def test_daewoon_step_facts_direction_changes_sequence():
    fwd = daewoon_step_facts("庚", "辰", "辛巳", True, count=8)
    bwd = daewoon_step_facts("庚", "辰", "辛巳", False, count=8)
    assert [f["ganji"] for f in fwd] != [f["ganji"] for f in bwd]


# ------------------------------------------------------------------ 대운 순번 ↔ 인생국면 라벨
def test_stage_labels_cover_all_8_steps():
    assert set(STAGE_LABELS.keys()) == set(range(1, 9))
    assert STAGE_LABELS[1] == "학업과 가정·교우관계"
    assert STAGE_LABELS[7] == STAGE_LABELS[8] == "역할 전환과 정리"


def test_hint_for_step_returns_nonempty_for_every_group_and_step():
    for group in DOMINANT_GROUPS:
        for step in range(1, 9):
            assert hint_for_step(group, step), f"{group}/step{step} missing hint"


# ------------------------------------------------------------------ 현재 몇 번째 대운인지 계산
def test_current_step_before_first_daewoon_defaults_to_1():
    assert _current_step(daewoon_num=5, age=2) == 1


def test_current_step_exact_boundaries():
    # daewoon_num=5 -> 1번째 [5,14], 2번째 [15,24], ...
    assert _current_step(daewoon_num=5, age=5) == 1
    assert _current_step(daewoon_num=5, age=14) == 1
    assert _current_step(daewoon_num=5, age=15) == 2
    assert _current_step(daewoon_num=5, age=36) == 4
    assert _current_step(daewoon_num=5, age=44) == 4
    assert _current_step(daewoon_num=5, age=45) == 5


def test_current_step_clamped_to_8_for_very_old_age():
    assert _current_step(daewoon_num=10, age=200) == 8


# ------------------------------------------------------------------ 사주 용어 노출 가드레일
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
    ("충형 관계가 없어 방해 요소 없이 계획했던 목표를 밀어붙일 수 있습니다.", "충형"),
]


@pytest.mark.parametrize("text,leaked_term", JARGON_LEAK_SAMPLES)
def test_strip_jargon_removes_observed_leaks(text, leaked_term):
    cleaned = _strip_jargon(text)
    assert leaked_term not in cleaned
    assert len(cleaned) > len(text) - 20  # 문맥은 보존
    assert "니다" in cleaned or "요" in cleaned


def test_strip_jargon_leaves_clean_text_untouched():
    clean = "차분하게 자기 페이스를 지키며 신뢰를 쌓아가는 시기예요."
    assert _strip_jargon(clean) == clean


def test_strip_jargon_does_not_touch_plain_korean_words():
    text = "재물 중심의 삶을 살아가는 시기예요."
    assert "재물" in _strip_jargon(text)


# ------------------------------------------------------------------ 배치 생성 콤보 키 열거
from scripts.generate_content_db import (  # noqa: E402
    _lifelong_base_keys,
    _lifelong_domains_keys,
    _lifelong_stage_keys,
    coerce_lifelong_base,
    coerce_lifelong_domains,
    coerce_lifelong_stage,
    lifelong_base_valid,
    lifelong_domains_valid,
    lifelong_stage_valid,
)


def test_lifelong_base_keys_are_exactly_60_ilju():
    keys = _lifelong_base_keys(only=None)
    assert len(keys) == 60
    assert len({k for k, _ in keys}) == 60
    for k, ilju in keys:
        assert k == ilju
        assert len(ilju) == 2


def test_lifelong_domains_keys_total_is_2400():
    keys = _lifelong_domains_keys(only=None)
    assert len(keys) == 60 * len(DOMINANT_GROUPS) * 8
    assert len(keys) == 2400
    assert len({k for k, *_ in keys}) == 2400


def test_lifelong_domains_keys_only_filter():
    all_keys = _lifelong_domains_keys(only=None)
    target = all_keys[99][0]
    filtered = _lifelong_domains_keys(only=target)
    assert len(filtered) == 1
    assert filtered[0][0] == target


def test_lifelong_stage_keys_total_is_14000():
    keys = _lifelong_stage_keys(only=None)
    assert len(keys) == 14000
    assert len({k for k, *_ in keys}) == 14000


def test_lifelong_stage_keys_only_filter():
    all_keys = _lifelong_stage_keys(only=None)
    target = all_keys[321][0]
    filtered = _lifelong_stage_keys(only=target)
    assert len(filtered) == 1
    assert filtered[0][0] == target


# ------------------------------------------------------------------ 검증/정제 함수
def test_lifelong_base_valid_accepts_life_theme_only():
    assert lifelong_base_valid({"life_theme": "반복되는 인생 과제"}) is True


def test_lifelong_base_valid_rejects_empty_or_missing():
    assert lifelong_base_valid({"life_theme": ""}) is False
    assert lifelong_base_valid({}) is False
    assert lifelong_base_valid("not a dict") is False


def test_coerce_lifelong_base_strips_jargon_in_life_theme():
    out = coerce_lifelong_base({"life_theme": "재성 중심의 성향을 오가는 삶입니다."})
    assert "재성" not in out["life_theme"]


_DOMAINS_COMPLETE = {
    "wealth": {"style": "s", "management_tip": "t"},
    "career": {"best_fit_work": "w", "success_environment": "e"},
    "family": {"relation_characteristics": "r", "harmony_key": "h"},
    "social": {"connection_style": "c", "network_strategy": "n"},
}


def test_lifelong_domains_valid_accepts_correct_field_names():
    assert lifelong_domains_valid(dict(_DOMAINS_COMPLETE)) is True


def test_lifelong_domains_valid_rejects_mixed_up_field_names():
    """실측: lite 모델이 career 에 wealth 의 필드명(style/management_tip)을 섞어 쓰는 경우가
    10건 중 4건 나왔음 — 엄격 검증으로 걸러져야 한다."""
    bad = dict(_DOMAINS_COMPLETE)
    bad["career"] = {"style": "s", "management_tip": "t"}  # wealth 필드명 오염
    assert lifelong_domains_valid(bad) is False


def test_lifelong_domains_valid_rejects_missing_domain():
    bad = {k: v for k, v in _DOMAINS_COMPLETE.items() if k != "social"}
    assert lifelong_domains_valid(bad) is False


def test_coerce_lifelong_domains_strips_jargon_across_all_domains():
    entry = {
        "wealth": {"style": "재성 중심의 스타일이에요.", "management_tip": "팁"},
        "career": {"best_fit_work": "w", "success_environment": "e"},
        "family": {"relation_characteristics": "r", "harmony_key": "h"},
        "social": {"connection_style": "c", "network_strategy": "n"},
    }
    out = coerce_lifelong_domains(entry)
    assert "재성" not in out["wealth"]["style"]


_STAGE_COMPLETE = {
    "theme_line": "a", "event_narrative": "b", "previous_diff": "c", "next_hint": "d",
}


def test_lifelong_stage_valid_requires_all_four_fields():
    assert lifelong_stage_valid(dict(_STAGE_COMPLETE)) is True
    missing = dict(_STAGE_COMPLETE)
    missing["next_hint"] = ""
    assert lifelong_stage_valid(missing) is False
    assert lifelong_stage_valid("not a dict") is False


def test_coerce_lifelong_stage_strips_jargon_in_place():
    entry = {
        "theme_line": "관성 중심의 시기",
        "event_narrative": "괜찮아요.",
        "previous_diff": "인성 중심의 평온한 흐름으로 전환됩니다.",
        "next_hint": "괜찮아요.",
    }
    out = coerce_lifelong_stage(entry)
    assert "관성" not in out["theme_line"]
    assert "인성" not in out["previous_diff"]


# ------------------------------------------------------------------ 조회 기반 서비스(라이브 API 호출 없음)
from domains.lifelong.service import analyze_lifelong_fortune  # noqa: E402


def test_analyze_lifelong_fortune_returns_all_8_stages_with_current_flag(monkeypatch):
    import domains.lifelong.service as svc

    fake_stage = dict(_STAGE_COMPLETE)
    monkeypatch.setattr(svc, "lookup_base", lambda ilju: {"life_theme": "테스트 주제"})
    monkeypatch.setattr(svc, "lookup_personality", lambda ilju, group: {"base_nature": "테스트 성격"})
    monkeypatch.setattr(svc, "lookup_stage", lambda ilju, dom, rel, step: fake_stage)
    monkeypatch.setattr(svc, "lookup_domains", lambda ilju, dom, step: dict(_DOMAINS_COMPLETE))

    data, is_fallback = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    assert is_fallback is False
    assert data["data"]["core_nature"]["personality"] == "테스트 성격"
    assert data["data"]["core_nature"]["life_theme"] == "테스트 주제"

    stages = data["data"]["life_stages"]
    assert len(stages) == 8
    assert [s["step"] for s in stages] == list(range(1, 9))
    assert sum(1 for s in stages if s["is_current"]) == 1
    assert data["data"]["current_step"] == next(s["step"] for s in stages if s["is_current"])
    for s in stages:
        assert s["theme_line"] == "a"
        assert s["age_range"][1] == s["age_range"][0] + 9

    assert data["data"]["life_domains"] == _DOMAINS_COMPLETE


def test_analyze_lifelong_fortune_falls_back_when_lookup_misses(monkeypatch):
    import domains.lifelong.service as svc

    monkeypatch.setattr(svc, "lookup_base", lambda ilju: None)
    monkeypatch.setattr(svc, "lookup_personality", lambda ilju, group: None)
    monkeypatch.setattr(svc, "lookup_stage", lambda ilju, dom, rel, step: None)
    monkeypatch.setattr(svc, "lookup_domains", lambda ilju, dom, step: None)

    data, is_fallback = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    assert is_fallback is True
    stages = data["data"]["life_stages"]
    assert len(stages) == 8
    for s in stages:
        assert s["theme_line"] and s["event_narrative"] and s["previous_diff"] and s["next_hint"]
    assert data["data"]["core_nature"]["personality"]
    assert data["data"]["core_nature"]["life_theme"]
    assert data["data"]["life_domains"]
