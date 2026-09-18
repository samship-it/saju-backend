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


def test_resolve_bucket_sign_overrides_relation_type():
    # 1961년생 남 실측 버그 재현: 관계는 '해'(friction)지만 희기가 강하게 긍정이면
    # "주의" 계열이 아니라 harmony로 재분류돼야 한다.
    from domains.daily.woon_modifier import _resolve_bucket

    assert _resolve_bucket("friction", 0.36) == "harmony"
    assert _resolve_bucket("harmony", -0.36) == "conflict"  # 반대 방향도 성립
    assert _resolve_bucket("conflict", -0.9) == "conflict"  # 이미 강한 부정은 그대로
    assert _resolve_bucket("repeat", 0.05) == "repeat"  # 약한 신호는 관계 타입 유지


def test_1961_regression_label_matches_positive_delta():
    # 원래 버그: overall=86, delta=+8(순증가)인데 woon_state="보고/전달 주의"가 떴었음.
    from core.saju_base import calculate_saju
    import datetime

    saju = calculate_saju(1961, 6, 15, 10, 0, gender="male", is_lunar=False,
                           target_date=datetime.date(2026, 9, 17))
    mod = compute_woon_modifier(saju)
    assert mod["score_delta"] > 0
    assert mod["state_label"] == "명예/승진운"  # "보고/전달 주의" 아님


def test_domain_deltas_are_not_uniform_copy():
    # 관성이 트리거인 케이스 - money/love/work_study가 서로 달라야 한다(예전엔 전부 동일).
    from core.saju_base import calculate_saju
    import datetime

    saju = calculate_saju(1961, 6, 15, 10, 0, gender="male", is_lunar=False,
                           target_date=datetime.date(2026, 9, 17))
    mod = compute_woon_modifier(saju)
    deltas = (mod["money_delta"], mod["love_delta"], mod["work_study_delta"])
    assert len(set(deltas)) > 1  # 최소 하나는 달라야 함(균등 복사 아님)
    for d in deltas:
        assert -40 <= d <= 40


def test_domain_delta_excludes_unrelated_groups():
    from domains.daily.woon_modifier import _domain_delta, DOMAIN_GROUPS, _layer_facts

    # 천간=재성(money·love 공통), 지지=인성(love 전용) 조합 - money와 love가 겹치지 않는
    # 성분(지지·관계)이 있어서 서로 다른 값이 나와야 한다.
    strength = {"verdict": "신강", "yongsin": ["토"], "gisin": [], "heesin": []}
    facts = _layer_facts("甲", "午", "戊子", strength)  # 戊=재성(토=용신), 子=인성(+일지 午와 충)
    layers = {"ilwoon": facts}
    money = _domain_delta(layers, DOMAIN_GROUPS["money"])  # 재성만 해당(천간만)
    love = _domain_delta(layers, DOMAIN_GROUPS["love"])    # 재성(천간)+인성(지지+관계) 둘 다 해당
    assert money != love


def test_build_social_summary_is_pure_lookup_passthrough():
    from domains.daily.social_template import build_social_summary, SOCIAL_TEMPLATES

    assert build_social_summary("관성", "harmony") == SOCIAL_TEMPLATES["관성"]["harmony"]
    assert build_social_summary("존재안함", "harmony") != ""  # 폴백 문구로 대체


def test_today_energy_uses_ilwoon_layer_only_not_overall_trigger():
    # 대운=강한 관성/harmony(가중치 커서 트리거로 뽑힘), 일운=약한 재성 조합.
    # headline은 대운(트리거)을 따르지만 today_energy는 항상 ilwoon만 봐야 한다.
    from domains.daily.woon_modifier import TODAY_ENERGY_TABLE

    mod = compute_woon_modifier(_saju("壬", "寅", daewoon="己丑", sewoon="", ilwoon="乙未"))
    assert mod["trigger_layer"] == "daewoon"
    ilwoon_facts = mod["layers"]["ilwoon"]
    from domains.daily.woon_modifier import _resolve_bucket
    expected_bucket = _resolve_bucket(ilwoon_facts["relation_bucket"], ilwoon_facts["layer_intensity"])
    expected = TODAY_ENERGY_TABLE[ilwoon_facts["group_gan"]][expected_bucket]
    assert mod["today_energy"].startswith(expected)


def test_today_energy_never_equals_headline_table_text():
    """headline·today_energy는 별도 표(HEADLINE_TABLE vs TODAY_ENERGY_TABLE)를 써야 한다 —
    trigger_layer가 ilwoon으로 뽑혀 (group,bucket)이 today_energy와 완전히 같아지는
    경우에도 문장 자체는 겹치면 안 된다(사용자 실측 리포트로 발견된 회귀 방지)."""
    from domains.daily.woon_modifier import HEADLINE_TABLE, TODAY_ENERGY_TABLE

    for group in HEADLINE_TABLE:
        for bucket in HEADLINE_TABLE[group]:
            assert HEADLINE_TABLE[group][bucket] != TODAY_ENERGY_TABLE[group][bucket]


