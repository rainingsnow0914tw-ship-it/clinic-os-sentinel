"""ai_drafts table (Phase 4.2c)

Revision ID: 0005_ai_drafts
Revises: 0004_visit_hpi_pe
Create Date: 2026-06-27

ADR-006 精神: AI 寫 ai_drafts → 醫師 review 後接受才入正表。
這版 minimal: 醫師按「完成就診」時, 把當下 AI panel 4 個 agent
response 全 dump 進 ai_drafts (status='accepted_with_visit'),
之後 Mode A/B 回顧才能看醫師當時看過什麼 AI 建議。

欄位:
- id, clinic_id, patient_id, visit_id  (FK)
- agent_type: intake / triage / audit / education
- payload_json: full agent response (JSONB)
- status: pending / accepted_with_visit / dismissed / accepted_to_record
- accepted_at: TIMESTAMPTZ nullable
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_ai_drafts"
down_revision: Union[str, None] = "0004_visit_hpi_pe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "clinic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clinics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "visit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_type", sa.String(20), nullable=False),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="accepted_with_visit",
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column(
            "is_demo_data",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_type IN ('intake', 'triage', 'audit', 'education')",
            name="ck_ai_drafts_agent_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted_with_visit', 'dismissed', 'accepted_to_record')",
            name="ck_ai_drafts_status",
        ),
    )
    op.create_index("ix_ai_drafts_visit", "ai_drafts", ["visit_id"])
    op.create_index("ix_ai_drafts_patient", "ai_drafts", ["patient_id"])
    op.create_index("ix_ai_drafts_agent_type", "ai_drafts", ["agent_type"])


def downgrade() -> None:
    op.drop_table("ai_drafts")
