"""건강운 문장 교정. 다른 분야의 문장은 바꾸지 않는다."""
from domains.yearly.health_prose import rewrite_health_sentence, rewrite_health_text


def test_breakfast_does_not_claim_to_hold_metabolism():
    raw = "아침 식사는 거르지 말고 가볍게라도 단백질과 탄수화물을 챙겨 먹어 하루의 대사량을 유지하는 것이 좋습니다."
    done = rewrite_health_sentence(raw)
    assert "대사량" not in done
    assert "식사 리듬" in done
    assert done.startswith("아침 식사는 거르지 말고")


def test_beer_is_not_a_recovery_method():
    raw = "혼자서 끙끙 앓기보다 믿을 만한 친구나 멘토를 만나 가볍게 맥주 한 잔 기울이며 속마음을 터놓아 보세요."
    done = rewrite_health_sentence(raw)
    assert "맥주" not in done
    assert "따뜻한 차" in done
    assert "편안한 대화" in done


def test_exercise_metabolism_and_drinking_caution_stay():
    exercise = "매일 아침 가벼운 유산소 운동으로 하루의 대사량을 높이고 상쾌한 기분으로 시작하는 습관을 들여보세요."
    caution = "사람들과 어울리는 자리가 많아지더라도 과식이나 과음을 피하고 적당히 조절하는 지혜가 필요해요."
    assert rewrite_health_text(exercise) == exercise
    assert rewrite_health_text(caution) == caution
