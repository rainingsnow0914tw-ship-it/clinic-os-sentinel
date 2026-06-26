"""sentinel layer: heart 4 tables + visit_examinations + heart_layer_snapshots

Revision ID: 0003_sentinel_layer
Revises: 0002_business_tables
Create Date: 2026-06-27

v0.3 Phase 1 起手 -- 把 v0.1 baseline 的哨兵層 4 心臟表移植到 v3 並升 PG-style,
加上 v0.3.1 設計補丁 (confidence_status / first/confirmed_at_visit /
visit_examinations / heart_layer_snapshots)。

新增 6 張表:
- patient_problems        慢性病 / 主動 problem list
- patient_medications     長期 / 短期用藥
- patient_flags           5+1 類紅旗 (含 v0.3.1 confidence_status)
- patient_baselines       基線數據 (BP/HR/BMI 趨勢)
- visit_examinations      v0.3 新: 結構化檢查 (vital signs / lab / xray / ecg)
- heart_layer_snapshots   v0.3 新: visit 前後拍照 (Mode A 依賴)

設計原則對齊 0002:
- UUID PK 走 server_default gen_random_uuid()
- 帶 DemoDataMixin (source / is_demo_data)
- 時間戳走 server_default now()
- FK ondelete RESTRICT (心臟表) / CASCADE (snapshot 跟著 visit 走)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_sentinel_layer"
down_revision: Union[str, None] = "0002_business_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _common_business_cols():
    """沿用 0002 樣板。"""
    return [
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
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column(
            "is_demo_data",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    ]


def _timestamp_cols():
    return [
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
    ]


def upgrade() -> None:
    # ─────────────────────────────────────────────
    # patient_problems  -- 慢性病 / 主動 problem list
    # ─────────────────────────────────────────────
    op.create_table(
        "patient_problems",
        *_common_business_cols(),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("problem_name", sa.String(200), nullable=False),
        sa.Column("icd10_code", sa.String(20), nullable=True),
        sa.Column("control_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("problem_source", sa.String(30), nullable=False, server_default="self_report"),
        sa.Column("diagnosed_at", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamp_cols(),
    )
    op.create_index("ix_patient_problems_clinic_patient", "patient_problems", ["clinic_id", "patient_id"])
    op.create_index("ix_patient_problems_is_demo", "patient_problems", ["is_demo_data"])

    # ─────────────────────────────────────────────
    # patient_medications  -- 長期 / 短期用藥
    # ─────────────────────────────────────────────
    op.create_table(
        "patient_medications",
        *_common_business_cols(),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("medication_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False, server_default="long_term"),
        sa.Column("dosage", sa.String(100), nullable=True),
        sa.Column("frequency", sa.String(100), nullable=True),
        sa.Column("medication_source", sa.String(30), nullable=False, server_default="self_report"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamp_cols(),
    )
    op.create_index("ix_patient_medications_clinic_patient", "patient_medications", ["clinic_id", "patient_id"])
    op.create_index("ix_patient_medications_is_demo", "patient_medications", ["is_demo_data"])

    # ─────────────────────────────────────────────
    # patient_flags  -- 紅旗 (含 v0.3.1 §7.3 confidence_status 升級邏輯)
    # ─────────────────────────────────────────────
    op.create_table(
        "patient_flags",
        *_common_business_cols(),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("flag_type", sa.String(30), nullable=False),
        sa.Column("temporal_mode", sa.String(20), nullable=False, server_default="permanent"),
        sa.Column("severity", sa.String(10), nullable=True),
        sa.Column("flag_source", sa.String(30), nullable=False, server_default="self_report"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("wake_trigger", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        # v0.3.1 §7.3 新增
        sa.Column(
            "confidence_status",
            sa.String(20),
            nullable=False,
            server_default="to_observe",
        ),
        sa.Column(
            "first_observed_at_visit",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "confirmed_at_visit",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamp_cols(),
    )
    op.create_index("ix_patient_flags_clinic_patient", "patient_flags", ["clinic_id", "patient_id"])
    op.create_index("ix_patient_flags_type", "patient_flags", ["flag_type"])
    op.create_index("ix_patient_flags_confidence", "patient_flags", ["confidence_status"])
    op.create_index("ix_patient_flags_is_demo", "patient_flags", ["is_demo_data"])

    # ─────────────────────────────────────────────
    # patient_baselines  -- 基線數據 (BP/HR/BMI 趨勢)
    # ─────────────────────────────────────────────
    op.create_table(
        "patient_baselines",
        *_common_business_cols(),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("baseline_source", sa.String(30), nullable=False, server_default="clinical"),
        sa.Column("value_text", sa.Text, nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamp_cols(),
    )
    op.create_index("ix_patient_baselines_clinic_patient", "patient_baselines", ["clinic_id", "patient_id"])
    op.create_index("ix_patient_baselines_category", "patient_baselines", ["category"])
    op.create_index("ix_patient_baselines_is_demo", "patient_baselines", ["is_demo_data"])

    # ─────────────────────────────────────────────
    # visit_examinations  -- v0.3 新: 結構化檢查 (1:1 with visit)
    # ─────────────────────────────────────────────
    op.create_table(
        "visit_examinations",
        *_common_business_cols(),
        sa.Column(
            "visit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("vital_signs_json", postgresql.JSONB, nullable=True),
        sa.Column("lab_results_json", postgresql.JSONB, nullable=True),
        sa.Column("xray_findings", sa.Text, nullable=True),
        sa.Column("ecg_findings", sa.Text, nullable=True),
        sa.Column("free_notes", sa.Text, nullable=True),
        *_timestamp_cols(),
    )
    op.create_index("ix_visit_examinations_patient", "visit_examinations", ["patient_id"])
    op.create_index("ix_visit_examinations_is_demo", "visit_examinations", ["is_demo_data"])

    # ─────────────────────────────────────────────
    # heart_layer_snapshots  -- v0.3 新: Mode A 依賴
    # ─────────────────────────────────────────────
    op.create_table(
        "heart_layer_snapshots",
        *_common_business_cols(),
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
        sa.Column("snapshot_type", sa.String(20), nullable=False),
        sa.Column("problems_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("medications_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("flags_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("baselines_json", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary_text", sa.Text, nullable=True),
        *_timestamp_cols(),
        sa.CheckConstraint(
            "snapshot_type IN ('before_visit', 'after_visit')",
            name="ck_snapshots_type",
        ),
    )
    op.create_index(
        "ix_snapshots_visit_type",
        "heart_layer_snapshots",
        ["visit_id", "snapshot_type"],
    )
    op.create_index("ix_snapshots_patient", "heart_layer_snapshots", ["patient_id"])
    op.create_index("ix_snapshots_is_demo", "heart_layer_snapshots", ["is_demo_data"])


def downgrade() -> None:
    op.drop_table("heart_layer_snapshots")
    op.drop_table("visit_examinations")
    op.drop_table("patient_baselines")
    op.drop_table("patient_flags")
    op.drop_table("patient_medications")
    op.drop_table("patient_problems")
