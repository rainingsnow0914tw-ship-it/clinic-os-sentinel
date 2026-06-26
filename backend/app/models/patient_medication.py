"""
============================================================
models/patient_medication.py — 心臟表 2:長期用藥清單
============================================================
Sentinel 哨兵記憶心臟的長期用藥獨立表。

為什麼獨立(不放 problem 的關聯欄位)：
- 後閘門 agent 撞的是「完整長期用藥清單」(含散落各次就診的)
- 一個藥可能對應多病(高血壓藥 + 心臟保護)
- 保健品 / 中藥不一定對應某慢性病但會影響交互作用

對應 schemas/sentinel.py 的 HeartMedication。
============================================================
"""

import uuid
from sqlalchemy import String, Boolean, Uuid, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base, TimestampMixin


class MedicationCategory(str, enum.Enum):
    """藥物類別 — 影響規則引擎處理方式。"""

    CHRONIC_DISEASE_MED = "chronic_disease_med"   # 慢性病處方藥
    SUPPLEMENT = "supplement"                     # 保健品
    TCM = "tcm"                                   # 中藥 / 中成藥


class MedicationSource(str, enum.Enum):
    """資料來源。"""

    SELF_REPORT = "self_report"
    VERIFIED = "verified"
    AUTHORITATIVE = "authoritative"


class PatientMedication(Base, TimestampMixin):
    """病人長期用藥。"""

    __tablename__ = "patient_medications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)

    # 藥名(原始寫法，可能是中文/英文/品牌名/學名)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 類別
    category: Mapped[MedicationCategory] = mapped_column(
        SQLEnum(MedicationCategory),
        nullable=False,
        default=MedicationCategory.CHRONIC_DISEASE_MED,
    )

    # 對應哪個 problem(可空，保健品中藥常常沒對應)
    for_problem_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)

    # 成分明確性 — 後閘門 agent 對「成分不明」要特別提醒，不假裝確定
    composition_certain: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # 來源
    source: Mapped[MedicationSource] = mapped_column(
        SQLEnum(MedicationSource),
        nullable=False,
        default=MedicationSource.SELF_REPORT,
    )

    def __repr__(self) -> str:
        return f"<PatientMedication id={self.id} name={self.name} cat={self.category}>"
