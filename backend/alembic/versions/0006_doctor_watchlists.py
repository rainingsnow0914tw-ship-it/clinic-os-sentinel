"""doctor_watchlists table (Phase 7.2)

Revision ID: 0006_doctor_watchlists
Revises: 0005_ai_drafts
Create Date: 2026-06-28

v0.3.1 design: AI reverse-trains doctor via Mode B retrospect.
When a Mode B review surfaces a lesson worth remembering, doctor can
pin it to personal watchlist. Next time the doctor opens a new visit,
watchlist banner shows reminders.

Fields:
- id, clinic_id, doctor_user_id  (FK)
- source_visit_id (FK, where this lesson came from)
- source_mode VARCHAR(20)  ('hindsight' / 'at_the_time')
- pattern VARCHAR(200)     ('Elderly + Controlled HTN + NSAID')
- lesson_text TEXT         ('Schedule 4-week BP follow-up')
- triggered_count INT default 0
- is_dismissed BOOL default false
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_doctor_watchlists"
down_revision: Union[str, None] = "0005_ai_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctor_watchlists",
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
            "doctor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_visit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_mode", sa.String(20), nullable=False, server_default="hindsight"),
        sa.Column("pattern", sa.String(200), nullable=False),
        sa.Column("lesson_text", sa.Text, nullable=False),
        sa.Column(
            "triggered_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_dismissed",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
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
            "source_mode IN ('hindsight', 'at_the_time')",
            name="ck_doctor_watchlists_source_mode",
        ),
    )
    op.create_index(
        "ix_doctor_watchlists_doctor",
        "doctor_watchlists",
        ["doctor_user_id", "is_dismissed"],
    )
    op.create_index(
        "ix_doctor_watchlists_clinic",
        "doctor_watchlists",
        ["clinic_id"],
    )


def downgrade() -> None:
    op.drop_table("doctor_watchlists")
