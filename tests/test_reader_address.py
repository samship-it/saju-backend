"""개인 운세 문장에 여러 사람을 부르는 호칭이 남지 않는지 확인한다."""
from pathlib import Path

from shared.prose_quality import finish_reading, polish_text
from shared.text_format import to_one_reader

ROOT = Path(__file__).resolve().parents[1]


def test_one_reader_keeps_the_prediction():
    solo = to_one_reader("솔로 여러분, 오늘은 가만히 있어도 눈에 띄어요.")
    assert solo == "오늘은 가만히 있어도 눈에 띄어요."
    assert "여러분" not in solo

    trait = to_one_reader("눈치 빠른 여러분은 특유의 재치로 분위기를 살려요.")
    assert trait == "눈치 빠른 당신은 특유의 재치로 분위기를 살려요."

    hobby = to_one_reader("올해 취미를 통해 여러분은 내면의 감정을 풀어내요.")
    assert hobby == "올해 취미를 통해 내면의 감정을 풀어내요."

    weapon = to_one_reader("감각이 여러분의 가장 큰 무기예요.")
    assert weapon == "감각이 당신의 가장 큰 무기예요."

    couple = to_one_reader("두 사람 사이에 흐르는 기운이 여러분의 앞날을 밝혀요.")
    assert couple == "두 사람 사이에 흐르는 기운이 두 사람의 앞날을 밝혀요."
    assert "여러분" not in couple


def test_served_text_drops_the_crowd_address_even_when_proofread_is_off(monkeypatch):
    source = "올해 여러분은 매력이 먼저 보여요."
    assert polish_text(source) == "올해 당신은 매력이 먼저 보여요."
    monkeypatch.setenv("PROOFREAD_ENABLED", "")
    monkeypatch.setenv("PROOFREAD_LLM_ENABLED", "")
    kept, _ = finish_reading({"content_type": "결혼운", "overall": source})
    assert kept["overall"] == "올해 당신은 매력이 먼저 보여요."
    assert "여러분" not in kept["overall"]


def test_stored_fortune_text_has_no_crowd_address():
    hits = []
    for path in (ROOT / "domains").rglob("*.json"):
        if "여러분" in path.read_text(encoding="utf-8"):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []
