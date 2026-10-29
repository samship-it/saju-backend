"""로그인 사용자의 인연 목록.

오늘의 운세가 target_person_id 를 받으면 이 테이블의 생년월일시·성별만 읽는다.
소유자(user_id)와 인연 id 가 둘 다 맞을 때만 반환한다.
"""
from sqlalchemy import Boolean, Column, Integer, String, text

from core.database import Base, SessionLocal, engine, init_db

_partner_cache = {}
_list_cache = {}
_list_version = {}


class UserPartner(Base):
    __tablename__ = "user_partner"

    owner_user_id = Column(String(128), primary_key=True)
    partner_id = Column(String(128), primary_key=True)
    nickname = Column(String(64), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    hour = Column(Integer, nullable=True)
    minute = Column(Integer, nullable=False, default=0)
    gender = Column(String(16), nullable=False, default="female")
    is_lunar = Column(Boolean, nullable=False, default=False)
    love_status = Column(String(32), nullable=True)
    job_status = Column(String(32), nullable=True)


def _ensure_status_columns() -> None:
    from sqlalchemy import inspect

    try:
        cols = {col["name"] for col in inspect(engine).get_columns(UserPartner.__tablename__)}
    except Exception:
        return
    with engine.begin() as conn:
        if "love_status" not in cols:
            conn.execute(text("ALTER TABLE user_partner ADD COLUMN love_status VARCHAR(32)"))
        if "job_status" not in cols:
            conn.execute(text("ALTER TABLE user_partner ADD COLUMN job_status VARCHAR(32)"))


try:
    init_db()
    _ensure_status_columns()
except Exception as _e:  # pragma: no cover
    print(f"[daily.partners] 테이블 생성 실패: {_e}")


def _row_dict(row: UserPartner) -> dict:
    return {
        "owner_user_id": row.owner_user_id,
        "partner_id": row.partner_id,
        "nickname": row.nickname,
        "year": row.year,
        "month": row.month,
        "day": row.day,
        "hour": row.hour,
        "minute": row.minute or 0,
        "gender": row.gender or "female",
        "is_lunar": bool(row.is_lunar),
        "love_status": row.love_status,
        "job_status": row.job_status,
    }


def _key(owner_user_id: str, partner_id: str):
    return (owner_user_id, partner_id)


def _invalidate_list(owner_user_id: str) -> None:
    _list_version[owner_user_id] = _list_version.get(owner_user_id, 0) + 1
    _list_cache.pop(owner_user_id, None)


def _remember_list(owner_user_id: str, version: int, rows: list) -> bool:
    """조회를 시작했을 때의 버전일 때만 캐시에 넣는다. 더 최신 저장이 있으면 버린다."""
    if _list_version.get(owner_user_id, 0) != version:
        return False
    _list_cache[owner_user_id] = (version, rows)
    return True


def partners_of(owner_user_id: str) -> list:
    """이 사용자가 등록한 인연. partner_id 순."""
    version = _list_version.get(owner_user_id, 0)
    cached = _list_cache.get(owner_user_id)
    if cached is not None and cached[0] == version:
        return list(cached[1])
    session = SessionLocal()
    try:
        rows = (
            session.query(UserPartner)
            .filter(UserPartner.owner_user_id == owner_user_id)
            .order_by(UserPartner.partner_id.asc())
            .all()
        )
        found = [_row_dict(row) for row in rows]
    finally:
        session.close()
    _remember_list(owner_user_id, version, found)
    return list(found)


def partner_of(owner_user_id: str, partner_id: str):
    """등록된 인연. 없거나 다른 사용자 소유면 None."""
    key = _key(owner_user_id, partner_id)
    if key in _partner_cache:
        return _partner_cache[key]
    session = SessionLocal()
    try:
        row = (
            session.query(UserPartner)
            .filter(
                UserPartner.owner_user_id == owner_user_id,
                UserPartner.partner_id == partner_id,
            )
            .one_or_none()
        )
        found = _row_dict(row) if row else None
    finally:
        session.close()
    _partner_cache[key] = found
    return found


def upsert_partner(
    owner_user_id: str, partner_id: str, *, nickname: str,
    year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    love_status=None, job_status=None,
) -> dict:
    session = SessionLocal()
    try:
        row = (
            session.query(UserPartner)
            .filter(
                UserPartner.owner_user_id == owner_user_id,
                UserPartner.partner_id == partner_id,
            )
            .one_or_none()
        )
        if row is None:
            row = UserPartner(owner_user_id=owner_user_id, partner_id=partner_id)
            session.add(row)
        row.nickname = nickname
        row.year = int(year)
        row.month = int(month)
        row.day = int(day)
        row.hour = None if hour is None else int(hour)
        row.minute = int(minute or 0)
        row.gender = gender or "female"
        row.is_lunar = bool(is_lunar)
        if love_status:
            row.love_status = love_status
        if job_status:
            row.job_status = job_status
        session.commit()
        session.refresh(row)
        found = _row_dict(row)
        _partner_cache[_key(owner_user_id, partner_id)] = found
        _invalidate_list(owner_user_id)
        return found
    finally:
        session.close()


def delete_partner(owner_user_id: str, partner_id: str) -> None:
    session = SessionLocal()
    try:
        session.query(UserPartner).filter(
            UserPartner.owner_user_id == owner_user_id,
            UserPartner.partner_id == partner_id,
        ).delete()
        session.commit()
    finally:
        session.close()
    _partner_cache.pop(_key(owner_user_id, partner_id), None)
    _invalidate_list(owner_user_id)
