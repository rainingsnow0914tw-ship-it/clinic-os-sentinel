"""
============================================================
models/drug.py
============================================================
Drug — 藥品主檔（Sprint 2 minimal 版）。

完整版會有：定價模式、預設用法、處方分類、適應症、禁忌等。
這版只放 mock data + FEFO 計算用得到的欄位。
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class Drug(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "drugs"

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

    # 業務欄位
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # 'tablet', 'ml', 'cap'

    # Phase 7.4: 分類 (退燒止痛 / 抗生素 / 抗組織胺 / ...) for 處方選單
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 預設售價（per unit）；mock data 用得到
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )

    # 軟刪除
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )

    __table_args__ = (
        # 同一 clinic 內 code 唯一
        Index("uq_drugs_clinic_code", "clinic_id", "code", unique=True),
        Index("ix_drugs_clinic_demo", "clinic_id", "is_demo_data"),
    )
