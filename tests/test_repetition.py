"""한 편 운세의 반복 제한.

올해와 같은 뜻의 묶음은 두 번까지다.
점수, 키워드, 상징 오브젝트는 그대로 둔다.
"""
from shared.repetition import limit_entry, limit_prose, over_limit


def test_year_word_drops_even_when_another_repeat_stays():
    text = " ".join([
        "올해 취미는 붓을 드는 흐름이에요.",
        "창작 활동이 올해 아주 잘 맞아요.",
        "이 과정에서 혼자만의 작업 시간이 올해 훨씬 잘 맞아요. 감정에만 집중해요.",
    ])
    out = limit_prose([text])[0]
    assert out.count("올해") == 2
    assert "이 과정에서" in out
    text = " ".join([
        "올해 사업은 협력으로 내실을 다져요.",
        "올해 방향은 함께 판을 짜는 쪽이에요.",
        "올해의 무기는 신뢰예요.",
        "올해는 역할을 문서로 남기세요.",
        "올해를 관통하는 파트너 운이 강해요.",
    ])
    out = limit_prose([text])[0]
    assert out.count("올해") == 2
    assert "협력으로 내실을 다져요" in out
    assert "역할을 문서로 남기세요" in out
    assert over_limit([out]) == {}


def test_same_meaning_cluster_is_capped_without_a_forced_synonym():
    parts = limit_prose([
        "평온한 하루가 먼저 찾아와요. 안정적인 루틴이 그다음이에요. 안정감이 일을 받쳐 줘요.",
    ])
    assert parts[0].count("안정") <= 2
    assert "심정" not in parts[0]
    assert over_limit(parts) == {}


def test_income_phrase_and_product_name_stay_readable():
    text = " ".join([
        "기회의 달에는 제안을 검토해 보세요.",
        "고정 수입과 알짜배기 부수입을 함께 살펴요.",
        "수입을 높이는 이야기만 반복하지 마세요.",
        "수익이 들어와도 서두르지 마세요.",
    ])
    out = limit_prose([text])[0]
    assert "기회의 달" in out
    assert "고정 수입과" in out or "알짜배기 부수입" in out
    assert "견이" not in out
    assert " " not in out.replace("  ", "") or "  " not in out


def test_entry_leaves_scores_keywords_and_object():
    entry = {
        "_model": "gemini",
        "concept_object": "지갑",
        "keywords": ["올해"],
        "one_line": "올해 돈의 흐름이 차분해져요.",
        "overall_flow": "올해는 들어올 돈을 먼저 세어 봐요. 올해 지출은 나눠 두세요.",
        "stay_vs_move": {"stay_score": 4, "move_score": 2, "verdict": "유지 권장"},
    }
    limit_entry(entry)
    assert entry["concept_object"] == "지갑"
    assert entry["keywords"] == ["올해"]
    assert entry["_model"] == "gemini"
    assert entry["stay_vs_move"]["stay_score"] == 4
    assert entry["stay_vs_move"]["verdict"] == "유지 권장"
    prose = entry["one_line"] + entry["overall_flow"]
    assert prose.count("올해") <= 2


def test_a_phrase_of_the_same_cluster_counts_once():
    from shared.repetition import over_limit

    text = "주변 사람들과의 인간관계는 따뜻하고 다정한 말로 풀려요. 성과는 따로 말해요."
    assert over_limit([text, "사람들 이야기가 다시 나와요.", "인간관계가 또 나와요."])["주변"] == 3
    once = over_limit([text])
    assert "주변" not in once
    assert "다정" not in once
