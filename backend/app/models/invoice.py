"""
============================================================
models/invoice.py
============================================================
Invoice — 收據主檔。

簡化結構（minimal 版）：
- consultation_fee:  診療費
- medication_fee:    藥費（從 prescription_items 加總）
- other_fee:         其他費用
- total_amount:      = consultation + medication + other（service 層算後寫入）

void_reason / voided_at: 作廢時填，沒作廢就 null。
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class Invoice(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "invoices"

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

    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 收據編號（service 層生，格式如 YYYYMMDD-XXXX，每 clinic 獨立流水）
    invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 三個費用分項
    consultation_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )
    medication_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )
    other_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )

    # draft → issued → voided
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )

    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'issued', 'voided')",
            name="ck_invoices_status",
        ),
        # 同 clinic 內 invoice_no 唯一（issued 後才有號）
        Index(
            "uq_invoices_clinic_no",
            "clinic_id", "invoice_no",
            unique=True,
            postgresql_where="invoice_no IS NOT NULL",
        ),
        Index("ix_invoices_visit", "visit_id"),
        Index("ix_invoices_clinic_demo", "clinic_id", "is_demo_data"),
    )
