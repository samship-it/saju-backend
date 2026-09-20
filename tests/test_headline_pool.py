"""domains/daily/headline_pool.py — 사전 생성 대형 풀(셀당 다수 변형) 로테이션 검증.

실제 headline_pool.json/today_energy_pool.json 파일에는 의존하지 않는다(생성 전에도
테스트가 통과해야 한다) — 모듈의 인메모리 캐시(_headline_cache/_energy_cache)를 직접
주입해서 순수하게 로테이션·폴백 로직만 검증한다.
"""
import pytest

from domains.daily import headline_pool


@pytest.fixture(autouse=True)
def _isolate_cache(monkeypatch):
    monkeypatch.setattr(headline_pool, "_headline_cache", None, raising=False)
    monkeypatch.setattr(headline_pool, "_energy_cache", None, raising=False)
    yield


def test_pick_headline_none_when_cell_missing(monkeypatch):
    monkeypatch.setattr(headline_pool, "_headline_cache", {}, raising=False)
    assert headline_pool.pick_headline("비견", "harmony", 0) is None


def test_pick_headline_none_when_sipsin_or_bucket_missing(monkeypatch):
    monkeypatch.setattr(
        headline_pool, "_headline_cache", {"비견_harmony": {"variants": ["a"]}}, raising=False
    )
    assert headline_pool.pick_headline(None, "harmony", 0) is None
    assert headline_pool.pick_headline("비견", None, 0) is None


def test_pick_headline_none_when_entry_malformed(monkeypatch):
    monkeypatch.setattr(
        headline_pool, "_headline_cache",
        {"비견_harmony": {"variants": []}, "겁재_harmony": "이상한 값"}, raising=False,
    )
    assert headline_pool.pick_headline("비견", "harmony", 0) is None
    assert headline_pool.pick_headline("겁재", "harmony", 0) is None


def test_pick_headline_rotates_by_day_ordinal_and_wraps(monkeypatch):
    variants = ["문장A", "문장B", "문장C"]
    monkeypatch.setattr(
        headline_pool, "_headline_cache", {"비견_harmony": {"variants": variants}}, raising=False
    )
    assert headline_pool.pick_headline("비견", "harmony", 0) == "문장A"
    assert headline_pool.pick_headline("비견", "harmony", 1) == "문장B"
    assert headline_pool.pick_headline("비견", "harmony", 2) == "문장C"
    assert headline_pool.pick_headline("비견", "harmony", 3) == "문장A"  # 3개 주기로 순환
    assert headline_pool.pick_headline("비견", "harmony", 100) == variants[100 % 3]


def test_pick_headline_and_today_energy_use_independent_pools(monkeypatch):
    monkeypatch.setattr(
        headline_pool, "_headline_cache", {"비견_harmony": {"variants": ["H"]}}, raising=False
    )
    monkeypatch.setattr(
        headline_pool, "_energy_cache", {"비견_harmony": {"variants": ["E"]}}, raising=False
    )
    assert headline_pool.pick_headline("비견", "harmony", 0) == "H"
    assert headline_pool.pick_today_energy("비견", "harmony", 0) == "E"


def test_load_headline_pool_missing_file_returns_empty_dict():
    # 아직 생성 전(headline_pool.json 없음)이어도 예외 없이 빈 dict — 호출자가 폴백한다.
    result = headline_pool._read_json("/no/such/path/headline_pool.json")
    assert result == {}


def test_stats_reports_expected_cell_count(monkeypatch):
    monkeypatch.setattr(
        headline_pool, "_headline_cache",
        {f"비견_{b}": {"variants": ["a", "b"]} for b in ("harmony", "conflict")}, raising=False,
    )
    monkeypatch.setattr(headline_pool, "_energy_cache", {}, raising=False)
    s = headline_pool.stats()
    assert s["headline_pool"]["cells"] == 2
    assert s["headline_pool"]["total_variants"] == 4
    assert s["headline_pool"]["min_variants_per_cell"] == 2
    assert s["today_energy_pool"]["cells"] == 0
