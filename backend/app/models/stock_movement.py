"""
============================================================
models/stock_movement.py
============================================================
StockMovement — 庫存流水（append-only）。

每次扣庫存、進貨、調整、作廢回補都寫一筆。

movement_type:
- 'purchase'  進貨（+ qty）
- 'dispense'  發藥扣減（- qty）
- 'adjust'    人工調整（± qty）
- 'void_reverse'  作廢回補（+ qty，由作廢收據觸發）
- 'expire'    過期報銷（- qty）

⚠️ 商業底線第 6 條：所有庫存變動都走這張表，永不直接 UPDATE drug_batches。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.demo_mixin import DemoDataMixin


class StockMovement(Base, DemoDataMixin):
    """
    注意：這張表 append-only（沒 updated_at），所以不繼承 TimestampMixin。
    """
    __tablename__ = "stock_movements"

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

    drug_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drug_batches.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 進出類型
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 數量變化（正/負；同一個欄位放方向）
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)

    # 關聯到哪個 prescription_item / invoice / void / 進貨單
    # 用 (related_entity_type, related_entity_id) 做 polymorphic FK
    # 不做硬 FK 因為 entity_type 多元（會指向不同表）
    related_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "movement_type IN "
            "('purchase', 'dispense', 'adjust', 'void_reverse', 'expire')",
            name="ck_stock_movements_type",
        ),
        Index("ix_stock_movements_clinic_demo", "clinic_id", "is_demo_data"),
        Index(
            "ix_stock_movements_related",
            "related_entity_type", "related_entity_id",
        ),
    )
