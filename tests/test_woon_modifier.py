"""대운/세운/일운 실시간 보정 엔진(domains/daily/woon_modifier.py) 단위 테스트."""
import itertools

from core.constants import GAN_ELEM, JI_ELEM
from domains.daily.woon_modifier import (
    WOON_STATE_TABLE, compute_woon_modifier, _relation_bucket,
)

GAN_H = list(GAN_ELEM.keys())
JI_H = list(JI_ELEM.keys())
ALL60 = [GAN_H[i % 10] + JI_H[i % 12] for i in range(60)]


def _saju(day_master, day_branch, daewoon="", sewoon="", ilwoon=""):
    return {
        "day_master": day_master,
        "day_branch": day_branch,
        "current_daewoon": {"ganji": daewoon} if daewoon else {},
        "seewoon_10years": [{"ganji": sewoon}] if sewoon else [],
        "today_ganji": {"day": ilwoon} if ilwoon else {},
    }


def test_state_table_covers_all_group_bucket_combos():
    groups = {"비겁", "식상", "재성", "관성", "인성"}
    buckets = {"harmony", "conflict", "adjustment", "friction", "repeat", "neutral"}
    assert set(WOON_STATE_TABLE.keys()) == groups
    for g in groups:
        assert set(WOON_STATE_TABLE[g].keys()) == buckets
        for b in buckets:
            entry = WOON_STATE_TABLE[g][b]
            assert entry["label"] and entry["comment"]


def test_score_delta_always_within_bounds():
    # 브루트포스로 최악/최선 조합을 훑어도 -40~+40 을 벗어나지 않아야 한다.
    for dm, db, dw, sw, il in itertools.islice(
        itertools.product(GAN_H[:3], JI_H[:3], ALL60[:10], ALL60[10:20], ALL60[20:30]), 200
    ):
        mod = compute_woon_modifier(_saju(dm, db, dw, sw, il))
        assert -40 <= mod["score_delta"] <= 40


def test_missing_daewoon_does_not_crash():
    # 첫 대운 시작 나이 이전(current_daewoon={}) 인 경우에도 세운/일운만으로 정상 동작.
    mod = compute_woon_modifier(_saju("甲", "子", daewoon="", sewoon="丙午", ilwoon="甲午"))
    assert "daewoon" not in mod["layers"]
    assert mod["trigger_layer"] in ("sewoon", "ilwoon")
    assert -40 <= mod["score_delta"] <= 40


def test_all_layers_empty_falls_back_to_default_state():
    mod = compute_woon_modifier(_saju("甲", "子"))
    assert mod["layers"] == {}
    assert mod["trigger_layer"] is None
    assert mod["score_delta"] == 0
    assert mod["state_label"] == "무난한 흐름"


def test_strong_positive_all_layers_picks_positive_label():
    mod = compute_woon_modifier(_saju("壬", "申", daewoon="己巳", sewoon="己巳", ilwoon="己巳"))
    assert mod["score_delta"] == 40  # 이론상 42 -> 상한 클리핑
    assert mod["state_label"] == "명예/승진운"


def test_trigger_layer_uses_normalized_intensity_not_raw_weight():
    # 대운=파(약한 관계, 가중치 큼) vs 일운=충(강한 관계, 가중치 작음) 이 동시에 걸릴 때
    # 정규화 강도 기준으로 더 "실제로 강한" 레이어(일운)가 트리거로 선택돼야 한다.
    mod = compute_woon_modifier(_saju("戊", "子", daewoon="己酉", sewoon="丙午", ilwoon="甲午"))
    assert mod["trigger_layer"] == "ilwoon"
    assert mod["state_label"] == "관재/마찰 주의"


def test_relation_bucket_mapping():
    assert _relation_bucket("육합(협력·인연)") == "harmony"
    assert _relation_bucket("충(충돌·이동)") == "conflict"
    assert _relation_bucket("형(마찰·조정)") == "adjustment"
    assert _relation_bucket("파(어긋남)") == "friction"
    assert _relation_bucket("해(방해·구설)") == "friction"
    assert _relation_bucket("복음(같은 지지)") == "repeat"
    assert _relation_bucket("무관") == "neutral"
