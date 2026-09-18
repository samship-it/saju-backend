"""오늘의 운세 — 애정 상태(love_status)/직업 상태(job_status) 분기 검증.

정적 표 완결성(status_variants.py) + 서비스 계층 통합(generate_daily_fortune)을 함께
검증한다. 실제 Gemini 호출 없음.
"""
import pytest

from domains.daily.status_variants import (
    JOB_STATUS_TEMPLATES,
    JOB_STATUSES,
    LOVE_STATUSES,
    MARRIED_LOVE_TEMPLATES,
    resolve_job_levelup,
    resolve_married_love,
)
from domains.daily.service import generate_daily_fortune

_BUCKETS = {"harmony", "conflict", "adjustment", "friction", "repeat", "neutral"}


# ------------------------------------------------------------------ 정적 표 완결성
def test_married_love_templates_cover_every_bucket():
    assert set(MARRIED_LOVE_TEMPLATES.keys()) == _BUCKETS
    for text in MARRIED_LOVE_TEMPLATES.values():
        assert isinstance(text, str) and text


def test_job_status_templates_cover_every_status_and_bucket():
    assert set(JOB_STATUS_TEMPLATES.keys()) == set(JOB_STATUSES)
    for status in JOB_STATUSES:
        assert set(JOB_STATUS_TEMPLATES[status].keys()) == _BUCKETS
        for text in JOB_STATUS_TEMPLATES[status].values():
            assert isinstance(text, str) and text


def test_resolve_married_love_picks_bucket_text():
    assert resolve_married_love("harmony") == MARRIED_LOVE_TEMPLATES["harmony"]


def test_resolve_married_love_falls_back_on_unknown_bucket():
    text = resolve_married_love(None)
    assert isinstance(text, str) and text
    assert resolve_married_love("no-such-bucket") == text


def test_resolve_job_levelup_picks_status_bucket_text():
    assert resolve_job_levelup("employee", "harmony") == JOB_STATUS_TEMPLATES["employee"]["harmony"]
    assert resolve_job_levelup("student", "conflict") == JOB_STATUS_TEMPLATES["student"]["conflict"]


def test_resolve_job_levelup_returns_none_for_unknown_status():
    assert resolve_job_levelup(None, "harmony") is None
    assert resolve_job_levelup("not-a-status", "harmony") is None


# ------------------------------------------------------------------ 서비스 계층 통합(generate_daily_fortune)
_BIRTH = dict(year=1990, month=5, day=15, hour=10, minute=0, gender="female", is_lunar=False)


def _saju_for_test():
    from core.saju_base import calculate_saju
    import datetime
    return calculate_saju(**_BIRTH, target_date=datetime.date(2026, 6, 1))


@pytest.mark.parametrize("love_status", list(LOVE_STATUSES))
def test_generate_daily_fortune_love_status_populates_summary_love(love_status):
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju, love_status=love_status)
    assert data["love_status"] == love_status
    assert data["summary"]["love"]


def test_generate_daily_fortune_love_solo_matches_love_single():
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju, love_status="solo")
    assert data["summary"]["love"] == data["summary"]["love_single"]


def test_generate_daily_fortune_love_in_relationship_matches_love_couple():
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju, love_status="in_relationship")
    assert data["summary"]["love"] == data["summary"]["love_couple"]


def test_generate_daily_fortune_love_married_uses_married_templates():
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju, love_status="married")
    assert data["summary"]["love"] in set(MARRIED_LOVE_TEMPLATES.values()) or data["summary"]["love"]
    assert data["summary"]["love"] != data["summary"]["love_single"]
    assert data["summary"]["love"] != data["summary"]["love_couple"]


def test_generate_daily_fortune_no_love_status_falls_back_to_joined_legacy_text():
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju)
    assert data["love_status"] is None
    single = data["summary"]["love_single"]
    couple = data["summary"]["love_couple"]
    assert single in data["summary"]["love"]
    assert couple in data["summary"]["love"]


def test_generate_daily_fortune_unknown_love_status_falls_back_like_missing():
    saju = _saju_for_test()
    data_unknown, _ = generate_daily_fortune(saju, love_status="not-a-status")
    data_missing, _ = generate_daily_fortune(saju)
    assert data_unknown["love_status"] is None
    assert data_unknown["summary"]["love"] == data_missing["summary"]["love"]


@pytest.mark.parametrize("job_status", list(JOB_STATUSES))
def test_generate_daily_fortune_job_status_populates_summary_job_levelup(job_status):
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju, job_status=job_status)
    assert data["job_status"] == job_status
    assert data["summary"]["job_levelup"]
    assert data["summary"]["job_levelup"] != data["summary"]["work_study"]


def test_generate_daily_fortune_no_job_status_falls_back_to_work_study():
    saju = _saju_for_test()
    data, _ = generate_daily_fortune(saju)
    assert data["job_status"] is None
    assert data["summary"]["job_levelup"] == data["summary"]["work_study"]


def test_generate_daily_fortune_unknown_job_status_falls_back_like_missing():
    saju = _saju_for_test()
    data_unknown, _ = generate_daily_fortune(saju, job_status="not-a-status")
    data_missing, _ = generate_daily_fortune(saju)
    assert data_unknown["job_status"] is None
    assert data_unknown["summary"]["job_levelup"] == data_missing["summary"]["job_levelup"]


def test_generate_daily_fortune_existing_fields_unchanged_by_status_params():
    """love_status/job_status를 줘도 기존 필드(love_single/love_couple/work_study 등)는
    그대로 유지돼야 한다(기존 클라이언트 호환 — 새 필드는 추가만 됨)."""
    saju = _saju_for_test()
    baseline, _ = generate_daily_fortune(saju)
    with_status, _ = generate_daily_fortune(saju, love_status="married", job_status="student")
    for key in ("love_single", "love_couple", "work_study", "money", "overall"):
        assert baseline["summary"][key] == with_status["summary"][key]
