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


def _sentences(text: str):
    return [
        re.sub(r"\s+", "", piece)
        for piece in re.findall(r"[^.!?…]+[.!?…]", text)
        if len(re.sub(r"\s+", "", piece)) >= 12
    ]


def test_couple_sections_each_hold_one_point():
    """구획을 이어 붙이지 않는다. 끌림 칸에 조언이나 마음 단정이 붙지 않는다."""
    # 일간은 木으로 고정하고, 상대 천간으로 역할만 바꾼다.
    yang = {"비겁": "甲", "식상": "丙", "재성": "戊", "관성": "庚", "인성": "壬"}
    yin = {"비겁": "乙", "식상": "丁", "재성": "己", "관성": "辛", "인성": "癸"}
    shapes = (
        ("hap", "子", "丑", "mix"),
        ("mixed", "寅", "亥", "mix"),
        ("chung", "子", "午", "yang"),
        ("hyung", "子", "卯", "mix"),
        ("hae", "子", "未", "mix"),
        ("self", "午", "午", "yang"),
        ("same", "丑", "丑", "yin"),
        ("pa", "子", "酉", "mix"),
        ("open", "子", "寅", "yang"),
    )
    for role in yang:
        headlines = []
        for kind, mine_b, their_b, polarity in shapes:
            if polarity == "yang":
                me, them = "甲", yang[role]
            elif polarity == "yin":
                me, them = "乙", yin[role]
            else:
                me, them = "甲", yin[role]
            brief = build_crush_brief(me + mine_b, them + their_b)
            texts = [brief["headline"], *(section["text"] for section in brief["sections"])]
            blob = "\n".join(texts)
            assert "마음이 있다는 뜻은 아니에요" not in blob
            attract = brief["sections"][0]["text"]
            assert "마세요" not in attract
            assert "해보세요" not in attract
            keys = []
            for text in texts:
                keys.extend(_sentences(text))
            assert len(keys) == len(set(keys)), (role, kind, keys)
            for banned in _BANNED:
                assert banned not in blob
            headlines.append(brief["headline"])
        assert len(headlines) == len(set(headlines)), role


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
