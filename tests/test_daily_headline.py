"""오늘의 운세 한줄평(headline) — HEADLINE_TABLE 기반 합성 검증.

headline은 순수하게 "오늘 하루 한 줄 요약"만 한다: 항상 정확히 한 문장(마침표 1개),
신살 경고는 절대 안 붙는다(그건 today_energy 몫 — test_woon_modifier.py 참고).
예전에는 static DB 원문을 쓰다가 |score_delta|가 크면 "오늘의 핵심 기운: {라벨}"로
라벨을 그대로 복붙했다(headline·woon_today·social 3중 반복 문제). 지금은 항상
woon_modifier.HEADLINE_TABLE에서 (오늘 일진의 개별 십신, trigger_bucket) 조합의
자연스러운 한 문장을 그대로 쓴다 — static DB의 headline 필드는 더 이상 화면에 쓰이지
않는다.

HEADLINE_TABLE의 키가 십신군(5종, WOON_STATE_TABLE과 동일)이 아니라 개별 십신(10종)인
이유: 일진 천간은 10일 주기로 매일 +1칸씩 도는데, 십신군은 그중 이웃한 두 칸(비견↔겁재,
식신↔상관, 편재↔정재, 편관↔정관, 편인↔정인)이 항상 같은 그룹으로 묶인다. 그룹(5종)
기준으로 조회하면 이틀에 한 번꼴로 어제와 같은 셀을 다시 조회해 한줄평이 그대로
반복되는 버그가 있었다(사용자 리포트). 개별 십신(10종)으로 쪼개면 이 이웃 쌍의 음양이
매일 갈라져 어제와 정확히 같은 키가 다시 나오는 경우가 구조적으로 없다.
"""
import pytest

from core.sipsin import sipsin_group
from domains.daily.woon_modifier import (
    HEADLINE_TABLE,
    WOON_STATE_TABLE,
    _DEFAULT_HEADLINE,
    _resolve_headline,
)
from domains.daily.service import _shape

_SIPSIN10 = {"비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인"}


def test_headline_table_covers_every_sipsin_bucket_cell():
    buckets = {"harmony", "conflict", "adjustment", "friction", "repeat", "neutral"}
    assert set(HEADLINE_TABLE.keys()) == _SIPSIN10
    for sipsin in _SIPSIN10:
        assert set(HEADLINE_TABLE[sipsin].keys()) == buckets
        for b in buckets:
            assert isinstance(HEADLINE_TABLE[sipsin][b], str) and HEADLINE_TABLE[sipsin][b]


def test_headline_table_text_differs_from_state_table_comment():
    # headline·comment·social이 같은 신호를 각자 다른 단어로 말해야 한다(복붙 금지).
    for sipsin in HEADLINE_TABLE:
        group = sipsin_group(sipsin)
        for b in HEADLINE_TABLE[sipsin]:
            assert HEADLINE_TABLE[sipsin][b] != WOON_STATE_TABLE[group][b]["comment"]
            assert HEADLINE_TABLE[sipsin][b] != WOON_STATE_TABLE[group][b]["label"]


def test_headline_table_sipsin_pair_within_group_has_distinct_text():
    # 같은 십신군(예: 비겁)에 속한 두 십신(비견/겁재)도 같은 버킷에서 서로 다른 문장을
    # 써야 한다 — 그래야 이웃한 두 날(같은 그룹, 다른 음양)이 겹치지 않는다.
    pairs = [
        ("비견", "겁재"), ("식신", "상관"), ("편재", "정재"), ("편관", "정관"), ("편인", "정인"),
    ]
    for a, b in pairs:
        for bucket in HEADLINE_TABLE[a]:
            assert HEADLINE_TABLE[a][bucket] != HEADLINE_TABLE[b][bucket]


@pytest.mark.parametrize(
    "sipsin,bucket",
    [(g, b) for g in HEADLINE_TABLE for b in HEADLINE_TABLE[g]] + [(None, None)],
)
def test_headline_table_entries_are_exactly_one_sentence(sipsin, bucket):
    text = HEADLINE_TABLE.get(sipsin or "", {}).get(bucket or "") or _DEFAULT_HEADLINE
    assert text.count(".") == 1 and text.endswith(".")


def test_resolve_headline_picks_sipsin_bucket_sentence():
    assert _resolve_headline("편재", "conflict") == HEADLINE_TABLE["편재"]["conflict"]
    assert _resolve_headline("정관", "harmony") == HEADLINE_TABLE["정관"]["harmony"]


def test_resolve_headline_falls_back_when_no_trigger():
    assert _resolve_headline(None, None) == _DEFAULT_HEADLINE


def test_resolve_headline_never_appends_sinsal():
    # headline은 신살을 받는 파라미터 자체가 없다 — 시그니처로 강제.
    # (sipsin, bucket, day_ordinal) 3개뿐 — day_ordinal은 풀 로테이션 시드일 뿐 신살과 무관.
    import inspect

    params = inspect.signature(_resolve_headline).parameters
    assert "sinsal_hits" not in params and len(params) == 3


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
    assert _resolve_headline(group, bucket) == HEADLINE_TABLE[group][bucket]
