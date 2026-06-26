"""
============================================================
models/patient_problem.py — 心臟表 1:慢性病
============================================================
Sentinel 哨兵記憶心臟的「常規背景」表(A 類)。
存的是當前狀態 + 來歷，一律現在式。

對應 schemas/sentinel.py 的 HeartProblem。
============================================================
"""

import uuid
from datetime import date
from sqlalchemy import String, Text, Date, Uuid, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base, TimestampMixin


class ControlStatus(str, enum.Enum):
    """慢性病控制狀態 — 讓 AI 判趨勢。"""

    CONTROLLED = "controlled"     # 控制中
    UNSTABLE = "unstable"         # 不穩
    WORSENING = "worsening"       # 惡化
    UNKNOWN = "unknown"


class ProblemSource(str, enum.Enum):
    """資料來源 — 可信度不同。"""

    SELF_REPORT = "self_report"           # 病人自述
    VERIFIED = "verified"                 # 醫生查證
    AUTHORITATIVE = "authoritative"       # 權威資料庫


class PatientProblem(Base, TimestampMixin):
    """病人慢性病小檔案。"""

    __tablename__ = "patient_problems"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    # 多租戶 + 病人關聯(沒 FK constraint，比賽 demo 不依賴完整 patients 表)
    clinic_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    # 病名
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 診斷時間
    diagnosed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 控制狀態(讓 AI 判趨勢)
    control_status: Mapped[ControlStatus] = mapped_column(
        SQLEnum(ControlStatus),
        nullable=False,
        default=ControlStatus.UNKNOWN,
    )

    # 來源(可信度不同)
    source: Mapped[ProblemSource] = mapped_column(
        SQLEnum(ProblemSource),
        nullable=False,
        default=ProblemSource.SELF_REPORT,
    )

    # 自由文字筆記(來歷、變化等)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<PatientProblem id={self.id} name={self.name} status={self.control_status}>"
