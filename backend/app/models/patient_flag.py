"""
============================================================
models/patient_flag.py — 心臟表 3:警訊紅旗
============================================================
Sentinel 哨兵的核心差異化資產 —— 結構化「會亮燈」的病人紅旗。

五類紅旗 × 三時態：
- 過敏(permanent) — 後閘門必撞
- 懷孕/哺乳(temporary) — 帶日期會過期
- 重大病史(permanent) — 中風後遺等
- 醫療指示(permanent) — DNR 等
- 醫病互動註記(permanent，禁主觀)
- 來源地/居住背景(dormant) — 特定線索喚醒

對應 schemas/sentinel.py 的 HeartFlag。
============================================================
"""

import uuid
from datetime import date
from sqlalchemy import String, Text, Date, Uuid, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base, TimestampMixin


class ConfidenceStatus(str, enum.Enum):
    """v0.3.1 §7.3 -- 單次 anomaly 升級狀態,避免單次觀察直接標永久紅旗。"""

    TO_OBSERVE = "to_observe"   # 第 1 次出現,待觀察 (UI 顯示淡色)
    CONFIRMED = "confirmed"     # 第 2 次以上確認 (UI 顯示亮紅)
    DISMISSED = "dismissed"     # 醫生手動關掉


class FlagType(str, enum.Enum):
    """紅旗類型 — 5 + 1 類。"""

    ALLERGY = "allergy"                         # 過敏
    PREGNANCY = "pregnancy"                     # 懷孕/哺乳
    MAJOR_HISTORY = "major_history"             # 重大病史(中風、手術)
    MEDICAL_DIRECTIVE = "medical_directive"     # 醫療指示(DNR)
    INTERACTION_NOTE = "interaction_note"       # 醫病互動註記(只記客觀)
    ORIGIN = "origin"                           # 來源地/居住背景(沉睡)


class FlagTemporalMode(str, enum.Enum):
    """時態 — 影響哨兵怎麼喚醒這條紅旗。"""

    PERMANENT = "permanent"     # 永久
    TEMPORARY = "temporary"     # 時效(會過期，看 valid_until)
    DORMANT = "dormant"         # 沉睡(看 wake_trigger)


class FlagSeverity(str, enum.Enum):
    """嚴重度 — 影響後閘門 agent 亮哪種色。"""

    RED = "red"
    YELLOW = "yellow"
    INFO = "info"


class FlagSource(str, enum.Enum):
    SELF_REPORT = "self_report"
    VERIFIED = "verified"
    AUTHORITATIVE = "authoritative"


class PatientFlag(Base, TimestampMixin):
    """病人警訊紅旗(會亮燈)。"""

    __tablename__ = "patient_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    flag_type: Mapped[FlagType] = mapped_column(SQLEnum(FlagType), nullable=False)
    temporal_mode: Mapped[FlagTemporalMode] = mapped_column(
        SQLEnum(FlagTemporalMode),
        nullable=False,
        default=FlagTemporalMode.PERMANENT,
    )
    severity: Mapped[FlagSeverity | None] = mapped_column(SQLEnum(FlagSeverity), nullable=True)
    source: Mapped[FlagSource] = mapped_column(
        SQLEnum(FlagSource),
        nullable=False,
        default=FlagSource.SELF_REPORT,
    )

    # 內容(互動註記只存客觀事實)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 時效型用
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 沉睡型喚醒線索(例如「東南亞旅遊」需要某症狀觸發才喚醒)
    wake_trigger: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 自由筆記
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- v0.3.1 §7.3 新增:單次 anomaly 升級邏輯 ----
    # to_observe (第1次) -> confirmed (第2次以上) / dismissed (醫生關)
    confidence_status: Mapped[ConfidenceStatus] = mapped_column(
        SQLEnum(ConfidenceStatus),
        nullable=False,
        default=ConfidenceStatus.TO_OBSERVE,
        server_default=ConfidenceStatus.TO_OBSERVE.value,
    )
    # 哪次 visit 首次標 to_observe (FK 在 alembic migration 加)
    first_observed_at_visit: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # 哪次 visit 升 confirmed
    confirmed_at_visit: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    def __repr__(self) -> str:
        return f"<PatientFlag id={self.id} type={self.flag_type} status={self.confidence_status}>"
