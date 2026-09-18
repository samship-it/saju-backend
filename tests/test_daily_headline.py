"""오늘의 운세 한줄평(headline) — HEADLINE_TABLE 기반 합성 검증.

예전에는 static DB 원문을 쓰다가 |score_delta|가 크면 "오늘의 핵심 기운: {라벨}"로
라벨을 그대로 복붙했다(headline·woon_today·social 3중 반복 문제). 지금은 항상
woon_modifier.HEADLINE_TABLE에서 (trigger_group, trigger_bucket) 조합의 자연스러운
문장을 가져오고, 신살이 있으면 짧은 한 줄을 덧붙인다 — static DB의 headline 필드는
더 이상 화면에 쓰이지 않는다.
"""
import pytest

from domains.daily.woon_modifier import (
    HEADLINE_TABLE,
    WOON_STATE_TABLE,
    SINSAL_HEADLINE_SUFFIX,
    _DEFAULT_HEADLINE,
    _resolve_headline,
)
from domains.daily.service import _shape


def test_headline_table_covers_every_group_bucket_cell():
    groups = set(WOON_STATE_TABLE.keys())
    buckets = {"harmony", "conflict", "adjustment", "friction", "repeat", "neutral"}
    assert set(HEADLINE_TABLE.keys()) == groups
    for g in groups:
        assert set(HEADLINE_TABLE[g].keys()) == buckets
        for b in buckets:
            assert isinstance(HEADLINE_TABLE[g][b], str) and HEADLINE_TABLE[g][b]


def test_headline_table_text_differs_from_state_table_comment():
    # headline·comment·social이 같은 신호를 각자 다른 단어로 말해야 한다(복붙 금지).
    for g in WOON_STATE_TABLE:
        for b in WOON_STATE_TABLE[g]:
            assert HEADLINE_TABLE[g][b] != WOON_STATE_TABLE[g][b]["comment"]
            assert HEADLINE_TABLE[g][b] != WOON_STATE_TABLE[g][b]["label"]


def test_resolve_headline_picks_group_bucket_sentence():
    assert _resolve_headline("재성", "conflict", []) == HEADLINE_TABLE["재성"]["conflict"]
    assert _resolve_headline("관성", "harmony", []) == HEADLINE_TABLE["관성"]["harmony"]


def test_resolve_headline_falls_back_when_no_trigger():
    assert _resolve_headline(None, None, []) == _DEFAULT_HEADLINE


def test_resolve_headline_appends_worst_sinsal_only():
    hits = [
        {"layer": "ilwoon", "name": "백호", "penalty": -10},
        {"layer": "ilwoon", "name": "겁살", "penalty": -8},
    ]
    out = _resolve_headline("재성", "conflict", hits)
    assert out.startswith(HEADLINE_TABLE["재성"]["conflict"])
    assert SINSAL_HEADLINE_SUFFIX["백호"] in out  # 감점이 더 큰(-10) 백호만 붙는다
    assert SINSAL_HEADLINE_SUFFIX["겁살"] not in out


def test_resolve_headline_no_sinsal_no_suffix():
    out = _resolve_headline("인성", "harmony", [])
    assert out == HEADLINE_TABLE["인성"]["harmony"]


# ------------------------------------------------------------------ 파이프라인(service._shape) 통합
_SAJU_DATA = {"day_master": "壬", "day_branch": "寅", "today_ganji": {"day": "戊辰"}}


def _ai(overall_score=75):
    return {
        "overall_score": overall_score,
        "money_score": overall_score,
        "love_score": overall_score,
        "work_study_score": overall_score,
        "summary": {
            "overall": "본문", "money": "본문", "love_single": "본문",
            "love_couple": "본문", "work_study": "본문",
        },
        "keywords": ["a", "b", "c"],
        "recommended_action": "오늘 해볼 행동입니다.",
    }


def test_shape_headline_comes_straight_from_modifier():
    modifier = {"headline": "돈 씀씀이에 예민해지기 쉬운 날이니 큰 지출은 하루 미뤄보세요."}
    out = _shape(_ai(), _SAJU_DATA, modifier)
    assert out["headline"] == modifier["headline"]


def test_shape_no_longer_reads_static_db_headline():
    # static DB에 headline 필드가 와도 무시하고 modifier["headline"]만 쓴다.
    ai = _ai()
    ai["headline"] = "원본 static headline 문장입니다."
    modifier = {"headline": "합성된 새 한줄평입니다."}
    out = _shape(ai, _SAJU_DATA, modifier)
    assert out["headline"] == "합성된 새 한줄평입니다."


@pytest.mark.parametrize(
    "group,bucket",
    [(g, b) for g in HEADLINE_TABLE for b in HEADLINE_TABLE[g]],
)
def test_resolve_headline_matches_table_for_every_state(group, bucket):
    assert _resolve_headline(group, bucket, []) == HEADLINE_TABLE[group][bucket]
