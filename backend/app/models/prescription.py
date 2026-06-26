"""
============================================================
models/prescription.py
============================================================
Prescription — 處方主檔。

一個 visit 可以有 0 或 1 個 prescription（V1 簡化）。
未來擴展：可能一個 visit 多張處方（看診中分次開藥）。
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class Prescription(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "prescriptions"

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

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 狀態
    # draft → confirmed（醫生簽完）→ dispensed（前台扣完藥）→ voided
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'dispensed', 'voided')",
            name="ck_prescriptions_status",
        ),
        # 一個 visit 最多一張 prescription（V1 設計）
        Index(
            "uq_prescriptions_visit",
            "visit_id",
            unique=True,
            postgresql_where="status != 'voided'",
        ),
        Index("ix_prescriptions_clinic_demo", "clinic_id", "is_demo_data"),
    )
