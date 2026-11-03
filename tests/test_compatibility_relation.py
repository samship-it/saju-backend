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
    assert friend["one_liner"] == "이런 친구, 평생 옆에 둬야지! 🤝"
    assert family["one_liner"] == "역시 가족은 가족이네! 🏡"
    assert business["one_liner"] == "이 조합이면 판을 키울 수 있겠는데? 🚀"
    assert coworker["one_liner"] == "같이 일하면 시너지가 제대로 나겠어! 💪"
    assert acquaintance["one_liner"] == "처음부터 왠지 통하는 사람! ✨"
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


def test_section_leads_drop_title_echo_and_keep_the_point():
    from domains.compatibility.relation_voice import trim_section_lead

    romantic = _analyze("romantic")
    assert romantic["scores"]["economy"] == 71
    assert not romantic["report"]["conflict"].startswith("갈등")
    assert not romantic["report"]["economy"].startswith("경제")
    assert "꼼꼼" in romantic["report"]["economy"]
    kept = trim_section_lead(
        "economy",
        "돈을 관리하고 소비하는 스타일에 있어서 두 분은 신중해요.",
    )
    assert kept.startswith("돈을 관리하고 소비")
    assert trim_section_lead(
        "conflict",
        "갈등이 생길 때는 서로의 의견 차이로 인해 감정이 상할 수 있어요.",
    ) == "서로의 의견 차이로 인해 감정이 상할 수 있어요."
    assert trim_section_lead(
        "communication",
        "대화를 나눌 때 나는 먼저 듣습니다.",
    ).startswith("대화를 나눌 때")


def test_nonromantic_scenes_follow_the_relation_without_score_change():
    from domains.compatibility.relation_voice import adapt_text

    src = (
        "상대가 주도권을 잡고 리드하려 할 때 넓은 마음으로 받아주면 "
        "상대는 금방 마음을 풀고 내게 뜨겁게 안겨옵니다."
    )
    assert "안겨옵니다" in adapt_text(src, "romantic")
    friend = adapt_text(src, "friend")
    assert "주도권" in friend
    assert "우정" in friend
    assert "안겨" not in friend
    business = adapt_text(src, "business")
    assert "역할" in business and "협업" in business
    assert "거리" in adapt_text(src, "acquaintance")
    assert "선을" not in adapt_text("서로를 품어주는 따뜻한 인연입니다.", "acquaintance")
    assert "사이예요" in adapt_text("완벽한 커플이에요.", "friend")
    assert "사이가에요" not in adapt_text("완벽한 커플이에요.", "friend")
    kept = adapt_text("든든함을 안겨 줍니다. 나는 우직하게 참아내요.", "friend")
    assert "든든함을 안겨" in kept
    assert "참아내" in kept
    body = _analyze("friend")
    assert body["scores"]["total"] == 72
    assert body["scores"]["economy"] == 71
    blob = "\n".join(body["report"].values())
    for word in ("안식처", "짝꿍", "손잡고", "연애", "사랑"):
        assert word not in blob


