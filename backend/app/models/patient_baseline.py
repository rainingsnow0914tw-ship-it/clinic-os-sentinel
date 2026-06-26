"""
============================================================
models/patient_baseline.py — 心臟表 4:基線
============================================================
Sentinel 哨兵的「平常什麼樣」基線記錄。

兩類：
- 客觀基線：由 visits 歷史自動算趨勢(例：平常血壓 130/80)
- 主觀症狀：症狀 > 2 週時入口 agent 提醒問

簡化 V1：每筆 baseline 一個 type + value，AI 接需要時自行 query。

對應 schemas/sentinel.py 沒專屬 schema(用 dict 帶過去)。
============================================================
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Uuid, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base, TimestampMixin


class BaselineCategory(str, enum.Enum):
    """基線類別。"""

    OBJECTIVE = "objective"     # 客觀(血壓、體重、HbA1c)
    SUBJECTIVE = "subjective"   # 主觀(疲倦感、睡眠品質)
    HABIT = "habit"             # 生活習慣(飲食、運動、抽菸喝酒)


class BaselineSource(str, enum.Enum):
    AUTO_FROM_VISITS = "auto_from_visits"   # 由 visits 歷史自動算
    SELF_REPORT = "self_report"
    VERIFIED = "verified"


class PatientBaseline(Base, TimestampMixin):
    """病人基線一筆。"""

    __tablename__ = "patient_baselines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    category: Mapped[BaselineCategory] = mapped_column(SQLEnum(BaselineCategory), nullable=False)

    # 基線類型(自由字串，例: "blood_pressure" / "fatigue_level" / "diet_pattern")
    baseline_type: Mapped[str] = mapped_column(String(80), nullable=False)

    # 值(自由字串，例: "130/80 mmHg" / "輕度疲倦" / "愛吃煎炸")
    value_text: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped[BaselineSource] = mapped_column(
        SQLEnum(BaselineSource),
        nullable=False,
        default=BaselineSource.SELF_REPORT,
    )

    # 記錄時間點(可空，未填代表「最近狀態」)
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<PatientBaseline id={self.id} type={self.baseline_type}>"
