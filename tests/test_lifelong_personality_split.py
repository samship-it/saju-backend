"""평생 사주와 성격운세는 같은 원국을 보되 같은 문장을 싣지 않는다."""
import re

from domains.lifelong.life_voice import build_core_voice
from domains.lifelong.service import analyze_lifelong_fortune
from domains.personality.behavior_voice import deepen_character
from domains.personality.content_db import load_db, lookup
from domains.personality.service import analyze_aptitude, analyze_character
from domains.personality.trait_signals import shares
from shared.prose_quality import repeated_sentence_count

_FORBIDDEN = re.compile(r"십신|용신|희신|기신|신강|신약|비겁|식상|재성|관성|인성")
_BIRTHS = (
    (1990, 2, 6, 14, 0, "female"),
    (1990, 5, 15, 10, 0, "male"),
    (1983, 5, 14, 14, 0, "female"),
)


def _stages():
    return [{"age_range": [4 + i * 10, 13 + i * 10]} for i in range(8)]


def _facts():
    groups = ["식상", "재성", "관성", "인성", "비겁", "식상", "재성", "관성"]
    return [{"sipsin_group": group} for group in groups]


def _character_blob(character):
    return " ".join(str(value) for value in character.values() if isinstance(value, str))


def test_life_voice_does_not_copy_any_stored_character_essay():
    db = load_db()
    assert len(db) >= 60
    for entry in db.values():
        character = entry.get("character")
        if not isinstance(character, dict):
            continue
        personality, weaknesses = build_core_voice(character, _stages(), _facts())
        blob = _character_blob(character)
        assert personality and weaknesses
        assert not shares(personality, blob)
        assert not shares(weaknesses, blob)
        assert len(personality) >= len(character.get("base_nature") or "")
        assert len(weaknesses) >= len(character.get("weaknesses") or "")
        assert not _FORBIDDEN.search(personality)
        assert not _FORBIDDEN.search(weaknesses)
        assert repeated_sentence_count(personality) == 0
        assert repeated_sentence_count(weaknesses) == 0
        deepened = deepen_character(character)
        for key, original in character.items():
            if not isinstance(original, str) or not original:
                continue
            assert original[:20] in deepened[key]
            extra = deepened[key].split("\n\n", 1)[1] if "\n\n" in deepened[key] else ""
            assert not shares(extra, personality)
            assert not shares(extra, weaknesses)


def test_unmentioned_trait_is_not_added():
    quiet = {
        "base_nature": "조용히 자기 속도를 지키며 하루를 정리하는 사람입니다.",
        "strengths": "맡은 기록을 빠짐없이 남기는 힘이 있습니다.",
        "weaknesses": "변화를 서두르지 않아 기회가 지나간 뒤에야 알아차립니다.",
        "supplement": "주말에 한 번, 이번 주의 기록을 다시 읽어 보세요.",
        "relationships": "소수의 사람과 오래 연락을 유지합니다.",
        "work_style": "같은 업무를 반복해도 정확도가 떨어지지 않습니다.",
    }
    personality, weaknesses = build_core_voice(quiet, _stages(), _facts())
    assert "활동 무대가 차례로" not in personality
    assert "경력의 줄기가 끊기" not in personality
    assert "마지막 구간의 주인" not in weaknesses

    broad = dict(quiet)
    broad["base_nature"] = "언제나 더 넓은 시야로 큰 그림을 그리며 움직입니다."
    personality, _ = build_core_voice(broad, _stages(), _facts())
    assert "활동 무대가 차례로" in personality


def test_child_decade_stays_with_study_allowance_and_friends():
    personality, weaknesses = build_core_voice(
        {"base_nature": "조용히 자기 속도를 지키며 하루를 정리하는 사람입니다."},
        _stages(),
        _facts(),
    )
    assert "4세부터 13세까지는 호기심과 표현을 공부와 놀이로 시험하는 시기입니다." in personality
    assert "4세부터 13세까지는 들어온 결과" not in personality
    assert "14세부터는 집안의 살림과 용돈" in weaknesses


def test_live_products_keep_their_fields_and_do_not_share_sentences():
    seen = set()
    for birth in _BIRTHS:
        life, life_fallback = analyze_lifelong_fortune(*birth, False)
        character, char_fallback = analyze_character(*birth, False)
        aptitude, _ = analyze_aptitude(*birth, False)
        assert life_fallback is False
        assert char_fallback is False
        core = life["data"]["core_nature"]
        assert list(core.keys()) == ["personality", "life_theme", "weaknesses", "tip"]
        assert core["life_theme"] and core["tip"]
        assert set(life["data"]["life_domains"]) >= {"wealth", "career", "family", "social"}
        assert len(life["data"]["life_stages"]) == 8
        for period in ("early_life", "middle_life", "late_life"):
            assert life["data"][period]

        report = character["report"]
        assert set(report) == {
            "base_nature", "strengths", "weaknesses", "supplement", "relationships", "work_style",
        }
        stored = lookup(character["saju_info"]["day_ganji"], "character")
        stored_apt = lookup(character["saju_info"]["day_ganji"], "aptitude")
        blob = _character_blob(stored)
        assert not shares(core["personality"], blob)
        assert not shares(core["weaknesses"], blob)
        assert len(core["personality"]) >= len(stored["base_nature"])
        assert len(core["weaknesses"]) >= len(stored["weaknesses"])
        assert stored["base_nature"][:20] in report["base_nature"]
        assert len(report["base_nature"]) > len(stored["base_nature"])
        assert "세 칸이 비어 있으면" not in aptitude["report"]["fit_task"]
        assert stored_apt["fit_task"][:20] in aptitude["report"]["fit_task"]
        period_text = " ".join(
            str(value)
            for period in ("early_life", "middle_life", "late_life")
            for value in life["data"][period].values()
            if isinstance(value, str)
        )
        assert not shares(core["personality"], period_text)
        assert not shares(core["weaknesses"], period_text)
        seen.add(core["personality"])
    assert len(seen) == len(_BIRTHS)


def test_character_lookup_cache_is_not_rewritten():
    data, _ = analyze_character(1990, 2, 6, 14, 0, "female", False)
    ilju = data["saju_info"]["day_ganji"]
    before = lookup(ilju, "character")["base_nature"]
    analyze_character(1990, 2, 6, 14, 0, "female", False)
    assert lookup(ilju, "character")["base_nature"] == before


def test_missing_character_row_keeps_the_old_fallback_sentence(monkeypatch):
    import domains.lifelong.service as svc

    monkeypatch.setattr(svc, "lookup_personality", lambda ilju, group: None)
    data, is_fallback = analyze_lifelong_fortune(1990, 5, 15, 10, 0, "male", False)
    assert is_fallback is True
    personality = data["data"]["core_nature"]["personality"]
    weaknesses = data["data"]["core_nature"]["weaknesses"]
    assert "자기 페이스를 지키는 성향입니다." in personality
    assert "변화의 타이밍을 놓치기 쉽습니다." in weaknesses
    assert "세부터" in personality
