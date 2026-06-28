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
import re
from typing import Optional
from uuid import UUID

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import User, VisitExamination as _VEModel

from app.core.database import SessionLocal
from app.models import (
    AiDraft,
    Clinic,
    Drug,
    Patient,
    PatientFlag,
    PatientProblem,
    PatientMedication,
    PatientBaseline,
    Prescription,
    PrescriptionItem,
    Visit,
)
from app.services.heart_evolution import (
    evolve_heart_layer_after_visit,
    take_heart_layer_snapshot,
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


def _build_drug_keyword_map(db: Session) -> dict[str, Drug]:
    """build keyword (lower) -> Drug map: drug.name + drug.code 學名變體.

    司機 6/28 反饋: medic 填 Rx textarea 但完成就診後處方不見了.
    解法: parse Rx 每行第 1 詞 fuzzy match drug.name 或 drug.code 學名.

    e.g. 'Azithromycin 250 首次2粒 qd 5 day' → match 'azithromycin' →
         Zithromax (AZITHROMYCIN_250)
    """
    drugs = db.scalars(select(Drug)).all()
    out: dict[str, Drug] = {}
    for d in drugs:
        # brand name (Norvasc)
        if d.name:
            out[d.name.lower()] = d
        # code 學名 (AMLODIPINE_5 -> amlodipine)
        if d.code:
            base = d.code.split("_")[0].lower()
            if base and base not in out:
                out[base] = d
    return out


def _parse_rx_line(line: str, drug_by_kw: dict[str, Drug]) -> tuple[Drug | None, str, int, int]:
    """Parse one Rx textarea line.

    Args:
      line: 'Azithromycin 250 首次2粒 qd 5 day'
      drug_by_kw: keyword (lower) -> Drug

    Returns: (drug or None, usage_text=full_line, daily_dose, days)
    """
    line_lower = line.lower()

    # parse days
    days = 7
    m = re.search(r"(\d+)\s*(?:day|d\b|天|d\s*$)", line_lower)
    if m:
        try:
            days = int(m.group(1))
        except ValueError:
            pass

    # parse daily_dose by frequency keyword
    daily_dose = 1
    if re.search(r"\bbid\b|\bq12h\b", line_lower):
        daily_dose = 2
    elif re.search(r"\btid\b|\bq8h\b", line_lower):
        daily_dose = 3
    elif re.search(r"\bqid\b|\bq6h\b", line_lower):
        daily_dose = 4
    elif re.search(r"\bqd\b|\bqday\b|\bod\b|\bdaily\b", line_lower):
        daily_dose = 1

    # match drug (按 keyword 長度 desc 避免短 keyword 偷 match)
    drug: Drug | None = None
    for keyword in sorted(drug_by_kw.keys(), key=len, reverse=True):
        if keyword in line_lower:
            drug = drug_by_kw[keyword]
            break

    return drug, line[:500], daily_dose, days


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
    # Phase 8 fairness: 評審看 reconstruct 是否有先知能力的證據鏈
    first_observed_at_visit: UUID | None = None
    confirmed_at_visit: UUID | None = None


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


class PrescriptionItemSummary(BaseModel):
    """處方一筆 (Phase 2.4d)"""
    drug_name: str
    drug_code: str | None = None
    unit: str | None = None
    usage_text: str | None = None    # 例 "1#bid pox5D" 醫師簡寫
    daily_dose: float | None = None
    days: int | None = None
    total_quantity: int | None = None


class AiDraftSummary(BaseModel):
    """Phase 4.2d: visit 對應的 ai_drafts (含當時 AI panel 結果, Mode A/B 回顧用)"""
    id: UUID
    agent_type: str
    status: str
    payload: dict
    accepted_at: str | None = None


class VisitTimelineItem(BaseModel):
    id: UUID
    visit_date: str
    chief_complaint: str | None = None
    hpi: str | None = None             # 現病史 (Phase 2.4c)
    physical_exam: str | None = None   # 查體 (Phase 2.4c)
    diagnosis: str | None = None
    status: str
    # v0.3 examination 摘要 (jsonb columns 直接 expose, frontend 自行 render)
    vital_signs: dict | None = None
    lab_results: list | None = None
    xray_findings: str | None = None
    ecg_findings: str | None = None
    # Phase 2.4d 處方
    prescription_items: list[PrescriptionItemSummary] = []
    # Phase 4.2d ai_drafts (當時 AI 建議)
    ai_drafts: list[AiDraftSummary] = []


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
                first_observed_at_visit=f.first_observed_at_visit,
                confirmed_at_visit=f.confirmed_at_visit,
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

    # 一次撈所有 visit 的 examination + prescription + ai_drafts (避免 N+1)
    visit_ids = [v.id for v in visits]
    exam_by_vid: dict[UUID, "VisitExamination"] = {}
    rx_by_vid: dict[UUID, list[PrescriptionItemSummary]] = {}
    drafts_by_vid: dict[UUID, list[AiDraftSummary]] = {}
    if visit_ids:
        for draft in db.scalars(
            select(AiDraft)
            .where(AiDraft.visit_id.in_(visit_ids))
            .order_by(AiDraft.created_at)
        ).all():
            drafts_by_vid.setdefault(draft.visit_id, []).append(
                AiDraftSummary(
                    id=draft.id,
                    agent_type=draft.agent_type,
                    status=draft.status,
                    payload=draft.payload_json,
                    accepted_at=draft.accepted_at.isoformat() if draft.accepted_at else None,
                )
            )
        from app.models import VisitExamination as _VE
        for e in db.scalars(select(_VE).where(_VE.visit_id.in_(visit_ids))).all():
            exam_by_vid[e.visit_id] = e

        # 一次 join prescription -> prescription_items -> drug 撈出 visit 處方
        rx_rows = db.execute(
            select(
                Prescription.visit_id,
                Drug.name,
                Drug.code,
                Drug.unit,
                PrescriptionItem.usage_text,
                PrescriptionItem.daily_dose,
                PrescriptionItem.days,
                PrescriptionItem.total_quantity,
            )
            .join(PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id)
            .join(Drug, Drug.id == PrescriptionItem.drug_id)
            .where(Prescription.visit_id.in_(visit_ids))
        ).all()
        for row in rx_rows:
            vid, name, code, unit, usage, dd, days, qty = row
            rx_by_vid.setdefault(vid, []).append(
                PrescriptionItemSummary(
                    drug_name=name,
                    drug_code=code,
                    unit=unit,
                    usage_text=usage,
                    daily_dose=float(dd) if dd is not None else None,
                    days=days,
                    total_quantity=qty,
                )
            )

    visit_items = []
    for v in visits:
        e = exam_by_vid.get(v.id)
        visit_items.append(
            VisitTimelineItem(
                id=v.id,
                visit_date=v.visit_date.isoformat() if v.visit_date else "",
                chief_complaint=v.chief_complaint,
                hpi=v.hpi,
                physical_exam=v.physical_exam,
                diagnosis=v.diagnosis,
                status=v.status,
                vital_signs=e.vital_signs_json if e else None,
                lab_results=e.lab_results_json if e else None,
                xray_findings=e.xray_findings if e else None,
                ecg_findings=e.ecg_findings if e else None,
                prescription_items=rx_by_vid.get(v.id, []),
                ai_drafts=drafts_by_vid.get(v.id, []),
            )
        )

    return PatientDetailResponse(
        id=p.id,
        name=p.name,
        gender=p.gender,
        date_of_birth=p.date_of_birth.isoformat() if p.date_of_birth else None,
        phone=p.phone,
        id_number=p.id_number,
        clinic_id=p.clinic_id,
        heart_layer=heart,
        visits=visit_items,
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


# ─────────────────────────────────────────────────────────
# Create new visit (Phase 4.1)
# ─────────────────────────────────────────────────────────

class VitalSignsInput(BaseModel):
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    heart_rate: int | None = None
    respiratory_rate: int | None = None
    temperature_c: float | None = None
    oxygen_saturation: int | None = None


class AiDraftInput(BaseModel):
    """Phase 4.2c: 醫師按完成就診時帶上來的 AI panel 結果。"""
    agent_type: str   # intake / triage / audit / education
    payload: dict     # full agent response


class PrescriptionItemInput(BaseModel):
    """Phase 7.4: 結構化 Rx item (form UI 用, 已選定 drug_id, 不用 parse)"""
    drug_id: UUID
    usage_text: str = Field(default="", max_length=500)
    daily_dose: int = Field(..., ge=1)
    days: int = Field(..., ge=1)


class NewVisitRequest(BaseModel):
    chief_complaint: str = Field(..., min_length=1)
    hpi: str | None = None
    physical_exam: str | None = None
    diagnosis: str | None = None
    visit_date: str | None = None   # ISO format, 預設 now
    vital_signs: VitalSignsInput | None = None
    free_notes: str | None = None
    ai_drafts: list[AiDraftInput] = []   # Phase 4.2c: AI panel 結果一起寫
    prescription_lines: list[str] = []   # Phase 7.3: 一行一個 Rx, backend parse drug + dose (fallback)
    prescription_items: list[PrescriptionItemInput] = []   # Phase 7.4: 結構化 Rx (form UI 主要途徑)


class HeartEvolutionSummary(BaseModel):
    """Phase 5: visit 完成時心臟層自動演進統計"""
    problems_added: int = 0
    medications_added: int = 0
    flags_added: int = 0
    flags_upgraded: int = 0
    baselines_added: int = 0


class NewVisitResponse(BaseModel):
    visit_id: UUID
    patient_id: UUID
    visit_date: str
    status: str
    ai_drafts_saved: int = 0
    prescription_items_saved: int = 0   # Phase 7.3
    prescription_items_unmatched: list[str] = []   # 找不到對應 drug 的 raw line
    heart_evolution: HeartEvolutionSummary | None = None


@router.post(
    "/sentinel/patients/{patient_id}/visits",
    response_model=NewVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_visit(
    patient_id: UUID,
    payload: NewVisitRequest,
    db: Session = Depends(get_db),
):
    """新就診 (Phase 4.1, dev-bypass)。

    建 Visit + VisitExamination (如果帶 vital_signs)。
    醫師 ID auto pick 第一個 owner user (demo mode)。
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    # owner user (demo 一個醫師)
    owner = db.scalars(select(User).order_by(User.created_at).limit(1)).first()
    if not owner:
        raise HTTPException(status_code=500, detail="No user in DB")

    # visit_date
    if payload.visit_date:
        try:
            vdate = datetime.fromisoformat(payload.visit_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid visit_date: {payload.visit_date}")
    else:
        vdate = datetime.now(timezone.utc)

    visit_uuid = uuid4()
    visit = Visit(
        id=visit_uuid,
        clinic_id=patient.clinic_id,
        patient_id=patient.id,
        doctor_user_id=owner.id,
        visit_date=vdate,
        chief_complaint=payload.chief_complaint,
        hpi=payload.hpi,
        physical_exam=payload.physical_exam,
        diagnosis=payload.diagnosis,
        status="completed",
        source="manual",
        is_demo_data=False,
    )
    db.add(visit)

    # 如果帶 vital_signs / free_notes 也建 visit_examination
    vs = payload.vital_signs
    if vs and any(getattr(vs, f) is not None for f in vs.model_fields):
        exam = _VEModel(
            id=uuid4(),
            clinic_id=patient.clinic_id,
            visit_id=visit_uuid,
            patient_id=patient.id,
            vital_signs_json=vs.model_dump(exclude_none=True),
            lab_results_json=None,
            xray_findings=None,
            ecg_findings=None,
            free_notes=payload.free_notes,
            source="manual",
            is_demo_data=False,
        )
        db.add(exam)
    elif payload.free_notes:
        exam = _VEModel(
            id=uuid4(),
            clinic_id=patient.clinic_id,
            visit_id=visit_uuid,
            patient_id=patient.id,
            vital_signs_json=None,
            lab_results_json=None,
            xray_findings=None,
            ecg_findings=None,
            free_notes=payload.free_notes,
            source="manual",
            is_demo_data=False,
        )
        db.add(exam)

    # 先 flush visit + examination, 確保 ai_drafts FK to visit_id 可解析
    db.flush()

    # Phase 6.1: visit 起始拍 before_visit snapshot (Mode A 依賴)
    take_heart_layer_snapshot(db, visit, "before_visit")

    # Phase 4.2c: 一起寫 ai_drafts (status='accepted_with_visit')
    drafts_saved = 0
    if payload.ai_drafts:
        allowed_agents = {"intake", "triage", "audit", "education"}
        for d in payload.ai_drafts:
            if d.agent_type not in allowed_agents:
                continue
            draft = AiDraft(
                id=uuid4(),
                clinic_id=patient.clinic_id,
                patient_id=patient.id,
                visit_id=visit_uuid,
                agent_type=d.agent_type,
                payload_json=d.payload,
                status="accepted_with_visit",
                accepted_at=vdate,
                source="manual",
                is_demo_data=False,
            )
            db.add(draft)
            drafts_saved += 1

    # 再 flush 確保 ai_drafts 在 evolve_heart_layer 撈得到
    db.flush()

    # Phase 7.3/7.4: 寫 Prescription + PrescriptionItem
    # 優先用結構化 prescription_items (form UI), fallback 用 prescription_lines (textarea parse)
    rx_saved = 0
    rx_unmatched: list[str] = []
    has_rx = bool(payload.prescription_items) or bool(payload.prescription_lines)
    if has_rx:
        rx_obj = Prescription(
            id=uuid4(),
            clinic_id=patient.clinic_id,
            visit_id=visit_uuid,
            status="dispensed",
            source="manual",
            is_demo_data=False,
        )
        db.add(rx_obj)
        db.flush()

        # 主途徑: 結構化 items (drug_id 已選定)
        for item in payload.prescription_items or []:
            drug = db.get(Drug, item.drug_id)
            if not drug:
                rx_unmatched.append(f"unknown drug_id {item.drug_id}")
                continue
            total_qty = max(1, int(item.daily_dose * item.days))
            db.add(PrescriptionItem(
                id=uuid4(),
                clinic_id=patient.clinic_id,
                prescription_id=rx_obj.id,
                drug_id=drug.id,
                usage_text=item.usage_text or f"{drug.name} ×{item.days}D",
                daily_dose=item.daily_dose,
                days=item.days,
                total_quantity=total_qty,
                unit_price_at_time=drug.unit_price or 0,
                total_price=(drug.unit_price or 0) * total_qty,
                source="manual",
                is_demo_data=False,
            ))
            rx_saved += 1

        # Fallback: textarea raw lines (parse drug + dose)
        if payload.prescription_lines:
            drug_kw_map = _build_drug_keyword_map(db)
            for raw_line in payload.prescription_lines:
                if not raw_line.strip():
                    continue
                drug, usage_text, daily_dose, days = _parse_rx_line(raw_line.strip(), drug_kw_map)
                if not drug:
                    rx_unmatched.append(raw_line.strip())
                    continue
                total_qty = max(1, int(daily_dose * days))
                db.add(PrescriptionItem(
                    id=uuid4(),
                    clinic_id=patient.clinic_id,
                    prescription_id=rx_obj.id,
                    drug_id=drug.id,
                    usage_text=usage_text,
                    daily_dose=daily_dose,
                    days=days,
                    total_quantity=total_qty,
                    unit_price_at_time=drug.unit_price or 0,
                    total_price=(drug.unit_price or 0) * total_qty,
                    source="manual",
                    is_demo_data=False,
                ))
                rx_saved += 1

        if rx_saved == 0:
            db.delete(rx_obj)
        db.flush()

    # Phase 5: visit 完成時自動演進心臟層 (problems / medications / flags / baselines)
    evolution = evolve_heart_layer_after_visit(db, visit)

    # Phase 6.1: evolve 完之後拍 after_visit snapshot
    db.flush()  # 確保 evolve 寫入的 4 心臟表新條目可被 serialize 撈到
    take_heart_layer_snapshot(db, visit, "after_visit")

    db.commit()

    return NewVisitResponse(
        visit_id=visit_uuid,
        patient_id=patient.id,
        visit_date=vdate.isoformat(),
        status="completed",
        ai_drafts_saved=drafts_saved,
        prescription_items_saved=rx_saved,
        prescription_items_unmatched=rx_unmatched,
        heart_evolution=HeartEvolutionSummary(
            problems_added=evolution.problems_added,
            medications_added=evolution.medications_added,
            flags_added=evolution.flags_added,
            flags_upgraded=evolution.flags_upgraded,
            baselines_added=evolution.baselines_added,
        ),
    )
