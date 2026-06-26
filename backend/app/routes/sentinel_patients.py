"""
============================================================
routes/sentinel_patients.py -- Sentinel 病人查詢 + 心臟層摘要
============================================================
為 Phase 3 frontend (病人搜尋頁 + 病例瀏覽頁) 提供的 dev-bypass-safe
endpoint, 避開 jimmy Sprint 2 patients stub + clinic_permission middleware
的 firebase auth 依賴。

路徑:
- GET /v1/sentinel/patients?q=&clinic_id=     搜尋 (姓名 / 電話 / id_number 模糊)
- GET /v1/sentinel/patients/{patient_id}      單病人 detail (含心臟層摘要 + visit timeline)
- GET /v1/sentinel/patients/{patient_id}/heart-layer    純心臟層 (給 audit endpoint pre-load)

設計:
- demo mode: 沒帶 clinic_id query 就 auto pick 第一間 clinic
- 不接 Depends(get_current_membership), 走 SENTINEL_DEV_BYPASS_AUTH 路徑
- response schema 用 pydantic, frontend types/api.ts 對應
============================================================
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Patient,
    PatientFlag,
    PatientProblem,
    PatientMedication,
    PatientBaseline,
    Visit,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────
# DB session dep (本地簡化版, 不接 get_current_membership)
# ─────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_clinic_id(db: Session, clinic_id: Optional[UUID]) -> UUID:
    """指定 clinic_id 就用, 否則取第一間 (demo mode)。"""
    if clinic_id:
        return clinic_id
    c = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
    if not c:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No clinic in DB. Run scripts/seed first.",
        )
    return c.id


# ─────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────

class PatientCard(BaseModel):
    """搜尋結果卡片用 (簡化版)。"""
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    name: str
    gender: str | None = None
    date_of_birth: str | None = None
    phone: str | None = None
    id_number: str | None = None

    # 心臟層摘要計數 (前端不展開, 只看數字)
    flag_count: int = 0
    chronic_count: int = 0
    has_red_flag: bool = False


class PatientSearchResponse(BaseModel):
    items: list[PatientCard]
    total: int
    clinic_id: UUID


class HeartFlagSummary(BaseModel):
    id: UUID
    flag_type: str
    severity: str | None = None
    content: str
    confidence_status: str
    flag_source: str


class HeartProblemSummary(BaseModel):
    id: UUID
    problem_name: str
    icd10_code: str | None = None
    control_status: str
    diagnosed_at: str | None = None


class HeartMedicationSummary(BaseModel):
    id: UUID
    medication_name: str
    category: str
    dosage: str | None = None
    frequency: str | None = None
    is_active: bool


class HeartBaselineSummary(BaseModel):
    id: UUID
    category: str
    value_text: str
    measured_at: str | None = None


class HeartLayerSummary(BaseModel):
    """心臟層摘要 (對應 v0.3.1 §5.2 病例頁)。"""
    flags: list[HeartFlagSummary]
    problems: list[HeartProblemSummary]
    medications: list[HeartMedicationSummary]
    baselines: list[HeartBaselineSummary]


class VisitTimelineItem(BaseModel):
    id: UUID
    visit_date: str
    chief_complaint: str | None = None
    diagnosis: str | None = None
    status: str


class PatientDetailResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    name: str
    gender: str | None = None
    date_of_birth: str | None = None
    phone: str | None = None
    id_number: str | None = None
    clinic_id: UUID

    heart_layer: HeartLayerSummary
    visits: list[VisitTimelineItem]


# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@router.get("/sentinel/patients", response_model=PatientSearchResponse)
def search_patients(
    q: str = Query(default="", description="姓名 / 電話 / id_number 模糊搜尋"),
    clinic_id: Optional[UUID] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    """病人搜尋 (Sentinel demo, dev bypass)。"""
    cid = _resolve_clinic_id(db, clinic_id)

    stmt = select(Patient).where(Patient.clinic_id == cid)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.name.ilike(like),
                Patient.phone.ilike(like),
                Patient.id_number.ilike(like),
            )
        )
    stmt = stmt.order_by(Patient.id_number).limit(limit)
    patients = db.scalars(stmt).all()

    # 一次撈所有心臟層紅旗 / 慢性病 計數 (避免 N+1)
    pids = [p.id for p in patients]
    flags_by_pid: dict[UUID, list[PatientFlag]] = {}
    if pids:
        for f in db.scalars(
            select(PatientFlag).where(PatientFlag.patient_id.in_(pids))
        ).all():
            flags_by_pid.setdefault(f.patient_id, []).append(f)
    problems_count_by_pid: dict[UUID, int] = {}
    if pids:
        for p in db.scalars(
            select(PatientProblem).where(PatientProblem.patient_id.in_(pids))
        ).all():
            problems_count_by_pid[p.patient_id] = problems_count_by_pid.get(p.patient_id, 0) + 1

    items = []
    for p in patients:
        flags = flags_by_pid.get(p.id, [])
        items.append(
            PatientCard(
                id=p.id,
                name=p.name,
                gender=p.gender,
                date_of_birth=p.date_of_birth.isoformat() if p.date_of_birth else None,
                phone=p.phone,
                id_number=p.id_number,
                flag_count=len(flags),
                chronic_count=problems_count_by_pid.get(p.id, 0),
                has_red_flag=any(f.severity == "red" for f in flags),
            )
        )

    return PatientSearchResponse(items=items, total=len(items), clinic_id=cid)


def _load_heart_layer(db: Session, patient_id: UUID) -> HeartLayerSummary:
    flags = db.scalars(
        select(PatientFlag).where(PatientFlag.patient_id == patient_id)
    ).all()
    problems = db.scalars(
        select(PatientProblem).where(PatientProblem.patient_id == patient_id)
    ).all()
    meds = db.scalars(
        select(PatientMedication).where(PatientMedication.patient_id == patient_id)
    ).all()
    baselines = db.scalars(
        select(PatientBaseline).where(PatientBaseline.patient_id == patient_id)
    ).all()

    return HeartLayerSummary(
        flags=[
            HeartFlagSummary(
                id=f.id,
                flag_type=f.flag_type,
                severity=f.severity,
                content=f.content,
                confidence_status=f.confidence_status,
                flag_source=f.flag_source,
            )
            for f in flags
        ],
        problems=[
            HeartProblemSummary(
                id=p.id,
                problem_name=p.problem_name,
                icd10_code=p.icd10_code,
                control_status=p.control_status,
                diagnosed_at=p.diagnosed_at.isoformat() if p.diagnosed_at else None,
            )
            for p in problems
        ],
        medications=[
            HeartMedicationSummary(
                id=m.id,
                medication_name=m.medication_name,
                category=m.category,
                dosage=m.dosage,
                frequency=m.frequency,
                is_active=m.is_active,
            )
            for m in meds
        ],
        baselines=[
            HeartBaselineSummary(
                id=b.id,
                category=b.category,
                value_text=b.value_text,
                measured_at=b.measured_at.isoformat() if b.measured_at else None,
            )
            for b in baselines
        ],
    )


@router.get("/sentinel/patients/{patient_id}", response_model=PatientDetailResponse)
def get_patient_detail(
    patient_id: UUID,
    db: Session = Depends(get_db),
):
    """單病人 detail: demographics + 心臟層摘要 + visit timeline。"""
    p = db.get(Patient, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    heart = _load_heart_layer(db, patient_id)

    visits = db.scalars(
        select(Visit)
        .where(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.desc())
    ).all()

    return PatientDetailResponse(
        id=p.id,
        name=p.name,
        gender=p.gender,
        date_of_birth=p.date_of_birth.isoformat() if p.date_of_birth else None,
        phone=p.phone,
        id_number=p.id_number,
        clinic_id=p.clinic_id,
        heart_layer=heart,
        visits=[
            VisitTimelineItem(
                id=v.id,
                visit_date=v.visit_date.isoformat() if v.visit_date else "",
                chief_complaint=v.chief_complaint,
                diagnosis=v.diagnosis,
                status=v.status,
            )
            for v in visits
        ],
    )


@router.get("/sentinel/patients/{patient_id}/heart-layer", response_model=HeartLayerSummary)
def get_patient_heart_layer(
    patient_id: UUID,
    db: Session = Depends(get_db),
):
    """純心臟層 (給 audit endpoint pre-load 或 frontend 局部 refresh)。"""
    p = db.get(Patient, patient_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return _load_heart_layer(db, patient_id)
