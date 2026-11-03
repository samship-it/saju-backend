from domains.daily.service import _shape
from shared.text_format import strip_reader_greeting


def test_strip_reader_greeting_keeps_the_fortune_sentence():
    text = "안녕하세요, 멋진 하루를 항해하는 호랑이님! 오늘은 계획을 차분히 점검할 시간입니다."
    assert strip_reader_greeting(text) == "오늘은 계획을 차분히 점검할 시간입니다."


def test_today_insight_does_not_address_the_reader_by_animal():
    shaped = _shape(
        {
            "overall_score": 70,
            "summary": {
                "overall": "반갑습니다, 거침없는 호랑이님! 오늘은 미뤄둔 일을 정리하기 좋은 날입니다.",
            },
            "keywords": ["정리", "점검", "속도"],
        },
        {},
        {"headline": "오늘은 한 박자 천천히 가는 날입니다."},
    )
    overall = shaped["summary"]["overall"]
    assert "안녕하세요" not in overall
    assert "반갑습니다" not in overall
    assert "호랑이" not in overall
    assert overall.startswith("오늘은")


def test_stored_insights_do_not_open_with_a_greeting():
    from domains.daily.content_db import load_db

    for key, entry in load_db().items():
        overall = (entry.get("summary") or {}).get("overall") or ""
        assert not overall.startswith(("안녕하세요", "반갑습니다", "우와", "와우")), key
        assert "호랑이님" not in overall, key
