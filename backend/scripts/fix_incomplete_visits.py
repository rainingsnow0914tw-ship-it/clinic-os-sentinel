"""
============================================================
scripts/fix_incomplete_visits.py -- 補不完整的 visit (司機 audit)
============================================================
司機 audit DB 反饋有些 visit 沒處方 + 有些 chronic patient 沒長期用藥.

修兩件事:
1. visit 沒 Rx -> 從 visit.diagnosis 推合理 default Rx + 寫進去
2. chronic patient 沒對應 long-term med -> 從 chronic 推 default 藥 +
   寫進 patient_medications (Phase 5 evolve 用 INFERRED_FROM_VISIT, 這
   邊用 SELF_REPORT, 表示既往用藥)

用法:
    cd backend && .venv/Scripts/python -m scripts.fix_incomplete_visits
"""

from __future__ import annotations

import logging
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Drug,
    Patient,
    PatientMedication,
    PatientProblem,
    Prescription,
    PrescriptionItem,
    SOURCE_MOCK,
    Visit,
)
from app.models.patient_medication import MedicationCategory, MedicationSource

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Dx keyword -> Rx recipe (list of (drug_code, usage_text, daily_dose, days))
DX_TO_RX: dict[str, list[tuple[str, str, int, int]]] = {
    # 慢性病 (沿用既有藥, 不另開)
    "高血壓":      [("AMLODIPINE_5", "1# QD", 1, 30)],
    "糖尿病":      [("METFORMIN_500", "1# bid pc", 2, 30)],
    "高脂血":      [("ATORVASTATIN_20", "1# QD HS", 1, 30)],
    "胃食道逆流":   [("OMEPRAZOLE_20", "1# QD ac (空腹)", 1, 30)],
    "心房顫動":    [("LOSARTAN_50", "1# QD", 1, 30)],  # 沿用降壓
    "慢性腎":     [("LOSARTAN_50", "1# QD", 1, 30)],
    # 急性病
    "上呼吸道感染": [("PARA_500", "1# QID prn 發熱頭痛", 4, 3),
                ("CETIRIZINE_10", "1# QD HS", 1, 5)],
    "鼻咽炎":     [("PARA_500", "1# QID prn", 4, 3),
                ("LORATADINE_10", "1# QD", 1, 5)],
    "支氣管炎":    [("AMOX_500", "1# tid", 3, 5),
                ("AMBROXOL_30", "1# tid", 3, 5)],
    "咽喉炎":     [("PARA_500", "1# QID prn", 4, 3),
                ("AMOX_500", "1# tid (細菌懷疑)", 3, 5)],
    "扁桃腺":     [("AMOX_500", "1# tid", 3, 7)],
    "腸胃炎":     [("LOPERAMIDE_2", "1# 拉肚子時, max qid", 4, 3),
                ("ORS_SACHET", "1 包/次 沖水補充", 3, 3)],
    "緊張":      [("PARA_500", "1# QID prn", 4, 5)],
    "頭痛":      [("PARA_500", "1# QID prn", 4, 5)],
    "偏頭痛":     [("PARA_500", "1# QID prn 急性", 4, 5)],
    "皮膚":      [("HYDROCORTISONE_1", "薄塗患處 bid", 2, 7),
                ("CHLORPHENIRAMINE_4", "1# tid prn 癢", 3, 5)],
    "接觸性皮膚": [("HYDROCORTISONE_1", "薄塗患處 bid", 2, 7)],
    "結膜":      [("ARTIFICIAL_TEARS", "1-2 滴 qid", 4, 7)],
    "氣喘":      [("FLUTICASONE_SPRAY", "1 噴 BID 維持", 2, 30)],
    "COPD":     [("FLUTICASONE_SPRAY", "1 噴 BID", 2, 30)],
    "骨關節炎":    [("IBU_400", "1# tid prn 疼痛 (短期)", 3, 7),
                ("PARA_500", "1# QID prn", 4, 7)],
    "痛風":      [("IBU_400", "1# tid prn (發作期短用)", 3, 5)],
    "焦慮":      [("PARA_500", "1# bid prn 緊張頭痛", 2, 7)],
    "失智":      [],   # MCI 不開特定藥, 多為衛教
    "認知":      [],
    "BPPV":     [("PARA_500", "1# QID prn 頭暈伴頭痛", 4, 5)],
    "前庭":      [("PARA_500", "1# QID prn", 4, 5)],
    "感染後咳":    [("AMBROXOL_30", "1# tid", 3, 5)],
    "心衰":      [("LOSARTAN_50", "1# QD", 1, 30)],
    "鬱血性":     [("LOSARTAN_50", "1# QD", 1, 30)],
    "攝護腺":     [],   # demo drug 表沒 tamsulosin/finasteride, skip
}


