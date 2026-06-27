"""
============================================================
models/visit.py
============================================================
Visit — 看診紀錄（minimal 版）。

完整版會有：主訴、診斷、SOAP 病歷、ICD-10 等。
這版只放 mock data 必要欄位 + 狀態。

狀態流：draft → in_progress → completed → invoiced
        completed 可被 voided（但通常是 invoice 被 voided 帶動）
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class Visit(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "visits"

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

    # 看診醫生
    doctor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    visit_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 主訴 / 診斷（minimal — 之後 Sprint 2 會拆更細）
    chief_complaint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # v0.3 Phase 2.4c (司機示範真實診所病歷補上)
    hpi: Mapped[str | None] = mapped_column(Text, nullable=True)              # 現病史 / Brief History
    physical_exam: Mapped[str | None] = mapped_column(Text, nullable=True)    # 查體 PE 醫師發現

    # 狀態
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'completed', 'invoiced', 'voided')",
            name="ck_visits_status",
        ),
        Index("ix_visits_clinic_patient", "clinic_id", "patient_id"),
        Index("ix_visits_clinic_demo", "clinic_id", "is_demo_data"),
    )
