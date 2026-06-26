"""
============================================================
core/database.py
============================================================
SQLAlchemy 資料庫連線管理。

設計原則：
- 用 SQLAlchemy 2.0 風格（不是舊的 1.4 ORM）
- 每個 request 有自己的 session（FastAPI Depends 處理 lifecycle）
- 用 begin() context manager 確保 transaction 正確 commit/rollback
- 連線池設定從 settings 讀
============================================================
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings


# ============================================================
# Engine
# ============================================================
# create_engine 是 connection pool 的工廠
# pool_pre_ping=True：每次借連線前先 ping 一下（避免拿到斷掉的連線）
# pool_recycle=300：連線最多用 5 分鐘就 recycle（避免 Cloud SQL 那邊砍連線）
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.APP_ENV == "development",  # 開發時印 SQL，方便 debug
)


# ============================================================
# Session Factory
# ============================================================
# autocommit / autoflush 都關掉，讓我們自己控制 transaction 邊界
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # commit 後物件不要 expire（前端常常還要讀）
)


# ============================================================
# Base：所有 ORM model 繼承這個
# ============================================================
class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base。所有 model class 繼承這個。"""
    pass


# ============================================================
# FastAPI Dependency
# ============================================================
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 的 dependency injection 用。
    用法：
        @app.get("/...")
        def handler(db: Session = Depends(get_db)):
            ...

    保證 request 結束時 session 一定會 close。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
