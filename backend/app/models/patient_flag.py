"""
============================================================
models/patient_flag.py -- 心臟表 3: 警訊紅旗 (v3 對齊版)
============================================================
Sentinel 哨兵的核心差異化資產 -- 結構化「會亮燈」的病人紅旗。

五類紅旗 x 三時態:
- 過敏 (permanent) -- 後閘門必撞
- 懷孕/哺乳 (temporary) -- 帶日期會過期
- 重大病史 (permanent) -- 中風後遺等
- 醫療指示 (permanent) -- DNR 等
- 醫病互動註記 (permanent, 禁主觀)
- 來源地/居住背景 (dormant) -- 特定線索喚醒

v3 設計變更 (vs v0.1):
- source -> flag_source (跟 alembic 0003 對齊)
- 加 DemoDataMixin + FK clinic_id/patient_id
- enum 改 String + 應用層 validation
- 保留 v0.3.1 §7.3 新欄位: confidence_status / first/confirmed_at_visit

對外 API contract 仍是 schemas/sentinel.py 的 HeartFlag (簡名 type)。
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


class FlagType(str, enum.Enum):
    """紅旗類型 -- 5 + 1 類。"""

    ALLERGY = "allergy"
    PREGNANCY = "pregnancy"
    MAJOR_HISTORY = "major_history"
    MEDICAL_DIRECTIVE = "medical_directive"
    INTERACTION_NOTE = "interaction_note"
    ORIGIN = "origin"


class FlagTemporalMode(str, enum.Enum):
    """時態 -- 影響哨兵怎麼喚醒這條紅旗。"""

    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    DORMANT = "dormant"


class FlagSeverity(str, enum.Enum):
    """嚴重度 -- 影響後閘門 agent 亮哪種色。"""

    RED = "red"
    YELLOW = "yellow"
    INFO = "info"


class FlagSource(str, enum.Enum):
    SELF_REPORT = "self_report"
    VERIFIED = "verified"
    AUTHORITATIVE = "authoritative"
    INFERRED_FROM_VISIT = "inferred_from_visit"   # Phase 5 evolve 用


class ConfidenceStatus(str, enum.Enum):
    """v0.3.1 §7.3 -- 單次 anomaly 升級狀態。"""

    TO_OBSERVE = "to_observe"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class PatientFlag(Base, TimestampMixin, DemoDataMixin):
    """病人警訊紅旗 (會亮燈, v3 對齊版)。"""

    __tablename__ = "patient_flags"

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

    flag_type: Mapped[str] = mapped_column(String(30), nullable=False)
    temporal_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FlagTemporalMode.PERMANENT.value,
        server_default=FlagTemporalMode.PERMANENT.value,
    )
    severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    flag_source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=FlagSource.SELF_REPORT.value,
        server_default=FlagSource.SELF_REPORT.value,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    wake_trigger: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- v0.3.1 §7.3 ----
    confidence_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ConfidenceStatus.TO_OBSERVE.value,
        server_default=ConfidenceStatus.TO_OBSERVE.value,
    )
    first_observed_at_visit: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmed_at_visit: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<PatientFlag id={self.id} type={self.flag_type} status={self.confidence_status}>"
