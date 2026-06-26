"""
============================================================
models/patient_medication.py -- 心臟表 2: 長期用藥 (v3 對齊版)
============================================================
Sentinel 哨兵記憶心臟的長期用藥獨立表。

v3 設計變更 (vs v0.1):
- name -> medication_name (跟 alembic 0003 對齊)
- source -> medication_source
- 加 dosage / frequency / is_active (alembic 已有)
- 移除 for_problem_id / composition_certain (alembic 沒)
- 加 DemoDataMixin + FK
- enum 改 String

對外 API contract 仍是 schemas/sentinel.py 的 HeartMedication (簡名 name)。
============================================================
"""

import uuid
import enum

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class MedicationCategory(str, enum.Enum):
    """藥物類別 -- 影響規則引擎處理方式。"""

    LONG_TERM = "long_term"                       # alembic default
    CHRONIC_DISEASE_MED = "chronic_disease_med"
    SHORT_TERM = "short_term"
    PRN = "prn"
    SUPPLEMENT = "supplement"
    TCM = "tcm"


class MedicationSource(str, enum.Enum):
    SELF_REPORT = "self_report"
    VERIFIED = "verified"
    AUTHORITATIVE = "authoritative"
    INFERRED_FROM_VISIT = "inferred_from_visit"


class PatientMedication(Base, TimestampMixin, DemoDataMixin):
    """病人長期用藥 (v3 對齊版)。"""

    __tablename__ = "patient_medications"

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

    medication_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MedicationCategory.LONG_TERM.value,
        server_default=MedicationCategory.LONG_TERM.value,
    )
    dosage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    medication_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MedicationSource.SELF_REPORT.value,
        server_default=MedicationSource.SELF_REPORT.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<PatientMedication id={self.id} name={self.medication_name} cat={self.category}>"
