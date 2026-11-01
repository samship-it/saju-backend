"""짝사랑운 한줄평과 신규 구획. 저장된 종합운·매력·3개월은 바꾸지 않는다."""
import re

from fastapi.testclient import TestClient

import main
from domains.relationship.crush_brief import build_crush_brief
from shared.prose_quality import repeated_sentence_count, voice_flag
from shared.text_format import is_valid_headline

client = TestClient(main.app)

_BANNED = (
    "비겁", "식상", "재성", "관성", "인성", "신강", "신약", "용신", "십신",
    "우리는 왜", "고백을 받", "반드시 끌", "재회가 돼요", "그리워해요",
)


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?…]", text))


def _titles(brief):
    return [section["title"] for section in brief["sections"]]


def test_couple_and_solo_section_order():
    couple = build_crush_brief("甲子", "乙丑")
    solo = build_crush_brief("乙酉", None)
    assert _titles(couple) == [
        "상대가 나에게 끌릴 수 있는 지점",
        "관계가 가까워지는 데 유리한 점과 걸림돌",
        "먼저 다가갈 때 주의할 점",
    ]
    assert _titles(solo) == [
        "나의 연애 성향",
        "내가 호감을 표현하는 방식과 주의할 점",
    ]
    assert "strategy" not in couple
    assert "strategy" not in solo
    assert couple["frame"]["subtitle"] == ""
    assert _sentence_count(couple["headline"]) == 1
    assert _sentence_count(solo["headline"]) == 1
    assert is_valid_headline(couple["headline"])
    assert is_valid_headline(solo["headline"])
    assert "속도를 굽히" not in solo["headline"]
    assert "이별" not in solo["sections"][0]["text"]


def test_relations_change_the_reading_and_same_relation_stays():
    bond = build_crush_brief("甲子", "乙丑")
    same = build_crush_brief("甲午", "乙未")
    other = build_crush_brief("甲子", "己丑")
    clash = build_crush_brief("乙酉", "己卯")
    none = build_crush_brief("甲子", "丙寅")
    assert bond["headline"] == same["headline"]
    assert bond["sections"][0]["text"] == same["sections"][0]["text"]
    assert bond["headline"] != other["headline"]
    assert bond["sections"][0]["text"] != other["sections"][0]["text"]
    assert bond["headline"] != clash["headline"]
    assert "풀어 주는" in none["sections"][0]["text"]
    assert "시간" in clash["headline"] or "비용" in clash["headline"]
    for brief in (bond, other, clash, none, build_crush_brief("甲子", None)):
        blob = brief["headline"] + "\n" + "\n".join(section["text"] for section in brief["sections"])
        for banned in _BANNED:
            assert banned not in blob, banned
        for section in brief["sections"]:
            assert section["text"]
            assert repeated_sentence_count(section["text"]) == 0
            assert voice_flag(section["text"], "haeyo") == ""
        assert voice_flag(brief["headline"], "haeyo") == ""


def test_crush_api_keeps_stored_prose_and_adds_sections():
    couple = client.post(
        "/api/v1/relationship/crush",
        json={
            "person": {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"},
            "partner": {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"},
        },
    ).json()
    assert couple["status"] == "success"
    assert couple["is_fallback"] is False
    assert couple["content_type"] == "짝사랑운"
    assert couple["overall"]
    assert couple["your_charm"]
    assert len(couple["strategy_3months"]) == 3
    assert couple["headline"]
    titles = [section["title"] for section in couple["crush_sections"]]
    assert titles == [
        "상대가 나에게 끌릴 수 있는 지점",
        "관계가 가까워지는 데 유리한 점과 걸림돌",
        "먼저 다가갈 때 주의할 점",
    ]
    assert couple["overall"] not in [section["text"] for section in couple["crush_sections"]]
    assert "reunion_sections" not in couple
    solo = client.post(
        "/api/v1/relationship/crush",
        json={"person": {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}},
    ).json()
    assert solo["is_fallback"] is False
    assert "strategy_3months" not in solo
    assert [section["title"] for section in solo["crush_sections"]] == [
        "나의 연애 성향",
        "내가 호감을 표현하는 방식과 주의할 점",
    ]
    reunion = client.post(
        "/api/v1/relationship/reunion",
        json={"person": {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}},
    ).json()
    assert "crush_sections" not in reunion
    assert "crush_frame" not in reunion
