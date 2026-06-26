"""sprint2 minimal business tables

Revision ID: 0002_business_tables
Revises: 0001_initial
Create Date: 2026-05-02

新增 9 張業務表（minimal 版，欄位之後 Sprint 2 業務 logic 再補完整）：
- patients
- drugs
- drug_batches
- stock_movements
- visits
- prescriptions
- prescription_items
- invoices
- invoice_items

每張表都帶 source / is_demo_data 欄位（DemoDataMixin），讓
reset_dev_data.py 能安全只刪 demo data。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002_business_tables"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _common_business_cols():
    """所有業務表共用的欄位：UUID PK、timestamps、demo tracking、clinic FK。"""
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
    # ─────────────────────────────────────────────────────────────
    # patients
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "patients",
        *_common_business_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("id_number", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamp_cols(),
        sa.CheckConstraint(
            "gender IN ('M', 'F', 'other') OR gender IS NULL",
            name="ck_patients_gender",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_patients_status",
        ),
    )
    op.create_index("ix_patients_clinic_id", "patients", ["clinic_id"])
    op.create_index(
        "ix_patients_clinic_demo", "patients", ["clinic_id", "is_demo_data"]
    )
    op.create_index("ix_patients_is_demo_data", "patients", ["is_demo_data"])

    # ─────────────────────────────────────────────────────────────
    # drugs
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "drugs",
        *_common_business_cols(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column(
            "unit_price", sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_timestamp_cols(),
    )
    op.create_index(
        "uq_drugs_clinic_code", "drugs", ["clinic_id", "code"], unique=True
    )
    op.create_index(
        "ix_drugs_clinic_demo", "drugs", ["clinic_id", "is_demo_data"]
    )
    op.create_index("ix_drugs_is_demo_data", "drugs", ["is_demo_data"])

    # ─────────────────────────────────────────────────────────────
    # drug_batches
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "drug_batches",
        *_common_business_cols(),
        sa.Column(
            "drug_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drugs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("batch_no", sa.String(50), nullable=False),
        sa.Column("expiry_date", sa.Date, nullable=False),
        sa.Column("quantity_received", sa.Integer, nullable=False),
        sa.Column("quantity_remaining", sa.Integer, nullable=False),
        sa.Column(
            "cost_per_unit", sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        sa.Column("received_date", sa.Date, nullable=False),
        *_timestamp_cols(),
    )
    # FEFO query 用 — 帶 partial index
    op.execute("""
        CREATE INDEX ix_drug_batches_fefo
        ON drug_batches (clinic_id, drug_id, expiry_date)
        WHERE quantity_remaining > 0
    """)
    op.create_index(
        "ix_drug_batches_clinic_demo", "drug_batches",
        ["clinic_id", "is_demo_data"],
    )
    op.create_index(
        "ix_drug_batches_is_demo_data", "drug_batches", ["is_demo_data"]
    )

    # ─────────────────────────────────────────────────────────────
    # stock_movements (append-only — 沒 updated_at)
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "stock_movements",
        *_common_business_cols(),
        sa.Column(
            "drug_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drug_batches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity_change", sa.Integer, nullable=False),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "movement_type IN "
            "('purchase', 'dispense', 'adjust', 'void_reverse', 'expire')",
            name="ck_stock_movements_type",
        ),
    )
    op.create_index(
        "ix_stock_movements_clinic_demo", "stock_movements",
        ["clinic_id", "is_demo_data"],
    )
    op.create_index(
        "ix_stock_movements_is_demo_data", "stock_movements", ["is_demo_data"]
    )
    op.create_index(
        "ix_stock_movements_related", "stock_movements",
        ["related_entity_type", "related_entity_id"],
    )
    op.create_index(
        "ix_stock_movements_created_at", "stock_movements", ["created_at"]
    )

    # ─────────────────────────────────────────────────────────────
    # visits
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "visits",
        *_common_business_cols(),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "doctor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("visit_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chief_complaint", sa.String(500), nullable=True),
        sa.Column("diagnosis", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        *_timestamp_cols(),
        sa.CheckConstraint(
            "status IN ('draft', 'in_progress', 'completed', 'invoiced', 'voided')",
            name="ck_visits_status",
        ),
    )
    op.create_index(
        "ix_visits_clinic_patient", "visits", ["clinic_id", "patient_id"]
    )
    op.create_index(
        "ix_visits_clinic_demo", "visits", ["clinic_id", "is_demo_data"]
    )
    op.create_index("ix_visits_is_demo_data", "visits", ["is_demo_data"])

    # ─────────────────────────────────────────────────────────────
    # prescriptions
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "prescriptions",
        *_common_business_cols(),
        sa.Column(
            "visit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        *_timestamp_cols(),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'dispensed', 'voided')",
            name="ck_prescriptions_status",
        ),
    )
    # 一個 visit 最多一張 active prescription
    op.execute("""
        CREATE UNIQUE INDEX uq_prescriptions_visit
        ON prescriptions (visit_id)
        WHERE status != 'voided'
    """)
    op.create_index(
        "ix_prescriptions_clinic_demo", "prescriptions",
        ["clinic_id", "is_demo_data"],
    )
    op.create_index(
        "ix_prescriptions_is_demo_data", "prescriptions", ["is_demo_data"]
    )

    # ─────────────────────────────────────────────────────────────
    # prescription_items
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "prescription_items",
        *_common_business_cols(),
        sa.Column(
            "prescription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prescriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "drug_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drugs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("usage_text", sa.String(500), nullable=True),
        sa.Column("daily_dose", sa.Numeric(10, 2), nullable=False),
        sa.Column("days", sa.Integer, nullable=False),
        sa.Column("total_quantity", sa.Integer, nullable=False),
        sa.Column("unit_price_at_time", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        *_timestamp_cols(),
    )
    op.create_index(
        "ix_prescription_items_prescription", "prescription_items",
        ["prescription_id"],
    )
    op.create_index(
        "ix_prescription_items_clinic_demo", "prescription_items",
        ["clinic_id", "is_demo_data"],
    )
    op.create_index(
        "ix_prescription_items_is_demo_data", "prescription_items",
        ["is_demo_data"],
    )

    # ─────────────────────────────────────────────────────────────
    # invoices
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "invoices",
        *_common_business_cols(),
        sa.Column(
            "visit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("invoice_no", sa.String(50), nullable=True),
        sa.Column(
            "consultation_fee",
            sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "medication_fee",
            sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "other_fee", sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(10, 2), nullable=False, server_default="0"
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.String(500), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_cols(),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'voided')",
            name="ck_invoices_status",
        ),
    )
    # invoice_no 同 clinic 唯一（issued 後才有號）
    op.execute("""
        CREATE UNIQUE INDEX uq_invoices_clinic_no
        ON invoices (clinic_id, invoice_no)
        WHERE invoice_no IS NOT NULL
    """)
    op.create_index("ix_invoices_visit", "invoices", ["visit_id"])
    op.create_index(
        "ix_invoices_clinic_demo", "invoices", ["clinic_id", "is_demo_data"]
    )
    op.create_index("ix_invoices_is_demo_data", "invoices", ["is_demo_data"])

    # ─────────────────────────────────────────────────────────────
    # invoice_items
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "invoice_items",
        *_common_business_cols(),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("source_entity_type", sa.String(50), nullable=True),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamp_cols(),
        sa.CheckConstraint(
            "item_type IN ('consultation', 'medication', 'other')",
            name="ck_invoice_items_type",
        ),
    )
    op.create_index("ix_invoice_items_invoice", "invoice_items", ["invoice_id"])
    op.create_index(
        "ix_invoice_items_clinic_demo", "invoice_items",
        ["clinic_id", "is_demo_data"],
    )
    op.create_index(
        "ix_invoice_items_is_demo_data", "invoice_items", ["is_demo_data"]
    )


def downgrade() -> None:
    # 反向順序：先刪有 FK 依賴的 child table
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
    op.drop_table("visits")
    op.drop_table("stock_movements")
    op.drop_table("drug_batches")
    op.drop_table("drugs")
    op.drop_table("patients")
