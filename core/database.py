import os
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# 프로젝트 루트에 local_saju.db 파일로 SQLite DB 생성
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./local_saju.db")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 1. 일일 운세 캐시 테이블
class DailyFortuneCache(Base):
    __tablename__ = "daily_fortune_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(255), unique=True, index=True)  # user_id + target_date + birth_hash
    fortune_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# 2. 시장 데이터 요약 테이블
class MarketSummary(Base):
    __tablename__ = "market_summary"

    id = Column(Integer, primary_key=True, index=True)
    target_date = Column(String(10), unique=True, index=True)  # YYYY-MM-DD
    summary_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# DB 테이블 자동 생성 함수
def init_db():
    Base.metadata.create_all(bind=engine)

# DB 세션 획득 객체
db_session = SessionLocal()

# 앱 기동 시 테이블 보장 (읽기 전용 FS 등 실패는 조용히 무시하고 런타임에서 폴백)
try:
    init_db()
except Exception as _e:  # pragma: no cover
    print(f"[database] init_db 실패 (런타임 폴백 사용): {_e}")

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")