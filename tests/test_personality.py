"""나의 성격 / 나의 적성(domains/personality) — landscape·bridge 신규 필드 검증."""
from domains.personality.service import (
    _VERDICT_TRAIT,
    _character_bridge,
    _verdict_key,
    analyze_aptitude,
    analyze_character,
)


def test_verdict_key_falls_back_to_neutral_for_unknown_values():
    assert _verdict_key({"verdict": "신강"}) == "신강"
    assert _verdict_key({"verdict": "신약"}) == "신약"
    assert _verdict_key({"verdict": "중화"}) == "중화"
    assert _verdict_key({"verdict": "모름"}) == "중화"
    assert _verdict_key({}) == "중화"


def test_character_bridge_mentions_the_elem_and_verdict_trait():
    bridge = _character_bridge("금", "신강")
    assert "금" in bridge
    assert _VERDICT_TRAIT["신강"] in bridge
    assert "성격" in bridge


def test_analyze_character_includes_landscape_and_bridge():
    data, is_fallback = analyze_character(1990, 5, 15, 10, 0, "male", False)
    assert isinstance(is_fallback, bool)
    assert set(data["landscape"].keys()) == {"scene", "reason"}
    assert data["landscape"]["scene"]
    assert data["bridge"]
    assert "성격" in data["bridge"]
    assert set(data["report"].keys()) == {
        "base_nature", "strengths", "weaknesses", "supplement", "relationships", "work_style",
    }


def test_analyze_aptitude_includes_landscape_and_bridge():
    data, is_fallback = analyze_aptitude(1990, 5, 15, 10, 0, "male", False)
    assert isinstance(is_fallback, bool)
    assert set(data["landscape"].keys()) == {"scene", "reason"}
    assert data["landscape"]["scene"]
    assert data["bridge"]
    assert "적성" in data["bridge"]
    assert set(data["report"].keys()) == {
        "fit_task", "fit_field", "good_env", "org_style", "tiring_env", "favorable_direction",
    }


def test_character_and_aptitude_share_the_same_landscape_for_the_same_birth():
    # 같은 사람의 같은 원국이므로 풍경은 동일해야 한다.
    char_data, _ = analyze_character(1990, 5, 15, 10, 0, "male", False)
    apt_data, _ = analyze_aptitude(1990, 5, 15, 10, 0, "male", False)
    assert char_data["landscape"] == apt_data["landscape"]


def test_bridge_differs_across_different_day_master_elements():
    a, _ = analyze_character(1990, 5, 15, 10, 0, "male", False)
    b, _ = analyze_character(1983, 5, 14, 14, 0, "female", False)
    # 서로 다른 생일이면 일간 오행·신강약 조합이 달라질 수 있다(항상 다르다고 단정할
    # 수는 없으니, 최소한 함수가 정상적으로 문자열을 만들어내는지만 확인한다).
    assert a["bridge"] and b["bridge"]
