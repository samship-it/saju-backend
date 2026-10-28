"""관계 유형은 기존 점수 필드를 고르고, 연애 이외 해석만 갈라진다."""
import pytest
from fastapi.testclient import TestClient

import main
from core.constants import compat_band

client = TestClient(main.app)

BIRTH_A = {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"}
BIRTH_B = {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}
ROMANCE_WORDS = ("애정", "도화", "배우자", "결혼", "연애", "천생연분", "사랑", "썸")


def _analyze(relation):
    response = client.post(
        "/api/v1/compatibility/analyze",
        json={"person1": BIRTH_A, "person2": BIRTH_B, "relation_type": relation},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _visible_text(body):
    report = body["report"]
    chunks = [body["relation_type_label"], body["one_liner"], *report.values()]
    return "\n".join(str(chunk) for chunk in chunks)


def test_romantic_headline_uses_existing_total():
    body = _analyze("romantic")
    scores = body["scores"]
    expected = compat_band(scores["total"])
    assert body["relation_type_label"] == expected["relation_type"]
    assert body["one_liner"] == expected["one_liner"]
    assert scores["overall"] == 96
    assert scores["love"] == 53
    assert scores["total"] == 72
    assert body["report"]["love"].strip()


def test_spouse_uses_the_same_romantic_path():
    romantic = _analyze("romantic")
    spouse = _analyze("spouse")
    assert spouse["one_liner"] == romantic["one_liner"]
    assert spouse["scores"] == romantic["scores"]
    assert spouse["report"]["love"].strip()


@pytest.mark.parametrize("relation", ["friend", "family", "business", "coworker"])
def test_other_relations_keep_overall_and_drop_romance_words(relation):
    body = _analyze(relation)
    assert body["relation_type_label"] == "성향 궁합"
    assert body["scores"]["overall"] == 96
    assert body["scores"]["total"] == 72
    assert body["report"]["love"] == ""
    assert body["report"]["economy"] == ""
    assert body["report"]["overall"].strip()
    text = _visible_text(body)
    for word in ROMANCE_WORDS:
        assert word not in text


def test_disposition_copy_changes_with_relation():
    friend = _analyze("friend")["report"]["overall"]
    family = _analyze("family")["report"]["overall"]
    business = _analyze("business")["report"]["overall"]
    coworker = _analyze("coworker")["report"]["overall"]
    assert len({friend, family, business, coworker}) == 4
    assert "친구 사이에서는" in friend
    assert "가족 사이에서는" in family
    assert "사업에서는" in business
    assert "직장에서는" in coworker
    assert "약속을 잡을 때" in friend
    assert "가격이나 일정" in business
    assert "집안 행사" in family
    assert "보고 방식" in coworker


def test_romantic_economy_restores_day_pillar_copy_without_score_change():
    romantic = _analyze("romantic")
    spouse = _analyze("spouse")
    business = _analyze("business")
    assert romantic["scores"] == spouse["scores"] == business["scores"]
    assert romantic["scores"]["economy"] == 71
    assert romantic["scores"]["total"] == 72
    assert romantic["one_liner"] == spouse["one_liner"]
    economy = romantic["report"]["economy"]
    assert economy == spouse["report"]["economy"]
    assert "생활비와 저축을 두고 보면" not in economy
    assert "스타식" not in economy
    assert "보름자리" not in economy
    assert "탄탄한 경제력" not in economy
    assert "꼼꼼" in economy
    assert business["report"]["economy"] == ""
    assert business["report"]["love"] == ""
    assert romantic["report"]["love"].strip()
    assert romantic["report"]["overall"] != business["report"]["overall"]


def test_economy_polish_fixes_typos_and_softens_promises():
    from domains.compatibility.content_db import polish_economy

    text = polish_economy(
        "서로의 소비 스타식을 존중하며 알뜰하게 보름자리를 가꾸어 나가 보세요. "
        "아주 탄탄한 경제력을 갖추게 될 거예요."
    )
    assert "스타일을" in text
    assert "스타식" not in text
    assert "보금자리" in text
    assert "수월해질 거예요" in text
    assert "탄탄한 경제력" not in text
