"""
ORM 基底類別

所有 model 都繼承 Base，並在需要時 mixin TimestampMixin
（V1 預設所有業務 table 都需要 created_at / updated_at）
"""

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    所有 ORM model 的共同祖先
    使用 SQLAlchemy 2.0 的 DeclarativeBase 寫法
    """
    pass


class TimestampMixin:
    """
    時間戳 mixin

    - created_at: insert 時由 PostgreSQL 自動填入 NOW()
    - updated_at: insert / update 時由 PostgreSQL 自動更新 NOW()

    用 server_default + onupdate 雙保險，讓資料庫端而不是應用端負責時間戳
    這樣就算之後換語言/換服務寫資料也能保證一致
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
