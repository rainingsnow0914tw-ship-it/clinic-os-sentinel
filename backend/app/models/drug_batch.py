"""
============================================================
models/drug_batch.py
============================================================
DrugBatch — 藥品批號庫存（FEFO 核心）。

每筆代表「某藥品的某批號的當前可用數量」。
- expiry_date: FEFO 排序的關鍵
- quantity_remaining: 當前剩餘量（被 stock_movements 動）

⚠️ 商業底線：扣庫存一定要過 stock_movements，不要直接 UPDATE quantity_remaining。
   這個值由 service layer 在每次 movement 時同步更新。
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class DrugBatch(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "drug_batches"

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

    drug_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drugs.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 批號（廠商給的 lot number）
    batch_no: Mapped[str] = mapped_column(String(50), nullable=False)

    # FEFO 關鍵欄位
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 進貨數量、剩餘數量、進貨成本（per unit）
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )

    received_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        # FEFO 查詢的關鍵 index：(clinic, drug, expiry, remaining>0)
        Index(
            "ix_drug_batches_fefo",
            "clinic_id", "drug_id", "expiry_date",
            postgresql_where="quantity_remaining > 0",
        ),
        Index("ix_drug_batches_clinic_demo", "clinic_id", "is_demo_data"),
    )
