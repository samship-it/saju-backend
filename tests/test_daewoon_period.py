"""10년 대운(domains/daewoon) — 평생운세 '자세히 보기' 완전 이관분 검증."""
from domains.daewoon.challenge import build_challenge, CHALLENGE
from domains.daewoon.landscape import build_decade_landscape
from domains.daewoon.service import analyze_daewoon_period
from domains.lifelong.service import DOMINANT_GROUPS


def test_challenge_table_covers_all_five_groups():
    assert set(CHALLENGE.keys()) == set(DOMINANT_GROUPS)
    for text in CHALLENGE.values():
        assert isinstance(text, str) and text


def test_build_challenge_falls_back_for_unknown_group():
    assert build_challenge("존재안함")  # 폴백 문구로 대체(빈 문자열 아님)


def test_build_decade_landscape_combines_day_master_and_decade_ganji_elem():
    out = build_decade_landscape("수", "戊辰")  # 戊 -> 토
    from domains.lifelong.landscape import ENV_IMAGE, SUBJECT_IMAGE

    assert out["scene"] == f"{ENV_IMAGE['토']} 아래 {SUBJECT_IMAGE['수']}"
    assert out["decade_elem"] == "토"


def test_build_decade_landscape_handles_empty_ganji():
    out = build_decade_landscape("수", "")
    assert out["scene"]
    assert out["decade_elem"] is None


# ------------------------------------------------------------------ analyze_daewoon_period()
def test_analyze_daewoon_period_defaults_to_current_step_when_omitted():
    from domains.lifelong.service import analyze_lifelong_fortune

    lifelong_data, _ = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    expected_step = lifelong_data["data"]["current_step"]

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False)
    assert data["data"]["step"] == expected_step


def test_analyze_daewoon_period_honors_explicit_step():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=3)
    assert data["data"]["step"] == 3


def test_analyze_daewoon_period_clamps_out_of_range_step():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=99)
    assert data["data"]["step"] == 8
    data2, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=0)
    assert data2["data"]["step"] == 1


def test_analyze_daewoon_period_has_all_five_schema_fields_plus_meta():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=4)
    d = data["data"]
    assert set(d.keys()) == {
        "decade_landscape", "overall_summary", "turning_points", "domain_flows",
        "challenge", "step", "stage_label", "age_range", "ganji",
    }
    assert d["overall_summary"]
    assert d["challenge"]
    assert d["ganji"] and len(d["ganji"]) == 2


def test_analyze_daewoon_period_turning_points_has_three_labeled_stages():
    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=2)
    tp = data["data"]["turning_points"]
    assert len(tp) == 3
    labels = [t["label"] for t in tp]
    assert labels == ["이 시기의 시작", "이 시기를 관통하는 핵심 전략", "경계할 점"]
    for t in tp:
        assert t["text"]


def test_analyze_daewoon_period_domain_flows_matches_shape_domains_schema():
    from domains.lifelong.service import DOMAIN_FIELDS

    data, _ = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=5)
    flows = data["data"]["domain_flows"]
    assert set(flows.keys()) == set(DOMAIN_FIELDS.keys())
    for domain, fields in DOMAIN_FIELDS.items():
        assert set(flows[domain].keys()) == set(fields)


def test_analyze_daewoon_period_works_for_every_step_1_to_8():
    for step in range(1, 9):
        data, _ = analyze_daewoon_period(1983, 5, 14, 14, 0, "female", False, step=step)
        assert data["data"]["step"] == step
        assert data["data"]["overall_summary"]


def test_analyze_daewoon_period_content_type_and_response_shape():
    data, is_fallback = analyze_daewoon_period(1990, 5, 15, 10, 0, "male", False, step=1)
    assert data["content_type"] == "daewoon_period"
    assert isinstance(is_fallback, bool)
    assert data["saju_info"]
    assert data["day_master"]
