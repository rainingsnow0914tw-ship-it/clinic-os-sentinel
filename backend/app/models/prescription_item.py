"""
============================================================
models/prescription_item.py
============================================================
PrescriptionItem — 處方明細（每行對應一個藥）。

藥量計算：
- daily_dose:   每日服用次數 × 每次劑量 = 一天總劑量（單位 = drug.unit）
- days:         開幾天的份量
- total_quantity = daily_dose × days  ← 服務層計算後寫入 / validation 會驗證
- total_price = total_quantity × unit_price_at_time

unit_price_at_time 是處方確認當下的售價快照，避免日後改價影響歷史紀錄。
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class PrescriptionItem(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "prescription_items"

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

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
    )

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 用法（自由文字 + 結構化）
    usage_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    daily_dose: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)

    # 計算結果（service 層算後寫入；validation 會檢查正確）
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_at_time: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        Index(
            "ix_prescription_items_prescription",
            "prescription_id",
        ),
        Index("ix_prescription_items_clinic_demo", "clinic_id", "is_demo_data"),
    )
