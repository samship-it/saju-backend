"""관계 유형은 기존 점수 필드를 고르고, 연애 이외 문장만 일주 해설에서 다듬는다."""
import pytest
from fastapi.testclient import TestClient

import main
from core.constants import compat_band

client = TestClient(main.app)

BIRTH_A = {"year": 1990, "month": 3, "day": 15, "hour": 10, "minute": 30, "gender": "male"}
BIRTH_B = {"year": 1992, "month": 7, "day": 8, "hour": 14, "minute": 0, "gender": "female"}
OTHERS = ("friend", "family", "business", "coworker", "acquaintance")
# 애정은 배려의 뜻으로 가족 문장에 남을 수 있다. 연애를 전제한 말만 막는다.
ROMANCE_WORDS = ("연애", "연인", "커플", "사랑", "썸", "스킨십", "데이트", "배우자", "결혼", "신혼", "로맨", "부부")


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
    assert "안정적인 사랑" in body["report"]["overall"]


def test_spouse_keeps_romantic_copy_unless_dating_stage():
    romantic = _analyze("romantic")
    spouse = _analyze("spouse")
    assert spouse["one_liner"] == romantic["one_liner"]
    assert spouse["scores"] == romantic["scores"]
    assert spouse["report"]["love"].strip()
    assert spouse["report"]["economy"] == romantic["report"]["economy"]
    assert spouse["report"]["overall"] == romantic["report"]["overall"]


@pytest.mark.parametrize("relation", OTHERS)
def test_other_relations_reuse_day_pillar_without_romance_premise(relation):
    romantic = _analyze("romantic")
    body = _analyze(relation)
    assert body["relation_type_label"] == "성향 궁합"
    assert body["scores"] == romantic["scores"]
    assert body["scores"]["overall"] == 96
    assert body["scores"]["total"] == 72
    assert body["scores"]["love"] == 53
    assert body["report"]["love"] == ""
    assert body["report"]["economy"].strip()
    assert body["report"]["overall"].strip()
    text = _visible_text(body)
    assert "안정적인 관계를" in body["report"]["overall"]
    assert "관계을" not in text
    assert "친구은" not in text
    for word in ROMANCE_WORDS:
        assert word not in text
    assert "참상대" not in text
    assert "들상대" not in text


def test_relation_voice_changes_only_awkward_words():
    friend = _analyze("friend")
    family = _analyze("family")
    business = _analyze("business")
    coworker = _analyze("coworker")
    acquaintance = _analyze("acquaintance")
    assert "친구 사이에서는" in friend["one_liner"]
    assert "가족 사이에서는" in family["one_liner"]
    assert "사업에서는" in business["one_liner"]
    assert "직장에서는" in coworker["one_liner"]
    assert "지인 사이에서는" in acquaintance["one_liner"]
    for body in (friend, family, business, coworker, acquaintance):
        blob = "\n".join(body["report"].values())
        for bad in ("관계을", "집를", "일를", "기준를", "가족로", "지인로", "비용와"):
            assert bad not in blob
    assert "살림" in family["report"]["economy"]
    assert "살림" not in friend["report"]["economy"]
    assert "돈을 아껴 쓰는" in friend["report"]["economy"]
    assert "챙겨가는" not in friend["report"]["economy"]
    assert "나눠 쓰는" not in friend["report"]["economy"]
    assert "비용을 아껴 쓰는" in business["report"]["economy"]
    assert "경비를 챙겨" not in business["report"]["economy"]
    assert "관리하는 뛰어난" not in business["report"]["economy"]
    assert "공동 비용을 아껴 쓰는" in coworker["report"]["economy"]
    assert "나눠 쓰는" not in coworker["report"]["economy"]
    assert "지출을 아껴 쓰는" in acquaintance["report"]["economy"]
    assert "돈을 쓰는 뛰어난" not in acquaintance["report"]["economy"]
    assert "아름다운 지인" not in acquaintance["report"]["relationship_advice"]
    assert "단단한 집" not in family["report"]["relationship_advice"]
    assert "일으로" not in "\n".join(friend["report"].values())
    assert len({
        friend["report"]["economy"],
        family["report"]["economy"],
        business["report"]["economy"],
        coworker["report"]["economy"],
        acquaintance["report"]["economy"],
    }) == 5


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
    assert business["report"]["economy"].strip()
    assert "비용" in business["report"]["economy"]
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


def test_voice_keeps_embedded_syllables_and_strips_romance():
    from domains.compatibility.relation_voice import adapt_text

    text = adapt_text(
        "나는 우직하게 참아내며 습관을 들여보세요. 내 남편이자 내 아내가 되어줄 거예요. "
        "따뜻한 스킨십과 데이트 비용으로 연애를 이어가요.",
        "friend",
    )
    assert "참아내" in text
    assert "들여보세요" in text
    assert "내 상대이자 내 상대" in text
    assert "남편" not in text
    assert "스킨십" not in text
    assert "데이트" not in text
    assert "연애" not in text
