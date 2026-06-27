"""
============================================================
models/doctor_watchlist.py -- Phase 7.2 AI 反訓練醫生 watchlist
============================================================
v0.3.1 §8.6 設計: AI 反過來訓練醫生 watchlist 機制。

Mode B 回顧浮現的教育要點, 醫師可選擇「加進我的 watchlist」, 下次新就診
時 banner 提醒。這是 Track 1 MemoryAgent「越用越聰明 + 反向訓練醫生」
narrative 的核心 evidence。

對外 API contract 走 routes/sentinel_watchlist.py.
============================================================
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class DoctorWatchlist(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "doctor_watchlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    doctor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_visit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="SET NULL"),
        nullable=True,
    )

    source_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="hindsight",
        server_default="hindsight",
    )
    pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    lesson_text: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_dismissed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    def __repr__(self) -> str:
        return f"<DoctorWatchlist id={self.id} pattern={self.pattern[:30]!r}>"