# 연인·배우자 한줄평. 60~69만 바뀌었고 등급명과 나머지 문장은 그대로다.
_ROMANTIC_LINES = (
    (90, 100, "💍 천생연분", "이 정도면 결혼각 💍"),
    (80, 89, "🏠 반려생활", "우린 장기전에 강해요."),
    (70, 79, "🧩 찰떡짝꿍", "생각보다 우리, 잘 맞는데?"),
    (60, 69, "💕 짝꿍연습중", "조금만 맞추면 더 좋아질 거야."),
    (50, 59, "💌 더 가까이", "좀 더 다가와줄래?"),
    (40, 49, "🌱 노력형 사랑", "사랑은 주는 거니까."),
    (30, 39, "↔️ 다른 사람", "우리, 좀 다르네."),
    (0, 29, "─ 평행선", "좋아하는 마음만으로는 조금 어려워요."),
)
_RELATION_LINES = {
    "friend": (
        "이런 친구, 평생 옆에 둬야지! 🤝",
        "말하지 않아도 통하는 사이.",
        "우리 은근히 잘 맞는 조합인데?",
        "조금씩 알아가면 더 좋겠어.",
        "다름을 인정하면 괜찮아질 사이.",
        "친해지려면 서로 노력이 필요해.",
        "우리는 꽤 다른 타입이네.",
        "친하다는 이유만으로 다 맞을 순 없지.",
    ),
    "family": (
        "역시 가족은 가족이네! 🏡",
        "서로 달라도 결국 든든한 내 편.",
        "우리 가족, 생각보다 합이 좋은데?",
        "조금만 더 이해하면 편해질 사이.",
        "가족이어도 서로의 방식은 존중해야 해.",
        "가까운 만큼 서로 배려가 필요해.",
        "가족이지만 생각은 꽤 다르네.",
        "가족이라는 이유로 모든 걸 맞출 필요는 없어.",
    ),
    "business": (
        "이 조합이면 판을 키울 수 있겠는데? 🚀",
        "서로의 강점이 확실한 팀.",
        "역할만 잘 나누면 꽤 괜찮은 조합.",
        "합의와 조율이 성과를 좌우하겠어.",
        "시작 전에 역할과 책임부터 맞춰보자.",
        "일하는 방식부터 조율해야겠어.",
        "목표가 같아도 접근법은 다르네.",
        "의욕만으로 함께 사업하기는 어려워.",
    ),
    "coworker": (
        "같이 일하면 시너지가 제대로 나겠어! 💪",
        "서로의 빈틈을 채워주는 좋은 조합.",
        "호흡만 맞추면 일하기 편하겠는데?",
        "소통 방식을 맞추면 더 수월해질 사이.",
        "업무 기준부터 맞춰보는 게 좋겠어.",
        "서로의 업무 스타일을 이해해야겠어.",
        "일하는 방식이 꽤 다르네.",
        "친해지는 것보다 업무 경계를 명확히 하는 게 먼저야.",
    ),
    "acquaintance": (
        "처음부터 왠지 통하는 사람! ✨",
        "알아갈수록 괜찮은 인연이네.",
        "생각보다 대화가 잘 통하는 사이.",
        "천천히 알아가면 좋을 것 같아.",
        "아직은 서로 알아가는 중.",
        "조금 더 거리를 두고 알아가 보자.",
        "서로의 결이 꽤 다른 편이네.",
        "모든 사람과 가까워질 필요는 없으니까.",
    ),
}


def test_one_liners_use_eight_bands_and_keep_scores():
    from domains.compatibility.disposition import one_liner

    romantic_lines = {line for _lo, _hi, _grade, line in _ROMANTIC_LINES}
    other_lines = {line for lines in _RELATION_LINES.values() for line in lines}
    assert romantic_lines.isdisjoint(other_lines)

    for lo, hi, grade, line in _ROMANTIC_LINES:
        for score in (lo, hi):
            band = compat_band(score)
            assert band["one_liner"] == line
            assert band["relation_type"] == grade
            assert band["band"] == f"{lo}-{hi}"
        if lo > 0:
            assert compat_band(lo - 1)["one_liner"] != line
        if hi < 100:
            assert compat_band(hi + 1)["one_liner"] != line
    assert compat_band(60)["one_liner"] == "조금만 맞추면 더 좋아질 거야."
    assert compat_band(59)["one_liner"] == "좀 더 다가와줄래?"
    assert compat_band(70)["one_liner"] == "생각보다 우리, 잘 맞는데?"

    for relation, lines in _RELATION_LINES.items():
        assert len(lines) == 8
        for (lo, hi, _grade, romantic_line), line in zip(_ROMANTIC_LINES, lines):
            for score in (lo, hi):
                assert one_liner(score, relation) == line
            assert line != romantic_line
            if lo > 0:
                assert one_liner(lo - 1, relation) != line
            if hi < 100:
                assert one_liner(hi + 1, relation) != line
        assert len({one_liner(90, relation) for relation in _RELATION_LINES}) == 5

    romantic = _analyze("romantic")
    spouse = _analyze("spouse")
    assert romantic["scores"]["total"] == spouse["scores"]["total"] == 72
    assert romantic["one_liner"] == spouse["one_liner"] == "생각보다 우리, 잘 맞는데?"
    assert romantic["relation_type_label"] == spouse["relation_type_label"] == "🧩 찰떡짝꿍"
    friend = _analyze("friend")
    assert friend["scores"] == romantic["scores"]
    assert friend["scores"]["overall"] == 96
    assert friend["one_liner"] == "이런 친구, 평생 옆에 둬야지! 🤝"
    assert friend["relation_type_label"] == "성향 궁합"
    assert friend["score_band"] == "90-100"

