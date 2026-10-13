"""로그인 사용자 사주 프로필과 복콩 잔액.

이상형 인연 API는 출생 폼을 받지 않고 이 테이블만 읽는다.
잔액 차감은 UPDATE ... WHERE bokkong >= cost 한 문으로 처리한다.
"""
import os

from sqlalchemy import Boolean, Column, Integer, String, text

from core.database import Base, SessionLocal, engine, init_db

DEFAULT_BOKKONG = 30

# 출생 정보는 잔액과 달리 요청마다 안 바뀐다. 복콩은 항상 DB에서 차감한다.
_birth_cache = {}


class UserSajuProfile(Base):
    __tablename__ = "user_saju_profile"

    user_id = Column(String(128), primary_key=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    hour = Column(Integer, nullable=True)
    minute = Column(Integer, nullable=False, default=0)
    gender = Column(String(16), nullable=False, default="female")
    is_lunar = Column(Boolean, nullable=False, default=False)
    bokkong = Column(Integer, nullable=False, default=DEFAULT_BOKKONG)


try:
    init_db()
except Exception as _e:  # pragma: no cover
    print(f"[love.profiles] 테이블 생성 실패: {_e}")


def ideal_partner_cost() -> int:
    raw = os.environ.get("IDEAL_PARTNER_COST", "30")
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 30


def _row_dict(row: UserSajuProfile) -> dict:
    return {
        "user_id": row.user_id,
        "year": row.year,
        "month": row.month,
        "day": row.day,
        "hour": row.hour,
        "minute": row.minute or 0,
        "gender": row.gender or "female",
        "is_lunar": bool(row.is_lunar),
        "bokkong": int(row.bokkong or 0),
    }


def _forget(user_id: str) -> None:
    _birth_cache.pop(user_id, None)


def birth_of(user_id: str):
    """사주 계산에 쓰는 출생 정보. 잔액은 믿지 않는다."""
    if user_id in _birth_cache:
        return _birth_cache[user_id]
    session = SessionLocal()
    try:
        row = session.query(UserSajuProfile).filter(UserSajuProfile.user_id == user_id).one_or_none()
        found = _row_dict(row) if row else None
    finally:
        session.close()
    _birth_cache[user_id] = found
    return found


def get_profile(user_id: str):
    """잔액까지 포함한 최신 프로필."""
    session = SessionLocal()
    try:
        row = session.query(UserSajuProfile).filter(UserSajuProfile.user_id == user_id).one_or_none()
        found = _row_dict(row) if row else None
    finally:
        session.close()
    _birth_cache[user_id] = found
    return found


def upsert_profile(
    user_id: str, *, year: int, month: int, day: int,
    hour=None, minute: int = 0, gender: str = "female", is_lunar: bool = False,
    bokkong=None,
) -> dict:
    """출생 정보를 저장한다. bokkong 가 None 이면 기존 잔액을 유지하고, 신규는 30으로 시작한다."""
    session = SessionLocal()
    try:
        row = session.query(UserSajuProfile).filter(UserSajuProfile.user_id == user_id).one_or_none()
        if row is None:
            row = UserSajuProfile(
                user_id=user_id,
                bokkong=DEFAULT_BOKKONG if bokkong is None else int(bokkong),
            )
            session.add(row)
        elif bokkong is not None:
            row.bokkong = int(bokkong)
        row.year = int(year)
        row.month = int(month)
        row.day = int(day)
        row.hour = None if hour is None else int(hour)
        row.minute = int(minute or 0)
        row.gender = gender or "female"
        row.is_lunar = bool(is_lunar)
        session.commit()
        session.refresh(row)
        found = _row_dict(row)
        _birth_cache[user_id] = found
        return found
    finally:
        session.close()


def deduct_bokkong(user_id: str, cost: int):
    """성공 시 ('ok', 남은 잔액). 프로필 없음 ('missing', None). 잔액 부족 ('insufficient', 현재 잔액)."""
    with engine.begin() as conn:
        if cost <= 0:
            row = conn.execute(
                text("SELECT bokkong FROM user_saju_profile WHERE user_id = :u"),
                {"u": user_id},
            ).first()
            if row is None:
                return "missing", None
            return "ok", int(row[0] or 0)

        row = conn.execute(
            text(
                "UPDATE user_saju_profile SET bokkong = bokkong - :c "
                "WHERE user_id = :u AND bokkong >= :c RETURNING bokkong"
            ),
            {"u": user_id, "c": cost},
        ).first()
        if row is not None:
            return "ok", int(row[0] or 0)

        current = conn.execute(
            text("SELECT bokkong FROM user_saju_profile WHERE user_id = :u"),
            {"u": user_id},
        ).first()
        if current is None:
            return "missing", None
        return "insufficient", int(current[0] or 0)


def delete_profile(user_id: str) -> None:
    session = SessionLocal()
    try:
        session.query(UserSajuProfile).filter(UserSajuProfile.user_id == user_id).delete()
        session.commit()
        _forget(user_id)
    finally:
        session.close()
