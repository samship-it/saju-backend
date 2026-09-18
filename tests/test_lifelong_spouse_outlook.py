"""평생운세 섹션7(가족) '배우자 관계/결혼운' — 배우자성 유무별 실시간 문구 조합 검증."""
from domains.lifelong.spouse_outlook import (
    ABSENT_TEXT,
    PRESENT_TEXT,
    _DEFAULT_TEXT,
    build_spouse_outlook,
)


def test_present_true_returns_present_table_text_by_group():
    for group in ("관성", "재성"):
        saju = {"spouse_star": {"spouse_star_group": group, "present": True}}
        out = build_spouse_outlook(saju)
        assert out["text"] == PRESENT_TEXT[group]
        assert out["spouse_star_present"] is True
        assert out["spouse_star_group"] == group


def test_present_false_returns_absent_table_text_by_group():
    for group in ("관성", "재성"):
        saju = {"spouse_star": {"spouse_star_group": group, "present": False}}
        out = build_spouse_outlook(saju)
        assert out["text"] == ABSENT_TEXT[group]
        assert out["spouse_star_present"] is False


def test_absent_text_avoids_deterministic_doom_framing():
    """'독신 가능성'을 단정("결혼 못 한다")이 아니라 가능성/선택지로 서술해야 한다
    (사용자 확인·승인된 톤 — 민감한 주제라 단정적 어투 금지)."""
    for text in ABSENT_TEXT.values():
        assert "못" not in text or "어렵다는 뜻은 아니" in text


def test_missing_spouse_star_falls_back_to_default_text():
    out = build_spouse_outlook({})
    assert out["text"]
    assert out["spouse_star_present"] is False


def test_unknown_group_falls_back_to_default_text():
    saju = {"spouse_star": {"spouse_star_group": "알수없음", "present": True}}
    out = build_spouse_outlook(saju)
    assert out["text"] == _DEFAULT_TEXT
