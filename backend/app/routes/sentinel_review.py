"""
============================================================
routes/sentinel_review.py -- Phase 6 Mode A/B 舊就診回顧
============================================================
Track 1 MemoryAgent 主秀 endpoint。對任何既有 visit 觸發 4 sentinel
agent 重跑, 兩種 mode 切換:

- Mode A (at_the_time): 用 before_visit snapshot 重建當時心臟層, AI
  模擬「當時可獲得的資訊」做分析, 找出當時就該想到的盲點
- Mode B (hindsight)  : 用當下心臟層 (含後續演進) 餵 AI, 配 hindsight
  bias disclaimer「不代表當時判斷有錯」

實作鐵律 (v0.3.1 §8.1):
- 不改 4 agent 內部 prompt, 純資料驅動 (餵不同 heart layer)
- prompt 不變 -> agent 自然會用 snapshot flag/problem 跑 audit
- mode_note 加在 closing_note 而非 prompt, 避免污染 agent 邏輯
- 每個 agent 是 best-effort, 缺資料 (e.g. 沒藥名) skip 該 agent

Endpoint:
- POST /v1/sentinel/visits/{visit_id}/review?mode=at_the_time|hindsight

Response:
- mode + heart_layer_source ('snapshot:before_visit'/'fallback:current')
- 4 agent panel (intake/triage/audit/education, 可能 null 若 skip)
- mode_disclaimer
============================================================
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import (
    run_intake_agent,
    run_triage_agent,
    run_audit_agent,
    run_education_agent,
)
from app.core.database import SessionLocal
from app.models import (
    AiDraft,
    Drug,
    Prescription,
    PrescriptionItem,
    Visit,
    VisitExamination,
)
from app.schemas.sentinel import (
    AuditRequest,
    AuditResponse,
    EducationRequest,
    EducationResponse,
    HeartFlag,
    HeartMedication,
    HeartProblem,
    IntakeRequest,
    IntakeResponse,
    TriageRequest,
    TriageResponse,
)
from app.services.heart_evolution import load_heart_layer_at_visit

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_past_visits_summary(db: Session, patient_id, target_visit_date) -> str:
    """撈 target_visit_date 之前的所有 visit, 摘要成 plain text 注入 AI context.

    司機 6/28 反饋: Mode A 不只該注入當次, 也該注入歷次 visit (dx + Rx),
    AI 才會知道 「病人之前就講過高血壓」.
    """
    visits = db.scalars(
        select(Visit)
        .where(
            Visit.patient_id == patient_id,
            Visit.visit_date < target_visit_date,
        )
        .order_by(Visit.visit_date)
    ).all()
    if not visits:
        return ""

    lines = ["【病人過去就診歷史 (按時序由早到近)】"]
    for v in visits:
        rx_rows = db.execute(
            select(Drug.name, PrescriptionItem.usage_text, PrescriptionItem.days)
            .join(PrescriptionItem, PrescriptionItem.drug_id == Drug.id)
            .join(Prescription, Prescription.id == PrescriptionItem.prescription_id)
            .where(Prescription.visit_id == v.id)
        ).all()
        rx_parts = [f"{r[0]} ({r[1] or ''}{'×'+str(r[2])+'D' if r[2] else ''})" for r in rx_rows]
        rx_text = ", ".join(rx_parts) if rx_parts else "(無處方)"
        parts = [f"- {v.visit_date.date()}"]
        if v.chief_complaint:
            parts.append(f"主訴 {v.chief_complaint}")
        if v.diagnosis:
            parts.append(f"診斷: {v.diagnosis}")
        parts.append(f"Rx: {rx_text}")
        lines.append(" / ".join(parts))

    return "\n".join(lines)


# ============================================================
# snapshot -> pydantic HeartFlag/Problem/Medication mapper
# ============================================================
# schema enum 跟 model enum 命名不一致, mapper 做安全 fallback:
# - HeartFlag.source: 只允許 self_report/verified/authoritative
#   inferred_from_visit -> self_report
# - HeartProblem.control_status: 只允許 controlled/unstable/worsening/None
#   active/unknown/resolved -> None
# - HeartMedication.category: 只允許 chronic_disease_med/supplement/tcm
#   long_term/short_term/prn -> chronic_disease_med (語意最接近)

_FLAG_SOURCE_MAP = {
    "self_report": "self_report",
    "verified": "verified",
    "authoritative": "authoritative",
    "inferred_from_visit": "self_report",
}
_FLAG_TYPE_VALID = {
    "allergy", "pregnancy", "major_history",
    "medical_directive", "interaction_note", "origin",
}
_CONTROL_STATUS_MAP = {
    "controlled": "controlled",
    "unstable": "unstable",
    "worsening": "worsening",
}
_MED_CATEGORY_MAP = {
    "chronic_disease_med": "chronic_disease_med",
    "supplement": "supplement",
    "tcm": "tcm",
    "long_term": "chronic_disease_med",
    "short_term": "chronic_disease_med",
    "prn": "chronic_disease_med",
}


def _map_flags(flags_json: list[dict]) -> list[HeartFlag]:
    out = []
    for f in flags_json:
        ftype = f.get("flag_type", "interaction_note")
        if ftype not in _FLAG_TYPE_VALID:
            ftype = "interaction_note"
        try:
            out.append(HeartFlag(
                type=ftype,
                content=f.get("content", ""),
                severity=f.get("severity") if f.get("severity") in {"red", "yellow", "info"} else None,
                source=_FLAG_SOURCE_MAP.get(f.get("flag_source"), "self_report"),
                valid_until=f.get("valid_until"),
            ))
        except Exception as e:
            logger.warning("skip flag mapping: %s (%s)", e, f)
    return out


def _map_problems(problems_json: list[dict]) -> list[HeartProblem]:
    out = []
    for p in problems_json:
        try:
            out.append(HeartProblem(
                name=p.get("problem_name", ""),
                diagnosed_at=p.get("diagnosed_at"),
                control_status=_CONTROL_STATUS_MAP.get(p.get("control_status")),
                medications=[],
            ))
        except Exception as e:
            logger.warning("skip problem mapping: %s (%s)", e, p)
    return out


def _map_medications(meds_json: list[dict]) -> list[HeartMedication]:
    out = []
    for m in meds_json:
        if not m.get("is_active", True):
            continue
        try:
            out.append(HeartMedication(
                name=m.get("medication_name", ""),
                category=_MED_CATEGORY_MAP.get(m.get("category"), "chronic_disease_med"),
                composition_certain=True,
                for_problem=None,
            ))
        except Exception as e:
            logger.warning("skip medication mapping: %s (%s)", e, m)
    return out


# ============================================================
# Response schema
# ============================================================
class ReviewMode(BaseModel):
    """前端 ReviewResponse 對應的 mode 識別。"""
    mode: Literal["at_the_time", "hindsight"]
    heart_layer_source: str   # 'snapshot:before_visit' / 'snapshot:after_visit' / 'fallback:current'
    summary_text: str         # snapshot.summary_text (給 UI 顯示「當時的心臟層狀態」)


class ReviewResponse(BaseModel):
    """4 agent 全跑完一次的回顧 panel."""
    model_config = ConfigDict(protected_namespaces=())

    visit_id: UUID
    mode: ReviewMode
    intake: IntakeResponse | None = None
    triage: TriageResponse | None = None
    audit: AuditResponse | None = None
    education: EducationResponse | None = None
    skipped: list[str] = Field(default_factory=list)   # 哪些 agent skip 了 + 原因
    mode_disclaimer: str = ""


class ReviewRequest(BaseModel):
    mode: Literal["at_the_time", "hindsight"] = "at_the_time"


# ============================================================
# Endpoint
# ============================================================
@router.post("/sentinel/visits/{visit_id}/review", response_model=ReviewResponse)
async def review_visit(
    visit_id: UUID,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
):
    """Phase 6 Mode A/B 舊就診回顧.

    Mode A (at_the_time): 餵 before_visit snapshot heart layer 給 4 agent
    Mode B (hindsight)  : 餵 current/after_visit snapshot heart layer
    """
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=f"Visit {visit_id} not found")

    # 拿心臟層 (snapshot or fallback)
    if payload.mode == "at_the_time":
        heart = load_heart_layer_at_visit(db, visit, prefer="before_visit")
    else:  # hindsight
        heart = load_heart_layer_at_visit(db, visit, prefer="after_visit")

    # 司機 6/28: 撈 target_visit 之前的所有 visit 摘要, 注入 AI context
    past_visits_summary = _build_past_visits_summary(db, visit.patient_id, visit.visit_date)

    flags = _map_flags(heart["flags_json"])
    problems = _map_problems(heart["problems_json"])
    medications = _map_medications(heart["medications_json"])

    # 拿該 visit 的 ai_drafts (Mode A/B 重跑 audit 要用 new_prescription)
    drafts = db.scalars(
        select(AiDraft).where(AiDraft.visit_id == visit.id)
    ).all()
    drafts_by_agent = {d.agent_type: d.payload_json for d in drafts}

    # 拿該 visit examination (vital signs 給 intake 看)
    exam = db.scalars(
        select(VisitExamination).where(VisitExamination.visit_id == visit.id)
    ).first()

    # 並行跑 4 agent (best-effort, 缺資料 skip)
    skipped: list[str] = []

    # --- intake: raw_dictation = chief_complaint + hpi (+ vital 摘要)
    dictation_parts = []
    if visit.chief_complaint:
        dictation_parts.append(f"主訴: {visit.chief_complaint}")
    if visit.hpi:
        dictation_parts.append(f"現病史: {visit.hpi}")
    if exam and exam.vital_signs_json:
        vs = exam.vital_signs_json
        if vs.get("blood_pressure_systolic"):
            dictation_parts.append(
                f"BP {vs['blood_pressure_systolic']}/{vs.get('blood_pressure_diastolic', '?')} mmHg"
            )
        if vs.get("heart_rate"):
            dictation_parts.append(f"HR {vs['heart_rate']} bpm")
    intake_req: IntakeRequest | None = None
    if dictation_parts:
        current_dictation = " / ".join(dictation_parts)
        # 注入歷次 visit 摘要 (司機 6/28 反饋)
        if past_visits_summary:
            current_dictation = (
                past_visits_summary
                + "\n\n【本次就診主訴 + 檢查】\n"
                + current_dictation
            )
        intake_req = IntakeRequest(
            raw_dictation=current_dictation,
            chief_complaint_hint=visit.chief_complaint,
            patient_id=visit.patient_id,
            visit_id=visit.id,
        )
    else:
        skipped.append("intake (no dictation source)")

    # --- triage: working_hypothesis = diagnosis (或 fallback chief_complaint)
    triage_req: TriageRequest | None = None
    hypothesis = visit.diagnosis or visit.chief_complaint
    if hypothesis:
        # 注入歷次 visit 摘要 (司機 6/28 反饋)
        full_hypothesis = hypothesis
        if past_visits_summary:
            full_hypothesis = (
                f"本次工作假設: {hypothesis}\n\n"
                + past_visits_summary
            )
        triage_req = TriageRequest(
            working_hypothesis=full_hypothesis,
            flags=flags,
            problems=problems,
            medications=medications,
            patient_id=visit.patient_id,
            visit_id=visit.id,
        )
    else:
        skipped.append("triage (no hypothesis/dx)")

    # --- audit: new_prescription = audit panel 拆出的藥名 (Phase 5 evolve 同邏輯)
    audit_req: AuditRequest | None = None
    drug_names: list[str] = []
    audit_payload = drafts_by_agent.get("audit")
    if audit_payload:
        seen = set()
        for f in audit_payload.get("rule_engine_findings", []) or []:
            if isinstance(f, dict):
                for k in ("drug_a", "drug_b"):
                    v = f.get(k)
                    if v and v not in seen:
                        seen.add(v)
                        drug_names.append(v)
        for r in audit_payload.get("contextual_risks", []) or []:
            if isinstance(r, dict) and r.get("drug") and r["drug"] not in seen:
                seen.add(r["drug"])
                drug_names.append(r["drug"])
    if drug_names:
        audit_req = AuditRequest(
            new_prescription=drug_names,
            flags=flags,
            long_term_medications=medications,
            problems=problems,
            patient_id=visit.patient_id,
            visit_id=visit.id,
        )
    else:
        skipped.append("audit (no prescription in ai_drafts)")

    # --- education: diagnosis (空就 skip)
    education_req: EducationRequest | None = None
    if visit.diagnosis:
        education_req = EducationRequest(
            diagnosis=visit.diagnosis,
            patient_habits={},
            patient_name_hint=None,
            patient_id=visit.patient_id,
            visit_id=visit.id,
        )
    else:
        skipped.append("education (no diagnosis)")

    # 並行跑
    async def _safe(name: str, coro):
        try:
            return await coro
        except Exception as e:
            logger.exception("[review] %s failed", name)
            skipped.append(f"{name} (agent error: {type(e).__name__})")
            return None

    coros = []
    coros.append(_safe("intake", run_intake_agent(intake_req)) if intake_req else _noop())
    coros.append(_safe("triage", run_triage_agent(triage_req)) if triage_req else _noop())
    coros.append(_safe("audit", run_audit_agent(audit_req)) if audit_req else _noop())
    coros.append(_safe("education", run_education_agent(education_req)) if education_req else _noop())

    intake_res, triage_res, audit_res, education_res = await asyncio.gather(*coros)

    # mode_note 加進 closing_note
    if payload.mode == "at_the_time":
        disclaimer = (
            "Mode A — 當時可獲得的資訊重審。AI 模擬該 visit 開始時的心臟層狀態, "
            "嘗試找出當時就該想到的盲點 (教育用途)."
        )
    else:
        disclaimer = (
            "Mode B — 事後諸葛回顧。AI 看當下完整心臟層 (含後續演進), "
            "指出後續發展揭示的當時盲點。但這不代表當時判斷有錯 — 當時可獲得的資訊有限, "
            "這是用後見之明做教育、不是究責."
        )

    return ReviewResponse(
        visit_id=visit.id,
        mode=ReviewMode(
            mode=payload.mode,
            heart_layer_source=heart.get("source", "unknown"),
            summary_text=heart.get("summary_text", ""),
        ),
        intake=intake_res,
        triage=triage_res,
        audit=audit_res,
        education=education_res,
        skipped=skipped,
        mode_disclaimer=disclaimer,
    )


async def _noop():
    return None