def test_headline_and_today_energy_differ_when_ilwoon_is_overall_trigger():
    # 대운/세운 없이 일운만 주면 trigger_layer가 무조건 ilwoon이 된다 — 이 경우가
    # 사용자가 실제로 겪은 회귀(2026-09-19 등에서 headline == today_energy)다.
    mod = compute_woon_modifier(_saju("壬", "寅", ilwoon="乙未"))
    assert mod["trigger_layer"] == "ilwoon"
    assert mod["headline"] != mod["today_energy"]


def test_headline_uses_ilwoon_signal_not_overall_trigger():
    """headline은 '오늘의 운세'이므로 대운이 트리거로 뽑혀도(가중치가 커서 항상 이김)
    오늘 일진(ilwoon) 신호를 써야 한다 — 안 그러면 대운/세운이 안 바뀌는 며칠 내내
    headline이 고정되는 버그가 생긴다(사용자 실측 리포트로 발견)."""
    from domains.daily.woon_modifier import HEADLINE_TABLE

    mod = compute_woon_modifier(_saju("壬", "寅", daewoon="己丑", sewoon="", ilwoon="乙未"))
    assert mod["trigger_layer"] == "daewoon"  # 트리거 자체는 여전히 대운(레이블/코멘트용)
    ilwoon_facts = mod["layers"]["ilwoon"]
    from domains.daily.woon_modifier import _resolve_bucket
    expected_bucket = _resolve_bucket(ilwoon_facts["relation_bucket"], ilwoon_facts["layer_intensity"])
    expected = HEADLINE_TABLE[ilwoon_facts["group_gan"]][expected_bucket]
    assert mod["headline"] == expected


def test_headline_varies_across_consecutive_days_for_real_birth():
    """실측 리포트: 1983-05-14 14시 여성 기준 2026-09-15~17 headline이 3일 내내 동일한
    문장("돈 씀씀이에 예민해지기 쉬운 날...")으로 나오던 버그의 재현 방지 테스트."""
    import datetime
    from core.saju_base import calculate_saju

    headlines = []
    for d in (15, 16, 17):
        saju = calculate_saju(
            1983, 5, 14, 14, 0, gender="female", is_lunar=False,
            target_date=datetime.date(2026, 9, d),
        )
        mod = compute_woon_modifier(saju)
        headlines.append(mod["headline"])
    assert len(set(headlines)) == 3, headlines


def test_today_energy_differs_between_people_with_different_yongsin():
    # 같은 오늘 일진(乙未)이라도 사람마다 용신/기신이 달라 today_energy가 달라야 한다.
    strength_a = {"verdict": "신약", "yongsin": ["금", "수"], "gisin": ["화", "토"], "heesin": []}
    strength_b = {"verdict": "신강", "yongsin": ["화", "토"], "gisin": ["금", "수"], "heesin": []}
    mod_a = compute_woon_modifier(_saju("壬", "寅", ilwoon="乙未", strength=strength_a))
    mod_b = compute_woon_modifier(_saju("壬", "寅", ilwoon="乙未", strength=strength_b))
    assert mod_a["today_energy"] != mod_b["today_energy"]


def test_today_energy_only_appends_ilwoon_sinsal_not_daewoon_sinsal():
    # 일지 子(申子辰국) 기준 巳=겁살(경고). 대운만 巳를 걸고 일운은 丑(반안살=경고 아님)로 둔다.
    # -> sinsal_hits에 daewoon/겁살은 있어도 today_energy(ilwoon 전용)에는 안 붙어야 한다.
    mod = compute_woon_modifier(_saju("戊", "子", daewoon="丁巳", sewoon="", ilwoon="己丑"))
    daewoon_hits = [h for h in mod["sinsal_hits"] if h["layer"] == "daewoon"]
    assert any(h["name"] == "겁살" for h in daewoon_hits)
    ilwoon_hits = [h for h in mod["sinsal_hits"] if h["layer"] == "ilwoon"]
    assert ilwoon_hits == []
    assert "겁살" not in mod["today_energy"]


def test_relation_bucket_mapping():
    assert _relation_bucket("육합(협력·인연)") == "harmony"
    assert _relation_bucket("충(충돌·이동)") == "conflict"
    assert _relation_bucket("형(마찰·조정)") == "adjustment"
    assert _relation_bucket("파(어긋남)") == "friction"
    assert _relation_bucket("해(방해·구설)") == "friction"
    assert _relation_bucket("복음(같은 지지)") == "repeat"
    assert _relation_bucket("무관") == "neutral"
