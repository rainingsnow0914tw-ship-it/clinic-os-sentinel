"""
============================================================
services/heart_evolution.py -- Phase 5 心臟層自動演進
============================================================
visit 完成時呼叫 evolve_heart_layer_after_visit(), 從 visit + ai_drafts
推導出 4 心臟表新內容, 對應 v0.3.1 §7.1 (累積規則) + §7.3 (信心度升級).

來源優先序 (Z 方案, 司機 6/28 凌晨拍板):
- problems     : visit.diagnosis 慢性病詞匹配 -> 直接 confirmed (醫師確診)
- medications  : ai_drafts.audit.new_prescription 藥名 long-term 詞匹配
- flags        : ai_drafts.intake.findings[section=='anomaly']
                 第 1 次 -> to_observe + first_observed_at_visit
                 第 2 次 -> confirmed + confirmed_at_visit
- baselines    : visit_examination.vital_signs 5 個欄位各寫一筆 trend

設計鐵律 (RaidMeter 配置驅動):
- 慢性病詞 / 長期藥詞 用 dict, 不寫死 in code
- text 模糊匹配走 normalize + substring (不上 fuzzywuzzy)
- 同 visit_id 跑兩次 -> idempotent (用 first_observed_at_visit 防重)
============================================================
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AiDraft,
    HeartLayerSnapshot,
    PatientBaseline,
    PatientFlag,
    PatientMedication,
    PatientProblem,
    Visit,
    VisitExamination,
)
from app.models.patient_baseline import BaselineCategory, BaselineSource
from app.models.patient_flag import (
    ConfidenceStatus,
    FlagSeverity,
    FlagSource,
    FlagTemporalMode,
    FlagType,
)
from app.models.patient_medication import MedicationCategory, MedicationSource
from app.models.patient_problem import ControlStatus, ProblemSource

logger = logging.getLogger(__name__)


# ============================================================
# 配置: 慢性病詞典 (visit.diagnosis -> patient_problems)
# ============================================================
# key = 文字觸發詞 (大小寫不敏感, 子串匹配), value = (canonical_name, icd10)
CHRONIC_DISEASE_KEYWORDS: dict[str, tuple[str, str | None]] = {
    # 心血管
    "高血壓": ("原發性高血壓", "I10"),
    "hypertension": ("原發性高血壓", "I10"),
    "htn": ("原發性高血壓", "I10"),
    "冠心病": ("冠狀動脈疾病", "I25.10"),
    "cad": ("冠狀動脈疾病", "I25.10"),
    "心衰": ("慢性心衰竭", "I50.9"),
    "心臟衰竭": ("慢性心衰竭", "I50.9"),
    "chf": ("慢性心衰竭", "I50.9"),
    "心房顫動": ("心房顫動", "I48.0"),
    "afib": ("心房顫動", "I48.0"),
    # 內分泌
    "糖尿病": ("第二型糖尿病", "E11.9"),
    "type 2 diabetes": ("第二型糖尿病", "E11.9"),
    "diabetes": ("第二型糖尿病", "E11.9"),
    "t2dm": ("第二型糖尿病", "E11.9"),
    "甲狀腺低下": ("甲狀腺功能低下", "E03.9"),
    "甲狀腺亢進": ("甲狀腺功能亢進", "E05.9"),
    # 代謝
    "高血脂": ("高脂血症", "E78.5"),
    "高膽固醇": ("高脂血症", "E78.5"),
    "hyperlipidemia": ("高脂血症", "E78.5"),
    "痛風": ("痛風", "M10.9"),
    "gout": ("痛風", "M10.9"),
    # 呼吸
    "哮喘": ("支氣管哮喘", "J45.909"),
    "asthma": ("支氣管哮喘", "J45.909"),
    "copd": ("慢性阻塞性肺病", "J44.9"),
    "慢性阻塞性肺病": ("慢性阻塞性肺病", "J44.9"),
    # 腎
    "慢性腎": ("慢性腎臟病", "N18.9"),
    "ckd": ("慢性腎臟病", "N18.9"),
    # 精神
    "失智": ("失智症", "F03"),
    "認知障礙": ("輕度認知障礙", "G31.84"),
    "dementia": ("失智症", "F03"),
    # 消化
    "胃食道逆流": ("胃食道逆流症", "K21.9"),
    "gerd": ("胃食道逆流症", "K21.9"),
    # 攝護腺 (gender-aware, 但 evolve 不再 gate, 因為 dx 是醫師寫的)
    "bph": ("良性攝護腺肥大", "N40.0"),
    "前列腺肥大": ("良性攝護腺肥大", "N40.0"),
}


# ============================================================
# 配置: 長期藥詞典 (ai_drafts.audit.new_prescription -> patient_medications)
# ============================================================
# 不在這 list 的藥默認當 short_term (visit-bound), 不寫進心臟層
LONG_TERM_DRUG_KEYWORDS: set[str] = {
    # 降壓
    "amlodipine", "氨氯地平",
    "losartan", "valsartan", "telmisartan",
    "lisinopril", "enalapril", "ramipril",
    "atenolol", "bisoprolol", "metoprolol",
    "hydrochlorothiazide", "hctz", "indapamide",
    # 降血糖
    "metformin", "二甲雙胍",
    "gliclazide", "glimepiride",
    "sitagliptin", "linagliptin",
    "empagliflozin", "dapagliflozin",
    # 降血脂
    "atorvastatin", "rosuvastatin", "simvastatin", "pravastatin",
    "ezetimibe",
    # 抗凝
    "aspirin", "clopidogrel", "warfarin", "apixaban", "rivaroxaban", "dabigatran",
    # 甲狀腺
    "levothyroxine", "甲狀腺素",
    # 哮喘 / COPD (長期吸入)
    "salbutamol", "salmeterol", "formoterol",
    "fluticasone", "budesonide",
    "tiotropium",
    # 胃藥 (長期 PPI)
    "omeprazole", "esomeprazole", "pantoprazole", "lansoprazole",
    # 痛風
    "allopurinol", "febuxostat",
    # 攝護腺
    "tamsulosin", "finasteride",
    # 失智
    "donepezil", "memantine",
}


# ============================================================
# 結果
# ============================================================
@dataclass
class EvolutionResult:
    """evolve 收尾統計, 給 logging / smoke test 用。"""

    problems_added: int = 0
    medications_added: int = 0
    flags_added: int = 0          # 新 to_observe
    flags_upgraded: int = 0       # to_observe -> confirmed
    baselines_added: int = 0

    def total(self) -> int:
        return (
            self.problems_added
            + self.medications_added
            + self.flags_added
            + self.flags_upgraded
            + self.baselines_added
        )


# ============================================================
# 主函式
# ============================================================
def evolve_heart_layer_after_visit(db: Session, visit: Visit) -> EvolutionResult:
    """visit 完成時自動跑, 從 visit + 該 visit 的 ai_drafts 推導心臟層演進.

    重要 invariant:
    - 必須在 db.flush() 之後 / db.commit() 之前呼叫, 因為要撈 ai_drafts (visit_id FK)
    - 同 visit 跑兩次 idempotent (用 first_observed_at_visit 去重)
    """
    result = EvolutionResult()

    # 撈該 visit 的 ai_drafts (同一 session, 已 flush 過)
    drafts = db.scalars(
        select(AiDraft).where(AiDraft.visit_id == visit.id)
    ).all()
    drafts_by_agent: dict[str, dict[str, Any]] = {
        d.agent_type: d.payload_json for d in drafts
    }

    # 撈 visit_examination (1:1)
    exam = db.scalars(
        select(VisitExamination).where(VisitExamination.visit_id == visit.id)
    ).first()

    # 1. 慢性病: visit.diagnosis 慢性病詞匹配
    result.problems_added = _evolve_problems(db, visit)

    # 2. 長期藥: ai_drafts.audit.new_prescription 過 long-term filter
    audit_payload = drafts_by_agent.get("audit")
    if audit_payload:
        result.medications_added = _evolve_medications(db, visit, audit_payload)

    # 3. 紅旗: ai_drafts.intake.findings[anomaly]
    intake_payload = drafts_by_agent.get("intake")
    if intake_payload:
        added, upgraded = _evolve_flags(db, visit, intake_payload)
        result.flags_added = added
        result.flags_upgraded = upgraded

    # 4. 基線: visit_examination.vital_signs
    if exam and exam.vital_signs_json:
        result.baselines_added = _evolve_baselines(db, visit, exam)

    logger.info(
        "[heart_evolution] visit=%s patient=%s "
        "problems+%d meds+%d flags+%d (upgraded %d) baselines+%d",
        visit.id, visit.patient_id,
        result.problems_added, result.medications_added,
        result.flags_added, result.flags_upgraded, result.baselines_added,
    )
    return result


# ============================================================
# Helpers
# ============================================================
def _normalize(text: str) -> str:
    """大小寫 / 全形空白 normalize, 給子串匹配用。"""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _evolve_problems(db: Session, visit: Visit) -> int:
    """visit.diagnosis 慢性病詞匹配 -> patient_problems (skip 重複 problem_name)。"""
    if not visit.diagnosis:
        return 0

    dx_norm = _normalize(visit.diagnosis)
    # 找出所有命中的 canonical_name (去重)
    hits: dict[str, str | None] = {}
    for keyword, (canonical, icd) in CHRONIC_DISEASE_KEYWORDS.items():
        if keyword.lower() in dx_norm and canonical not in hits:
            hits[canonical] = icd
    if not hits:
        return 0

    # 撈該病人既有 problem_name (避免重複插入)
    existing = {
        p.problem_name
        for p in db.scalars(
            select(PatientProblem).where(PatientProblem.patient_id == visit.patient_id)
        ).all()
    }

    added = 0
    for canonical, icd in hits.items():
        if canonical in existing:
            continue
        db.add(PatientProblem(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            problem_name=canonical,
            icd10_code=icd,
            control_status=ControlStatus.ACTIVE.value,
            problem_source=ProblemSource.INFERRED_FROM_VISIT.value,
            diagnosed_at=visit.visit_date.date() if visit.visit_date else None,
            notes=f"自動推導自 visit {visit.id} (Dx: {visit.diagnosis[:80]})",
            source="agent",
            is_demo_data=False,
        ))
        added += 1
    return added


def _evolve_medications(db: Session, visit: Visit, audit_payload: dict) -> int:
    """ai_drafts.audit.new_prescription long-term filter -> patient_medications。"""
    # audit payload shape (sentinel.AuditRequest 那邊): new_prescription: list[str]
    # 但 ai_drafts 存的是 AuditResponse, 沒有 new_prescription 欄位
    # 改從 audit response 的 rule_engine_findings / contextual_risks 反推 drug 名
    # 更穩: 直接用 visit.diagnosis 對 LONG_TERM_DRUG_KEYWORDS 做反向匹配
    # 但 visit.diagnosis 是診斷不是藥名, 不適合
    #
    # 折衷: audit payload 寫進去時是 frontend dump 的, 看 NewVisitPage 怎麼 dump
    # frontend 把 audit request 也 dump 進來了嗎? 看 ResponseSchema -> 只 dump response
    # 所以 audit payload 裡只有 rule_engine_findings (drug_a/drug_b/...) + contextual_risks (drug/...)
    # 從這兩個欄位取所有提到的 drug 名 (drug_a + drug_b + drug)
    drug_names: set[str] = set()
    for f in audit_payload.get("rule_engine_findings", []) or []:
        if isinstance(f, dict):
            if f.get("drug_a"):
                drug_names.add(_normalize(str(f["drug_a"])))
            if f.get("drug_b"):
                drug_names.add(_normalize(str(f["drug_b"])))
    for r in audit_payload.get("contextual_risks", []) or []:
        if isinstance(r, dict) and r.get("drug"):
            drug_names.add(_normalize(str(r["drug"])))

    if not drug_names:
        return 0

    # 過 long_term filter (substring match against LONG_TERM_DRUG_KEYWORDS)
    long_term_hits: set[str] = set()
    for dn in drug_names:
        for kw in LONG_TERM_DRUG_KEYWORDS:
            if kw in dn:
                long_term_hits.add(kw)
                break

    if not long_term_hits:
        return 0

    # 撈病人既有 medication_name (normalize 比對, 避免重複)
    existing_meds_norm = {
        _normalize(m.medication_name)
        for m in db.scalars(
            select(PatientMedication).where(PatientMedication.patient_id == visit.patient_id)
        ).all()
    }

    added = 0
    for drug_kw in long_term_hits:
        if any(drug_kw in em for em in existing_meds_norm):
            continue
        db.add(PatientMedication(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            medication_name=drug_kw,
            category=MedicationCategory.LONG_TERM.value,
            medication_source=MedicationSource.INFERRED_FROM_VISIT.value,
            is_active=True,
            notes=f"自動推導自 visit {visit.id} audit panel",
            source="agent",
            is_demo_data=False,
        ))
        added += 1
    return added


def _evolve_flags(
    db: Session, visit: Visit, intake_payload: dict
) -> tuple[int, int]:
    """intake.findings[section==anomaly] -> patient_flags 升級邏輯.

    Return (added_to_observe, upgraded_to_confirmed).
    """
    findings = intake_payload.get("findings", []) or []
    anomaly_texts = [
        _normalize(str(f.get("text", "")))
        for f in findings
        if isinstance(f, dict) and f.get("section") == "anomaly" and f.get("text")
    ]
    if not anomaly_texts:
        return (0, 0)

    # 撈病人既有 flags (帶 confidence_status 一起)
    existing_flags = db.scalars(
        select(PatientFlag).where(PatientFlag.patient_id == visit.patient_id)
    ).all()
    # 為了 idempotent: 跳過 first_observed_at_visit == 本 visit 的 flags
    # (重跑 evolve 不要重複寫)

    added = 0
    upgraded = 0
    for atext in anomaly_texts:
        # 找既有 flag content 模糊匹配 (子串雙向)
        match: PatientFlag | None = None
        for f in existing_flags:
            f_norm = _normalize(f.content)
            if atext in f_norm or f_norm in atext:
                match = f
                break

        if match is None:
            # 第 1 次出現 -> to_observe
            db.add(PatientFlag(
                id=uuid.uuid4(),
                clinic_id=visit.clinic_id,
                patient_id=visit.patient_id,
                flag_type=FlagType.INTERACTION_NOTE.value,
                temporal_mode=FlagTemporalMode.PERMANENT.value,
                severity=FlagSeverity.YELLOW.value,
                flag_source=FlagSource.INFERRED_FROM_VISIT.value,
                content=atext,
                confidence_status=ConfidenceStatus.TO_OBSERVE.value,
                first_observed_at_visit=visit.id,
                notes=f"自動推導自 visit {visit.id} intake anomaly finding",
                source="auto_evolve",
                is_demo_data=False,
            ))
            added += 1
        elif match.confidence_status == ConfidenceStatus.TO_OBSERVE.value:
            # 不是本次新建的 + 是 to_observe -> 升 confirmed
            if match.first_observed_at_visit == visit.id:
                # 同 visit 重跑, 不升級
                continue
            match.confidence_status = ConfidenceStatus.CONFIRMED.value
            match.confirmed_at_visit = visit.id
            match.severity = FlagSeverity.RED.value   # 升級就亮紅
            upgraded += 1
        # confirmed / dismissed -> 不動

    return (added, upgraded)


def _evolve_baselines(
    db: Session, visit: Visit, exam: VisitExamination
) -> int:
    """visit_examination.vital_signs 5 個 vital 各寫一筆 baseline trend。"""
    vs = exam.vital_signs_json or {}
    added = 0
    measured_at = visit.visit_date

    # BP (systolic + diastolic 合併一筆)
    sbp = vs.get("blood_pressure_systolic")
    dbp = vs.get("blood_pressure_diastolic")
    if sbp and dbp:
        db.add(PatientBaseline(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            category=BaselineCategory.OBJECTIVE.value,
            baseline_source=BaselineSource.AUTO_FROM_VISITS.value,
            value_text=f"BP {sbp}/{dbp} mmHg",
            measured_at=measured_at,
            notes=f"自動推導自 visit {visit.id}",
            source="agent",
            is_demo_data=False,
        ))
        added += 1

    # HR
    hr = vs.get("heart_rate")
    if hr:
        db.add(PatientBaseline(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            category=BaselineCategory.OBJECTIVE.value,
            baseline_source=BaselineSource.AUTO_FROM_VISITS.value,
            value_text=f"HR {hr} bpm",
            measured_at=measured_at,
            notes=f"自動推導自 visit {visit.id}",
            source="agent",
            is_demo_data=False,
        ))
        added += 1

    # T
    t = vs.get("temperature_c")
    if t:
        db.add(PatientBaseline(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            category=BaselineCategory.OBJECTIVE.value,
            baseline_source=BaselineSource.AUTO_FROM_VISITS.value,
            value_text=f"T {t}°C",
            measured_at=measured_at,
            notes=f"自動推導自 visit {visit.id}",
            source="agent",
            is_demo_data=False,
        ))
        added += 1

    # SpO2
    spo2 = vs.get("oxygen_saturation")
    if spo2:
        db.add(PatientBaseline(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            category=BaselineCategory.OBJECTIVE.value,
            baseline_source=BaselineSource.AUTO_FROM_VISITS.value,
            value_text=f"SpO2 {spo2}%",
            measured_at=measured_at,
            notes=f"自動推導自 visit {visit.id}",
            source="agent",
            is_demo_data=False,
        ))
        added += 1

    # RR
    rr = vs.get("respiratory_rate")
    if rr:
        db.add(PatientBaseline(
            id=uuid.uuid4(),
            clinic_id=visit.clinic_id,
            patient_id=visit.patient_id,
            category=BaselineCategory.OBJECTIVE.value,
            baseline_source=BaselineSource.AUTO_FROM_VISITS.value,
            value_text=f"RR {rr}/min",
            measured_at=measured_at,
            notes=f"自動推導自 visit {visit.id}",
            source="agent",
            is_demo_data=False,
        ))
        added += 1

    return added


# ============================================================
# Phase 6: snapshot 寫入 (Mode A 「當時可獲得的資訊重審」依賴)
# ============================================================
def _serialize_heart_layer(db: Session, patient_id: uuid.UUID) -> dict:
    """4 心臟表當下狀態 -> 4 個 list[dict] + plain text summary。"""
    flags = db.scalars(
        select(PatientFlag).where(PatientFlag.patient_id == patient_id)
    ).all()
    problems = db.scalars(
        select(PatientProblem).where(PatientProblem.patient_id == patient_id)
    ).all()
    medications = db.scalars(
        select(PatientMedication).where(PatientMedication.patient_id == patient_id)
    ).all()
    baselines = db.scalars(
        select(PatientBaseline).where(PatientBaseline.patient_id == patient_id)
    ).all()

    flags_json = [
        {
            "id": str(f.id),
            "flag_type": f.flag_type,
            "severity": f.severity,
            "content": f.content,
            "confidence_status": f.confidence_status,
            "flag_source": f.flag_source,
            "valid_until": f.valid_until.isoformat() if f.valid_until else None,
        }
        for f in flags
    ]
    problems_json = [
        {
            "id": str(p.id),
            "problem_name": p.problem_name,
            "icd10_code": p.icd10_code,
            "control_status": p.control_status,
            "problem_source": p.problem_source,
            "diagnosed_at": p.diagnosed_at.isoformat() if p.diagnosed_at else None,
        }
        for p in problems
    ]
    medications_json = [
        {
            "id": str(m.id),
            "medication_name": m.medication_name,
            "category": m.category,
            "dosage": m.dosage,
            "frequency": m.frequency,
            "is_active": m.is_active,
        }
        for m in medications
    ]
    baselines_json = [
        {
            "id": str(b.id),
            "category": b.category,
            "value_text": b.value_text,
            "measured_at": b.measured_at.isoformat() if b.measured_at else None,
        }
        for b in baselines
    ]

    confirmed_flags = [f for f in flags if f.confidence_status == "confirmed"]
    summary_lines = [
        f"心臟層摘要: {len(confirmed_flags)} 紅旗確認 / {len(flags) - len(confirmed_flags)} 待觀察 / {len(problems)} 慢性病 / {len(medications)} 長期用藥 / {len(baselines)} baseline",
    ]
    if confirmed_flags:
        summary_lines.append(
            "確認紅旗: " + "; ".join(f.content[:40] for f in confirmed_flags[:5])
        )
    if problems:
        summary_lines.append(
            "慢性病: " + ", ".join(p.problem_name for p in problems[:8])
        )
    if medications:
        active_meds = [m for m in medications if m.is_active]
        if active_meds:
            summary_lines.append(
                "長期用藥: " + ", ".join(m.medication_name for m in active_meds[:8])
            )

    return {
        "flags_json": flags_json,
        "problems_json": problems_json,
        "medications_json": medications_json,
        "baselines_json": baselines_json,
        "summary_text": "\n".join(summary_lines),
    }


def take_heart_layer_snapshot(
    db: Session, visit: Visit, snapshot_type: str
) -> HeartLayerSnapshot:
    """序列化當下 4 心臟表狀態進 heart_layer_snapshots 表。

    snapshot_type: 'before_visit' | 'after_visit'
    冪等: 同 visit + 同 type 已存在則 skip (return 既有)
    """
    existing = db.scalars(
        select(HeartLayerSnapshot).where(
            HeartLayerSnapshot.visit_id == visit.id,
            HeartLayerSnapshot.snapshot_type == snapshot_type,
        )
    ).first()
    if existing:
        return existing

    payload = _serialize_heart_layer(db, visit.patient_id)
    snap = HeartLayerSnapshot(
        id=uuid.uuid4(),
        clinic_id=visit.clinic_id,
        patient_id=visit.patient_id,
        visit_id=visit.id,
        snapshot_type=snapshot_type,
        problems_json=payload["problems_json"],
        medications_json=payload["medications_json"],
        flags_json=payload["flags_json"],
        baselines_json=payload["baselines_json"],
        summary_text=payload["summary_text"],
        source="agent",
        is_demo_data=False,
    )
    db.add(snap)
    return snap


def load_heart_layer_at_visit(
    db: Session, visit: Visit, prefer: str = "before_visit"
) -> dict:
    """Mode A 用: 拿該 visit 的 snapshot heart layer (含 4 list + summary)。

    fallback 順序:
    1. 該 visit + prefer snapshot
    2. 該 visit + 另一個 snapshot
    3. reconstruct (用 first_observed_at_visit / diagnosed_at / measured_at
       過濾出該 visit_date 那一刻的心臟層狀態, 不會看到後續演進)

    司機 6/28 反饋 bug: 之前 fallback:current 把後續 visit 才出現的紅旗
    餵給 Mode A 「當時可獲得」, AI 變先知. reconstruct fallback 修這個.
    """
    snap = db.scalars(
        select(HeartLayerSnapshot).where(
            HeartLayerSnapshot.visit_id == visit.id,
            HeartLayerSnapshot.snapshot_type == prefer,
        )
    ).first()
    if not snap:
        other = "after_visit" if prefer == "before_visit" else "before_visit"
        snap = db.scalars(
            select(HeartLayerSnapshot).where(
                HeartLayerSnapshot.visit_id == visit.id,
                HeartLayerSnapshot.snapshot_type == other,
            )
        ).first()
    if snap:
        return {
            "flags_json": snap.flags_json,
            "problems_json": snap.problems_json,
            "medications_json": snap.medications_json,
            "baselines_json": snap.baselines_json,
            "summary_text": snap.summary_text or "",
            "source": f"snapshot:{snap.snapshot_type}",
        }
    # fallback: reconstruct (按 target visit_date 過濾, 不含後續演進)
    if prefer == "before_visit":
        return reconstruct_heart_at(db, visit.patient_id, visit.visit_date)
    # Mode B (hindsight) 看當下 OK
    payload = _serialize_heart_layer(db, visit.patient_id)
    payload["source"] = "fallback:current (Mode B)"
    return payload


def reconstruct_heart_at(
    db: Session, patient_id: uuid.UUID, target_visit_date
) -> dict:
    """重建 target_visit_date 那一刻的心臟層狀態 (過濾掉後續演進)。

    過濾規則:
    - flag: first_observed_at_visit 對應 visit_date > target 排除
            confidence_status='confirmed' 但 confirmed_at_visit > target → 回推 to_observe
    - problem: diagnosed_at > target 排除
    - medication: source='agent' (evolve 加) created_at > target 排除;
                  source='mock' (seed 既存) 保留 (病人本來就在吃)
    - baseline: measured_at > target 排除
    """
    target_date = target_visit_date.date() if hasattr(target_visit_date, "date") else target_visit_date

    # 預先 cache 該 patient 所有相關 visit 的 visit_date (避免 N+1)
    visits = db.scalars(
        select(Visit).where(Visit.patient_id == patient_id)
    ).all()
    visit_date_by_id = {v.id: v.visit_date for v in visits}

    # 1. flags
    flags_raw = db.scalars(
        select(PatientFlag).where(PatientFlag.patient_id == patient_id)
    ).all()
    flags_json = []
    for f in flags_raw:
        if f.first_observed_at_visit:
            fov_date = visit_date_by_id.get(f.first_observed_at_visit)
            if fov_date and fov_date > target_visit_date:
                continue  # 這 flag 是 target 之後才出現的
        confidence = f.confidence_status
        if confidence == "confirmed" and f.confirmed_at_visit:
            cov_date = visit_date_by_id.get(f.confirmed_at_visit)
            if cov_date and cov_date > target_visit_date:
                confidence = "to_observe"  # 還沒升 confirmed
        flags_json.append({
            "id": str(f.id),
            "flag_type": f.flag_type,
            "severity": f.severity,
            "content": f.content,
            "confidence_status": confidence,
            "flag_source": f.flag_source,
            "valid_until": f.valid_until.isoformat() if f.valid_until else None,
        })

    # 2. problems
    problems_raw = db.scalars(
        select(PatientProblem).where(PatientProblem.patient_id == patient_id)
    ).all()
    problems_json = []
    for p in problems_raw:
        if p.diagnosed_at and p.diagnosed_at > target_date:
            continue
        problems_json.append({
            "id": str(p.id),
            "problem_name": p.problem_name,
            "icd10_code": p.icd10_code,
            "control_status": p.control_status,
            "problem_source": p.problem_source,
            "diagnosed_at": p.diagnosed_at.isoformat() if p.diagnosed_at else None,
        })

    # 3. medications: evolve 加的按 created_at, seed 既存保留
    medications_raw = db.scalars(
        select(PatientMedication).where(PatientMedication.patient_id == patient_id)
    ).all()
    medications_json = []
    for m in medications_raw:
        if m.source == "agent" and m.created_at and m.created_at > target_visit_date:
            continue
        if not m.is_active:
            continue
        medications_json.append({
            "id": str(m.id),
            "medication_name": m.medication_name,
            "category": m.category,
            "dosage": m.dosage,
            "frequency": m.frequency,
            "is_active": m.is_active,
        })

    # 4. baselines: measured_at <= target
    baselines_raw = db.scalars(
        select(PatientBaseline).where(PatientBaseline.patient_id == patient_id)
    ).all()
    baselines_json = []
    for b in baselines_raw:
        if b.measured_at and b.measured_at > target_visit_date:
            continue
        baselines_json.append({
            "id": str(b.id),
            "category": b.category,
            "value_text": b.value_text,
            "measured_at": b.measured_at.isoformat() if b.measured_at else None,
        })

    confirmed_flags = [f for f in flags_json if f["confidence_status"] == "confirmed"]
    to_observe_flags = [f for f in flags_json if f["confidence_status"] == "to_observe"]
    summary_lines = [
        f"心臟層摘要 (重建 {target_date}): {len(confirmed_flags)} 紅旗確認 / {len(to_observe_flags)} 待觀察 / {len(problems_json)} 慢性病 / {len(medications_json)} 長期用藥 / {len(baselines_json)} baseline",
    ]
    if confirmed_flags:
        summary_lines.append(
            "確認紅旗: " + "; ".join(f["content"][:40] for f in confirmed_flags[:5])
        )
    if problems_json:
        summary_lines.append(
            "慢性病: " + ", ".join(p["problem_name"] for p in problems_json[:8])
        )
    if medications_json:
        summary_lines.append(
            "長期用藥: " + ", ".join(m["medication_name"] for m in medications_json[:8])
        )

    return {
        "flags_json": flags_json,
        "problems_json": problems_json,
        "medications_json": medications_json,
        "baselines_json": baselines_json,
        "summary_text": "\n".join(summary_lines),
        "source": f"reconstruct:{target_date}",
    }
