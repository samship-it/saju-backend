"""재회운 한줄평은 일간·일지 신호의 판단 초점이다. 점수 등급이 아니다."""
import re

from fastapi.testclient import TestClient

import main
from core.constants import GAN, JI
from domains.relationship.reunion_brief import build_reunion_brief
from shared.text_format import is_valid_headline
from shared.prose_quality import repeated_sentence_count, voice_flag

client = TestClient(main.app)

_BANNED = (
    "비겁", "식상", "재성", "관성", "인성", "신강", "신약", "용신", "십신",
    "그리워해요", "그리워한다", "후회하", "연락이 올", "연락할 거",
    "재회가 돼요", "재회에 성공", "새 연인", "새로운 인연", "새로운 사람",
)
_LABELS = ["2026년 11월", "2026년 12월", "2027년 1월"]


def _blob(brief) -> str:
    chunks = [brief["headline"], brief["frame"]["title"], brief["frame"]["subtitle"]]
    for section in brief["sections"]:
        chunks.extend([section["title"], section["text"]])
    strategy = brief["strategy"]
    chunks.extend([strategy["title"], strategy["intro"]])
    for month in strategy["months"]:
        chunks.extend(month.values())
    return "\n".join(chunks)


def _ganji_list():
    return [gan + ji for gan in GAN for ji in JI]


def test_solo_brief_stays_on_my_habit_and_has_no_score():
    brief = build_reunion_brief("甲子", None, _LABELS)
    assert "score" not in brief
    assert brief["frame"]["title"] == "나의 연애 성향"
    titles = [section["title"] for section in brief["sections"]]
    assert titles == [
        "나의 연애 성향과 과거 인연에 대한 태도",
        "먼저 연락할지 판단할 때 고려할 기준",
        "상대에게 어필할 나의 매력",
    ]
    assert brief["strategy"]["title"] == "앞으로 3개월 동안의 행동 전략"
    text = _blob(brief)
    assert "새 연인" not in text
    assert "새로운 인연" not in text
    assert "연락이 올" not in text
    assert "예측하지 않아요" in text


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[.!?]", text) if part.strip()])


def test_couple_focus_follows_day_branch_not_a_luck_grade():
    bond = build_reunion_brief("甲子", "乙丑", _LABELS)
    clash = build_reunion_brief("甲子", "甲午", _LABELS)
    mixed = build_reunion_brief("甲寅", "乙亥", _LABELS)
    none = build_reunion_brief("甲子", "丙寅", _LABELS)
    gap = build_reunion_brief("壬子", "甲寅", _LABELS)
    assert _sentence_count(bond["headline"]) == 1
    assert "붙" in bond["headline"]
    assert "부딪" not in bond["headline"]
    assert "부딪" in clash["headline"] or "주제" in clash["headline"]
    assert "가까워" in mixed["headline"] and "틀어" in mixed["headline"]
    assert "아물" not in mixed["headline"]
    assert "고정 신호" not in none["headline"]
    assert "막힌 말" in none["headline"]
    assert "서두르" not in _blob(none)
    assert "늦추" not in _blob(gap)
    assert "고정 신호" not in gap["headline"]
    assert "막힌 말" in gap["headline"]
    why, overall = none["sections"][0]["text"], none["sections"][1]["text"]
    assert "풀어 주는" in why
    assert "다툼의 장면" not in none["sections"][2]["text"]
    assert "유리한 날짜" not in none["sections"][3]["text"]
    assert "밖으로 꺼내는" not in overall
    charm = none["sections"][-1]["text"]
    assert "표현할 때" in charm
    assert "주의할 점" in charm
    assert "마음을 정하세요" not in charm
    assert bond["headline"] != clash["headline"]
    titles = [section["title"] for section in bond["sections"]]
    assert titles[0] == "우리는 왜"
    assert titles[2] == "갈등이 생기는 원인과 반복될 수 있는 패턴"
    assert "재회가 성사되는 기한이 아니에요" in bond["strategy"]["intro"]
    assert "붙는 관계" in bond["strategy"]["intro"]
    assert "고정 장면" in none["strategy"]["intro"]
    assert "이별 원인이었는지는 사주가 몰라요" in clash["sections"][2]["text"]


