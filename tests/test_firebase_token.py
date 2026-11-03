"""Firebase ID 토큰 검증. Admin SDK 네트워크는 호출하지 않는다."""

import pytest
from firebase_admin import auth

from auth.firebase_token import FirebaseAuthError, verify_firebase_uid

PROJECT = "bokkong-test"
UID = "uid-verified"
TOKEN = "header.payload.signature"


def _configured(monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", PROJECT)
    monkeypatch.setattr("auth.firebase_token._ensure_app", lambda project_id: object())


def _raise(monkeypatch, exc: Exception):
    def boom(token, app=None, check_revoked=False, clock_skew_seconds=0):
        raise exc

    monkeypatch.setattr("auth.firebase_token.auth.verify_id_token", boom)


def test_valid_token_returns_uid(monkeypatch):
    _configured(monkeypatch)

    def ok(token, app=None, check_revoked=False, clock_skew_seconds=0):
        assert token == TOKEN
        return {"uid": UID, "aud": PROJECT}

    monkeypatch.setattr("auth.firebase_token.auth.verify_id_token", ok)
    assert verify_firebase_uid(TOKEN) == UID


def test_invalid_token_is_rejected(monkeypatch):
    _configured(monkeypatch)
    _raise(monkeypatch, auth.InvalidIdTokenError("malformed", cause=ValueError("bad")))
    with pytest.raises(FirebaseAuthError) as caught:
        verify_firebase_uid(TOKEN)
    assert caught.value.code == "INVALID_TOKEN"
    assert TOKEN not in str(caught.value)


def test_expired_token_is_rejected(monkeypatch):
    _configured(monkeypatch)
    _raise(monkeypatch, auth.ExpiredIdTokenError("expired", cause=ValueError("exp")))
    with pytest.raises(FirebaseAuthError) as caught:
        verify_firebase_uid(TOKEN)
    assert caught.value.code == "EXPIRED_TOKEN"
    assert TOKEN not in str(caught.value)


def test_other_project_claim_is_rejected(monkeypatch):
    _configured(monkeypatch)

    def other(token, app=None, check_revoked=False, clock_skew_seconds=0):
        return {"uid": UID, "aud": "other-project"}

    monkeypatch.setattr("auth.firebase_token.auth.verify_id_token", other)
    with pytest.raises(FirebaseAuthError) as caught:
        verify_firebase_uid(TOKEN)
    assert caught.value.code == "WRONG_PROJECT"


def test_audience_error_from_sdk_is_wrong_project(monkeypatch):
    _configured(monkeypatch)
    _raise(
        monkeypatch,
        auth.InvalidIdTokenError(
            f'Firebase ID token has incorrect "aud" claim. Token {TOKEN}',
            cause=ValueError("aud"),
        ),
    )
    with pytest.raises(FirebaseAuthError) as caught:
        verify_firebase_uid(TOKEN)
    assert caught.value.code == "WRONG_PROJECT"
    assert TOKEN not in str(caught.value)
    assert TOKEN not in caught.value.code


def test_missing_firebase_config_fails_before_verification(monkeypatch):
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    called = {"n": 0}

    def boom(token, app=None, check_revoked=False, clock_skew_seconds=0):
        called["n"] += 1
        raise AssertionError("verify should not run")

    monkeypatch.setattr("auth.firebase_token.auth.verify_id_token", boom)
    with pytest.raises(FirebaseAuthError) as caught:
        verify_firebase_uid(TOKEN)
    assert caught.value.code == "FIREBASE_NOT_CONFIGURED"
    assert called["n"] == 0
    assert TOKEN not in str(caught.value)


def test_missing_credentials_is_a_config_error(monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", PROJECT)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    def no_app():
        raise ValueError("The default Firebase app does not exist")

    def no_creds(*args, **kwargs):
        raise DefaultCredentialsError("missing")

    from google.auth.exceptions import DefaultCredentialsError

    monkeypatch.setattr("auth.firebase_token.get_app", no_app)
    monkeypatch.setattr("auth.firebase_token.initialize_app", no_creds)
    with pytest.raises(FirebaseAuthError) as caught:
        verify_firebase_uid(TOKEN)
    assert caught.value.code == "FIREBASE_CREDENTIALS_MISSING"
    assert TOKEN not in str(caught.value)


def test_import_does_not_initialize_firebase():
    import firebase_admin

    import auth.firebase_token  # noqa: F401

    assert firebase_admin._apps == {}
