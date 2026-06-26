"""
ORM models 匯出口

Sprint 1（已完成）：認證與多租戶 — clinics / users / clinic_memberships / audit_logs
Sprint 2（minimal 版）：業務 entities，欄位先放最小集合，後續 sprint 補完整

設計原則：
1. 所有 table 用 UUID v4 PK（ADR-003）
2. 所有業務 table 帶 clinic_id（多租戶）
3. 所有業務 table 用 DemoDataMixin（reset 時可清掉 demo data）
4. 不硬刪資料，用 status 軟刪除
"""

from app.models.audit_log import AuditLog
from app.models.base import Base, TimestampMixin
from app.models.clinic import Clinic
from app.models.clinic_membership import ClinicMembership, ClinicRole
from app.models.demo_mixin import (
    DemoDataMixin,
    SOURCE_AGENT,
    SOURCE_IMPORT,
    SOURCE_MANUAL,
    SOURCE_MOCK,
    VALID_SOURCES,
)
from app.models.drug import Drug
from app.models.drug_batch import DrugBatch
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.visit import Visit

# Sentinel 哨兵層心臟 4 表（v0.3 移植自 v0.1 baseline）
from app.models.patient_baseline import PatientBaseline, BaselineCategory, BaselineSource
from app.models.patient_flag import (
    PatientFlag,
    FlagType,
    FlagTemporalMode,
    FlagSeverity,
    FlagSource,
    ConfidenceStatus,  # v0.3.1 §7.3
)
from app.models.patient_medication import PatientMedication, MedicationCategory, MedicationSource
from app.models.patient_problem import PatientProblem, ControlStatus, ProblemSource

# v0.3.1 新增表（結構化檢查 + 心臟層快照）
from app.models.visit_examination import VisitExamination
from app.models.heart_layer_snapshot import HeartLayerSnapshot

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "DemoDataMixin",
    # Source 常數
    "SOURCE_MANUAL",
    "SOURCE_MOCK",
    "SOURCE_IMPORT",
    "SOURCE_AGENT",
    "VALID_SOURCES",
    # Sprint 1
    "User",
    "Clinic",
    "ClinicMembership",
    "ClinicRole",
    "AuditLog",
    # Sprint 2 minimal
    "Patient",
    "Drug",
    "DrugBatch",
    "StockMovement",
    "Visit",
    "Prescription",
    "PrescriptionItem",
    "Invoice",
    "InvoiceItem",
    # Sentinel 哨兵層心臟 4 表
    "PatientBaseline",
    "BaselineCategory",
    "BaselineSource",
    "PatientFlag",
    "FlagType",
    "FlagTemporalMode",
    "FlagSeverity",
    "FlagSource",
    "PatientMedication",
    "MedicationCategory",
    "MedicationSource",
    "PatientProblem",
    "ControlStatus",
    "ProblemSource",
    "ConfidenceStatus",
    # v0.3.1 新表
    "VisitExamination",
    "HeartLayerSnapshot",
]