# Chronic -> default long-term med (patient_medications 用)
CHRONIC_TO_LONG_TERM_MED: dict[str, tuple[str, str, str]] = {
    # canonical chronic name -> (medication_name, dosage, frequency)
    "原發性高血壓":   ("amlodipine", "5 mg", "QD"),
    "第二型糖尿病":   ("metformin", "500 mg", "BID pc"),
    "高脂血症":      ("atorvastatin", "20 mg", "QD HS"),
    "胃食道逆流症":   ("omeprazole", "20 mg", "QD ac"),
    "心房顫動":      ("apixaban", "5 mg", "BID"),
    "慢性腎臟病":     ("losartan", "50 mg", "QD"),
    "慢性腎臟病第三期": ("losartan", "50 mg", "QD"),
    "慢性心衰竭":     ("furosemide", "40 mg", "QD AM"),
    "支氣管哮喘":     ("fluticasone", "1 噴 BID", "BID"),
    "慢性阻塞性肺病":  ("tiotropium", "1 吸 QD", "QD"),
    "甲狀腺功能低下":  ("levothyroxine", "50 mcg", "QD AM"),
    "痛風":         ("allopurinol", "100 mg", "QD"),
    "骨關節炎":      ("acetaminophen", "500 mg", "TID PRN"),
    "膝部骨關節炎":   ("acetaminophen", "500 mg", "TID PRN"),
    "良性攝護腺肥大":  ("tamsulosin", "0.4 mg", "QD"),
    "失智症":       ("donepezil", "5 mg", "QD"),
    "輕度認知障礙":   ("donepezil", "5 mg", "QD"),
    "偏頭痛":       ("propranolol", "20 mg", "BID PRN"),
    "廣泛性焦慮症":   ("sertraline", "50 mg", "QD"),
    "重度憂鬱症":    ("sertraline", "50 mg", "QD"),
    "骨質疏鬆症":    ("alendronate", "70 mg", "QW"),
    "冠狀動脈疾病":   ("aspirin", "100 mg", "QD"),
}


def pick_rx_for_dx(dx: str) -> list[tuple[str, str, int, int]]:
    """match dx keyword -> default Rx recipe."""
    if not dx:
        return []
    for keyword, recipe in DX_TO_RX.items():
        if keyword in dx:
            return recipe
    return []


def fix_missing_rx(db: Session, clinic: Clinic) -> int:
    """補沒 prescription 的 visit (從 dx 推 default Rx)."""
    visits_no_rx = db.scalars(
        select(Visit).where(
            ~Visit.id.in_(select(Prescription.visit_id))
        )
    ).all()
    logger.info("找到 %d 個 visit 沒 Rx", len(visits_no_rx))
    drug_by_code = {d.code: d for d in db.scalars(select(Drug)).all()}

    added = 0
    for v in visits_no_rx:
        recipe = pick_rx_for_dx(v.diagnosis or "")
        if not recipe:
            logger.warning("  visit %s dx=%r 無法 match recipe, skip", v.id, v.diagnosis)
            continue
        rx = Prescription(
            id=uuid.uuid4(),
            clinic_id=v.clinic_id,
            visit_id=v.id,
            status="dispensed",
            source=SOURCE_MOCK,
            is_demo_data=True,
        )
        db.add(rx)
        db.flush()
        for drug_code, usage_text, daily_dose, days in recipe:
            drug = drug_by_code.get(drug_code)
            if not drug:
                continue
            total_qty = int(daily_dose * days)
            db.add(PrescriptionItem(
                id=uuid.uuid4(),
                clinic_id=v.clinic_id,
                prescription_id=rx.id,
                drug_id=drug.id,
                usage_text=usage_text,
                daily_dose=daily_dose,
                days=days,
                total_quantity=total_qty,
                unit_price_at_time=0,
                total_price=0,
                source=SOURCE_MOCK,
                is_demo_data=True,
            ))
        added += 1
        logger.info("  補 Rx %s: dx=%r -> %d items", v.id, v.diagnosis, len(recipe))

    return added


def fix_missing_chronic_meds(db: Session) -> int:
    """補有 chronic 但 0 long-term med 的 patient (從 chronic 推 default 藥)."""
    # 撈所有 patient + 計算 n_chronic / n_med
    patients = db.scalars(select(Patient)).all()
    added = 0
    for p in patients:
        chronics = db.scalars(
            select(PatientProblem).where(PatientProblem.patient_id == p.id)
        ).all()
        if not chronics:
            continue
        meds_existing = db.scalars(
            select(PatientMedication).where(PatientMedication.patient_id == p.id)
        ).all()
        existing_names = {m.medication_name.lower() for m in meds_existing}

        for pp in chronics:
            recipe = CHRONIC_TO_LONG_TERM_MED.get(pp.problem_name)
            if not recipe:
                continue
            med_name, dosage, freq = recipe
            if med_name.lower() in existing_names:
                continue
            db.add(PatientMedication(
                id=uuid.uuid4(),
                clinic_id=p.clinic_id,
                patient_id=p.id,
                medication_name=med_name,
                category=MedicationCategory.LONG_TERM.value,
                dosage=dosage,
                frequency=freq,
                medication_source=MedicationSource.SELF_REPORT.value,
                is_active=True,
                notes=f"自動補: 對應慢性病 {pp.problem_name}",
                source=SOURCE_MOCK,
                is_demo_data=True,
            ))
            existing_names.add(med_name.lower())
            added += 1
            logger.info("  補 long-term med %s for %s (chronic: %s)",
                        med_name, p.id_number, pp.problem_name)
    return added


def main() -> int:
    db = SessionLocal()
    try:
        clinic = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
        if not clinic:
            logger.error("no clinic")
            return 1

        n_rx = fix_missing_rx(db, clinic)
        n_med = fix_missing_chronic_meds(db)

        db.commit()
        logger.info("DONE: fixed %d missing Rx + %d missing long-term med", n_rx, n_med)
        return 0
    except Exception:
        db.rollback()
        logger.exception("fix failed")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
