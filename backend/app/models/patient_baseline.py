"""
============================================================
models/patient_baseline.py -- 心臟表 4: 基線 (v3 對齊版)
============================================================
Sentinel 哨兵的「平常什麼樣」基線記錄。

v3 設計變更 (vs v0.1):
- 移除 baseline_type (alembic 沒)
- source -> baseline_source
- recorded_at -> measured_at
- 加 DemoDataMixin + FK
- enum 改 String
============================================================
"""

import uuid
from datetime import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class BaselineCategory(str, enum.Enum):
    """基線類別。"""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    HABIT = "habit"


class BaselineSource(str, enum.Enum):
    AUTO_FROM_VISITS = "auto_from_visits"
    SELF_REPORT = "self_report"
    VERIFIED = "verified"
    CLINICAL = "clinical"   # alembic default


class PatientBaseline(Base, TimestampMixin, DemoDataMixin):
    """病人基線一筆 (v3 對齊版)。"""

    __tablename__ = "patient_baselines"

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
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(String(30), nullable=False)
    baseline_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=BaselineSource.CLINICAL.value,
        server_default=BaselineSource.CLINICAL.value,
    )
    value_text: Mapped[str] = mapped_column(Text, nullable=False)
    measured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<PatientBaseline id={self.id} category={self.category}>"