def test_new_sections_are_long_and_change_with_the_pair():
    bond = build_reunion_brief("甲子", "乙丑", _LABELS)
    clash = build_reunion_brief("乙酉", "己卯", _LABELS)
    solo_gap = build_reunion_brief("乙酉", None, _LABELS)
    solo_other = build_reunion_brief("甲子", None, _LABELS)
    for title in ("우리는 왜", "갈등이 생기는 원인과 반복될 수 있는 패턴", "재회를 고려할 때 유리한 점과 걸림돌"):
        text = next(section["text"] for section in clash["sections"] if section["title"] == title)
        assert _sentence_count(text) >= 4, title
    assert bond["sections"][0]["text"] != clash["sections"][0]["text"]
    attitude = solo_gap["sections"][0]["text"]
    contact = solo_gap["sections"][1]["text"]
    assert _sentence_count(attitude) >= 4
    assert _sentence_count(contact) >= 4
    assert attitude != solo_other["sections"][0]["text"]
    assert "보낼 수 있어요" in contact
    assert "속도를 굽히" not in solo_gap["headline"]
    assert "붙들" not in solo_gap["headline"]
    assert "식탁" not in clash["sections"][0]["text"]
    assert "식탁" not in clash["sections"][2]["text"]
    same = build_reunion_brief("甲午", "乙未", _LABELS)
    assert bond["sections"][0]["text"] == same["sections"][0]["text"]
    assert bond["headline"] == same["headline"]
    other_role = build_reunion_brief("甲子", "己丑", _LABELS)
    assert bond["sections"][0]["text"] != other_role["sections"][0]["text"]
    assert bond["headline"] != other_role["headline"]
    peer_clash = build_reunion_brief("甲子", "甲午", _LABELS)
    wealth_clash = build_reunion_brief("乙酉", "己卯", _LABELS)
    assert peer_clash["headline"] != wealth_clash["headline"]
    assert "양보" in peer_clash["headline"]
    assert "시간" in wealth_clash["headline"] or "비용" in wealth_clash["headline"]
    assert "답을 내가 미리" not in solo_gap["sections"][0]["text"]


def test_solo_and_couple_charm_are_not_the_same_sentence():
    solo = build_reunion_brief("甲子", None, _LABELS)
    couple = build_reunion_brief("甲子", "乙丑", _LABELS)
    solo_charm = solo["sections"][-1]["text"]
    couple_charm = couple["sections"][-1]["text"]
    assert solo_charm != couple_charm
    assert solo["headline"] != couple["headline"]
    assert "표현할 때" in couple_charm
    assert "그리워" not in couple_charm


def test_every_day_pillar_brief_is_speakable_and_unscored():
    pillars = _ganji_list()
    for self_ganji in pillars:
        solo = build_reunion_brief(self_ganji, None, _LABELS)
        assert is_valid_headline(solo["headline"]), solo["headline"]
        assert _sentence_count(solo["headline"]) == 1
        _assert_clean(solo)
    for self_ganji in pillars:
        for partner_ganji in pillars:
            brief = build_reunion_brief(self_ganji, partner_ganji, _LABELS)
            assert is_valid_headline(brief["headline"]), brief["headline"]
            assert _sentence_count(brief["headline"]) == 1, brief["headline"]
            _assert_clean(brief)


def _assert_clean(brief):
    text = _blob(brief)
    for banned in _BANNED:
        assert banned not in text, banned
    for section in brief["sections"]:
        assert repeated_sentence_count(section["text"]) == 0
        assert voice_flag(section["text"], "haeyo") == ""
    assert voice_flag(brief["headline"], "haeyo") == ""
    assert len(brief["strategy"]["months"]) == 3


def test_reunion_api_adds_headline_without_replacing_stored_overall():
    body = client.post(
        "/api/v1/relationship/reunion",
        json={
            "person": {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"},
            "partner": {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"},
        },
    ).json()
    assert body["status"] == "success"
    assert body["is_fallback"] is False
    assert body["overall"]
    assert body["your_charm"]
    assert len(body["strategy_3months"]) == 3
    assert body["headline"]
    assert body["reunion_sections"]
    assert "overall_score" not in body
    solo = client.post(
        "/api/v1/relationship/reunion",
        json={"person": {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}},
    ).json()
    assert solo["is_fallback"] is False
    assert "strategy_3months" not in solo
    assert solo["reunion_strategy"]["months"]
    crush = client.post(
        "/api/v1/relationship/crush",
        json={"person": {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}},
    ).json()
    assert "reunion_sections" not in crush
    assert "headline" not in crush
