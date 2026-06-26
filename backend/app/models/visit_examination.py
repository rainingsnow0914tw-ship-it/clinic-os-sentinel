"""
============================================================
models/visit_examination.py -- 結構化檢查數據 (v0.3 新增)
============================================================
對應 v0.3.1 設計 §6: visit 內的檢查資料 (跟 visit 1:1)
- vital_signs_json: VitalSigns dict (BP, HR, T, RR, SpO2)
- lab_results_json: list[LabResult] (WBC / Hb / CRP / HbA1c ...)
- xray_findings:    radiology 文字描述
- ecg_findings:     心電圖文字描述
- free_notes:       自由文字補充

4 agent 透過 ContextPack 拿到結構化檢查數據,audit agent 可
推理「BP 高 + 開 NSAID = 拮抗降壓藥」這種情境風險。
============================================================
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class VisitExamination(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "visit_examinations"

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
        unique=True,  # 1:1 with visit
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 4 大類結構化 + 2 個自由文字
    vital_signs_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    lab_results_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    xray_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    ecg_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    free_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<VisitExamination id={self.id} visit_id={self.visit_id}>"
