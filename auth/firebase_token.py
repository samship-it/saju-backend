"""Firebase ID 토큰에서 UID만 꺼낸다.

이 모듈을 import해도 앱은 초기화하지 않는다. 환경변수가 없어도 프로세스 시작은
그대로다. 검증을 호출했을 때만 설정이 있는지 확인한다.
서비스 계정 내용은 코드에 넣지 않고, GOOGLE_APPLICATION_CREDENTIALS 로만 읽는다.
토큰 원문과 비밀값은 로그로 남기지 않는다.
"""

import os

from firebase_admin import auth, get_app, initialize_app
from google.auth.exceptions import DefaultCredentialsError


class FirebaseAuthError(Exception):
    """검증 실패. code만 담고, 토큰 원문은 담지 않는다."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _project_id() -> str:
    return os.environ.get("FIREBASE_PROJECT_ID", "").strip()


def _ensure_app(project_id: str):
    try:
        app = get_app()
    except ValueError:
        try:
            app = initialize_app(options={"projectId": project_id})
        except DefaultCredentialsError:
            raise FirebaseAuthError("FIREBASE_CREDENTIALS_MISSING") from None
    else:
        existing = getattr(app, "project_id", None)
        if existing and existing != project_id:
            raise FirebaseAuthError("FIREBASE_PROJECT_MISMATCH")
    return app


def _wrong_project(exc: Exception) -> bool:
    message = str(exc).lower()
    return "audience" in message or "aud" in message


def verify_firebase_uid(id_token: str) -> str:
    """서명, 만료, 프로젝트를 확인한 뒤 UID를 반환한다."""
    project_id = _project_id()
    if not project_id:
        raise FirebaseAuthError("FIREBASE_NOT_CONFIGURED")

    token = id_token.strip() if isinstance(id_token, str) else ""
    if not token:
        raise FirebaseAuthError("INVALID_TOKEN")

    app = _ensure_app(project_id)
    try:
        claims = auth.verify_id_token(token, app=app)
    except auth.ExpiredIdTokenError:
        raise FirebaseAuthError("EXPIRED_TOKEN") from None
    except auth.RevokedIdTokenError:
        raise FirebaseAuthError("REVOKED_TOKEN") from None
    except auth.InvalidIdTokenError as exc:
        if _wrong_project(exc):
            raise FirebaseAuthError("WRONG_PROJECT") from None
        raise FirebaseAuthError("INVALID_TOKEN") from None
    except auth.CertificateFetchError:
        raise FirebaseAuthError("FIREBASE_UNAVAILABLE") from None
    except Exception:
        raise FirebaseAuthError("INVALID_TOKEN") from None

    if not isinstance(claims, dict):
        raise FirebaseAuthError("INVALID_TOKEN")
    if claims.get("aud") != project_id:
        raise FirebaseAuthError("WRONG_PROJECT")
    uid = claims.get("uid")
    if not isinstance(uid, str) or not uid.strip():
        raise FirebaseAuthError("INVALID_TOKEN")
    return uid.strip()
