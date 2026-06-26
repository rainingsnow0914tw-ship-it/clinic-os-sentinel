"""
============================================================
models/invoice_item.py
============================================================
InvoiceItem — 收據明細。

每筆 invoice_item 對應收據上的一行：
- consultation:   診療費（一張 invoice 只有一筆，金額 = invoice.consultation_fee）
- medication:     藥費（多筆，每筆對應一個 prescription_item）
- other:          其他費用（耗材、檢驗等，可選）

設計重點：
1. 不直接 reference prescription_item_id 是因為非藥品行（diagnostic、consultation）
   沒有對應的 prescription item。用 source_entity_type/id 做 polymorphic ref。
2. 所有 invoice_item 的 line_total 加總 = invoice.total_amount（validation）
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, Integer, Numeric, String
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class InvoiceItem(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "invoice_items"

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

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 類型
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 顯示在收據上的名稱
    description: Mapped[str] = mapped_column(String(200), nullable=False)

    # 數量、單價、小計（service 層算 line_total = quantity × unit_price）
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Polymorphic reference：對應到 prescription_item 或別的 entity
    source_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "item_type IN ('consultation', 'medication', 'other')",
            name="ck_invoice_items_type",
        ),
        Index("ix_invoice_items_invoice", "invoice_id"),
        Index("ix_invoice_items_clinic_demo", "clinic_id", "is_demo_data"),
    )
