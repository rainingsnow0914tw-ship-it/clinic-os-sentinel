"""
============================================================
models/patient.py
============================================================
Patient — 病人主檔（Sprint 2 minimal 版）。

只放 mock data 用得到的欄位 + DemoDataMixin。
完整業務欄位（病史、過敏、醫療紀錄...）等 Sprint 2 業務 logic 再補。
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class Patient(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    # 多租戶根 key
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 業務欄位
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 軟刪除狀態
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )

    __table_args__ = (
        CheckConstraint(
            "gender IN ('M', 'F', 'other') OR gender IS NULL",
            name="ck_patients_gender",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_patients_status",
        ),
        Index("ix_patients_clinic_demo", "clinic_id", "is_demo_data"),
        Index("ix_patients_clinic_id", "clinic_id"),
    )
