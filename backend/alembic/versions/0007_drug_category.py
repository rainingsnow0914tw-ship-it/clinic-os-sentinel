"""drugs.category column (Phase 7.4)

Revision ID: 0007_drug_category
Revises: 0006_doctor_watchlists
Create Date: 2026-06-28

司機 6/28 反饋: Rx 寫入要支援分類選單 (退燒/止痛/抗生素/...).
drugs 表加 category 欄位 (nullable, demo 用 14 個分類, 中文).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_drug_category"
down_revision: Union[str, None] = "0006_doctor_watchlists"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drugs",
        sa.Column("category", sa.String(50), nullable=True),
    )
    op.create_index("ix_drugs_category", "drugs", ["category"])


def downgrade() -> None:
    op.drop_index("ix_drugs_category", table_name="drugs")
    op.drop_column("drugs", "category")
