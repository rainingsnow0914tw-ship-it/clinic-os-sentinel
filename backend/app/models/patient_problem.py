"""
============================================================
models/patient_problem.py -- 心臟表 1: 慢性病 (v3 對齊版)
============================================================
Sentinel 哨兵記憶心臟的「常規背景」表 (A 類)。
存的是當前狀態 + 來歷,一律現在式。

v3 設計變更 (vs v0.1):
- 欄位 name -> problem_name (跟 alembic 0003 對齊)
- 加 icd10_code (alembic 已有)
- source -> problem_source (跟 alembic 對齊)
- 加 DemoDataMixin (跟 jimmy-integrated 業務表家規一致, reset_dev_data 才認得 demo)
- 加 FK clinic_id/patient_id ondelete RESTRICT
- enum 改 String + 應用層 validation (PG enum type 升級痛苦, 模型內保留 enum class 做 validation)

對外 API contract 仍走 schemas/sentinel.py 的 HeartProblem (簡名 name/...)。
ORM <-> schema 雙向 mapper 在 services/heart_layer.py。
============================================================
"""

import uuid
from datetime import date
import enum

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class ControlStatus(str, enum.Enum):
    """慢性病控制狀態 -- 讓 AI 判趨勢。"""

    ACTIVE = "active"            # 主動追蹤中 (alembic default)
    CONTROLLED = "controlled"
    UNSTABLE = "unstable"
    WORSENING = "worsening"
    UNKNOWN = "unknown"
    RESOLVED = "resolved"


class ProblemSource(str, enum.Enum):
    """資料來源 -- 可信度不同。"""

    SELF_REPORT = "self_report"
    VERIFIED = "verified"
    AUTHORITATIVE = "authoritative"
    INFERRED_FROM_VISIT = "inferred_from_visit"   # 從 visit 自動推導 (Phase 5 evolve)


class PatientProblem(Base, TimestampMixin, DemoDataMixin):
    """病人慢性病小檔案 (v3 對齊版)。"""

    __tablename__ = "patient_problems"

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

    problem_name: Mapped[str] = mapped_column(String(200), nullable=False)
    icd10_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    control_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ControlStatus.ACTIVE.value,
        server_default=ControlStatus.ACTIVE.value,
    )
    problem_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=ProblemSource.SELF_REPORT.value,
        server_default=ProblemSource.SELF_REPORT.value,
    )
    diagnosed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<PatientProblem id={self.id} name={self.problem_name} status={self.control_status}>"
