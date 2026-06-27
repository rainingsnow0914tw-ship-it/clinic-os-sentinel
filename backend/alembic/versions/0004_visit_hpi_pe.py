"""visit add hpi + physical_exam (Phase 2.4c)

Revision ID: 0004_visit_hpi_pe
Revises: 0003_sentinel_layer
Create Date: 2026-06-27

司機 (Chloe 醫師) 示範真實診所病歷, 缺 HPI (現病史) + PE (查體) 兩段。
這兩段是 SOAP note 核心 (Subjective HPI / Objective PE), 真實診所手寫
病歷必有 -- visit 表 minimum 補上, frontend 才能渲染像真病歷。

加欄位:
- hpi (TEXT, nullable)         現病史 / Brief History 詳細病程
- physical_exam (TEXT, nullable)  查體醫師發現 (神清/咽紅/肺音/腹軟...)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_visit_hpi_pe"
down_revision: Union[str, None] = "0003_sentinel_layer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("visits", sa.Column("hpi", sa.Text, nullable=True))
    op.add_column("visits", sa.Column("physical_exam", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("visits", "physical_exam")
    op.drop_column("visits", "hpi")
