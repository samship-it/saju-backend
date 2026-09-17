"""대운/세운/일운 실시간 보정 엔진(domains/daily/woon_modifier.py) 단위 테스트."""
import itertools

from core.constants import GAN_ELEM, JI_ELEM
from domains.daily.woon_modifier import (
    WOON_STATE_TABLE, compute_woon_modifier, _relation_bucket,
)

GAN_H = list(GAN_ELEM.keys())
JI_H = list(JI_ELEM.keys())
ALL60 = [GAN_H[i % 10] + JI_H[i % 12] for i in range(60)]


def _saju(day_master, day_branch, daewoon="", sewoon="", ilwoon="", strength=None):
    return {
        "day_master": day_master,
        "day_branch": day_branch,
        "current_daewoon": {"ganji": daewoon} if daewoon else {},
        "seewoon_10years": [{"ganji": sewoon}] if sewoon else [],
        "today_ganji": {"day": ilwoon} if ilwoon else {},
        "strength": strength or {},
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
    # 己丑 은 申(일지) 기준 십이신살 경고 4종/백호/양인 어디에도 안 걸리는 "순수" 긍정 케이스.
    mod = compute_woon_modifier(_saju("壬", "申", daewoon="己丑", sewoon="己丑", ilwoon="己丑"))
    assert mod["score_delta"] == 24
    assert mod["state_label"] == "명예/승진운"
    assert mod["sinsal_hits"] == []


def test_trigger_layer_uses_normalized_intensity_not_raw_weight():
    # 대운=파(약한 관계, 가중치 큼) vs 일운=충(강한 관계, 가중치 작음) 이 동시에 걸릴 때
    # 정규화 강도 기준으로 더 "실제로 강한" 레이어(일운)가 트리거로 선택돼야 한다.
    mod = compute_woon_modifier(_saju("戊", "子", daewoon="己酉", sewoon="丙午", ilwoon="甲午"))
    assert mod["trigger_layer"] == "ilwoon"
    assert mod["state_label"] == "관재/마찰 주의"


def test_weak_daymaster_siksang_forced_negative():
    # 신약 + 식신(식상군) 일운 -> 기본표(+0.7)가 아니라 강제로 부정.
    from domains.daily.woon_modifier import _layer_facts

    # 금(金)을 용신/기신/희신 어디에도 안 넣어 "한신"으로 만든 뒤에도, 신약+식상
    # 규칙이 별도로 강제 음수를 걸어야 한다(오행 희기와 무관하게 항상 적용).
    strength = {"verdict": "신약", "yongsin": ["수"], "gisin": ["화", "토"], "heesin": []}
    facts = _layer_facts("戊", "午", "庚戌", strength)  # 戊(토)->庚(금,식신,한신 오행)
    assert facts["sipsin_gan"] == "식신"
    assert facts["group_gan"] == "식상"
    assert facts["polarity_gan"] < 0  # 오행 자체는 한신인데도 신약+식상 규칙으로 강제 음수


def test_yongsin_gisin_overrides_base_polarity_sign():
    from domains.daily.woon_modifier import _layer_facts

    strength = {"verdict": "신강", "yongsin": ["화"], "gisin": ["목"], "heesin": []}
    # 甲(목,비견) 은 기본표에서 +0.2 지만, 목이 기신이면 음수로 뒤집혀야 한다.
    facts = _layer_facts("甲", "子", "甲子", strength)
    assert facts["sipsin_gan"] == "비견"
    assert facts["polarity_gan"] == -1.0


def test_twelve_sinsal_detects_warning_and_baekho_yangin():
    from core.twelve_sinsal import sinsal_check
    from core.constants import BAEKHO, YANGIN

    # 일지 子(申子辰국) 기준 巳 -> 겁살(경고)
    r = sinsal_check("子", "巳")
    assert r["name"] == "겁살"
    assert r["is_warning"] is True
    # 甲辰은 백호 7종에 포함
    assert "甲辰" in BAEKHO
    # 壬 일간의 양인은 子
    assert YANGIN["壬"] == "子"


def test_sinsal_penalty_and_note_flow_into_modifier():
    # 戊 일간, 子 일지: 오늘 甲午 -> 지지 午 = 재살(경고) + 戊의 양인(午)과도 일치.
    mod = compute_woon_modifier(_saju("戊", "子", ilwoon="甲午"))
    names = {h["name"] for h in mod["sinsal_hits"]}
    assert "재살" in names
    assert "양인" in names
    assert mod["sinsal_penalty"] < 0
    assert "재살" in mod["state_comment"] or "양인" in mod["state_comment"]


def test_relation_bucket_mapping():
    assert _relation_bucket("육합(협력·인연)") == "harmony"
    assert _relation_bucket("충(충돌·이동)") == "conflict"
    assert _relation_bucket("형(마찰·조정)") == "adjustment"
    assert _relation_bucket("파(어긋남)") == "friction"
    assert _relation_bucket("해(방해·구설)") == "friction"
    assert _relation_bucket("복음(같은 지지)") == "repeat"
    assert _relation_bucket("무관") == "neutral"
