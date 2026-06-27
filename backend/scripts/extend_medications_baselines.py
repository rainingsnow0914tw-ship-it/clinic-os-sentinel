"""
============================================================
scripts/extend_medications_baselines.py -- 補心臟層 medications + baselines
============================================================
seed_heart_layer.py 只灌 patient_flags + patient_problems, 沒灌 medications
跟 baselines, 心臟層 4 段只有 2 段有 data, 病例瀏覽右下 2 段空白。

本 script 補:
1. patient_medications: 從 chronic conditions 推導長期用藥
   高血壓 -> Amlodipine 5mg qd
   T2DM   -> Metformin 500mg bid
   高血脂 -> Atorvastatin 20mg qd hs
   心衰   -> Losartan 50mg qd
   COPD   -> Tiotropium (Spiriva) (drug pool 沒, fallback Fluticasone)
   ...
2. patient_baselines: 從 demographic 推
   平常 BP (BMI 偏高/高血壓人偏高範圍)
   BMI 推估 (年齡 + 性別)
   吸菸/飲酒 (10-15% chance)

idempotent: source='extended_mock' 區隔
============================================================
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Patient,
    PatientBaseline,
    PatientMedication,
    PatientProblem,
)
from app.models.patient_baseline import BaselineCategory, BaselineSource
from app.models.patient_medication import MedicationCategory, MedicationSource

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")
log = logging.getLogger("extend_med_base")

SEED = 20260627
SOURCE_TAG = "extended_mock"


# chronic -> long-term med list of tuple (name, dosage, frequency)
CHRONIC_TO_MEDS = {
    "Hypertension":          [("Amlodipine", "5mg", "qd am")],
    "Type 2 Diabetes":       [("Metformin", "500mg", "bid pc")],
    "Hyperlipidemia":        [("Atorvastatin", "20mg", "qd hs")],
    "Heart Failure":         [("Losartan", "50mg", "qd am"), ("Furosemide", "40mg", "qd am")],
    "Atrial Fibrillation":   [("Bisoprolol", "5mg", "qd am"), ("Apixaban", "5mg", "bid")],
    "CKD Stage 3":           [("Losartan", "50mg", "qd am")],
    "Asthma":                [("Fluticasone inhaler", "125mcg", "2 puff bid")],
    "COPD":                  [("Tiotropium inhaler", "18mcg", "1 puff qd")],
    "Hypothyroidism":        [("Levothyroxine", "50mcg", "qd ac")],
    "Anxiety Disorder":      [("Escitalopram", "10mg", "qd")],
    "Depression":            [("Sertraline", "50mg", "qd am")],
    "GERD":                  [("Omeprazole", "20mg", "qd ac")],
    "BPH":                   [("Tamsulosin", "0.4mg", "qd hs")],
    "Migraine":              [("Propranolol", "40mg", "bid")],
    "Osteoarthritis":        [("Glucosamine", "500mg", "tid")],
    "Osteoporosis":          [("Alendronate", "70mg", "1 tab weekly"), ("Calcium + VitD", "1 tab", "qd")],
    "Gout":                  [("Allopurinol", "100mg", "qd")],
    "Dementia":              [("Donepezil", "5mg", "qd hs")],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = os.environ.get("ENVIRONMENT", "").lower()
    if env != "dev":
        log.error("ENVIRONMENT=dev required")
        return 1

    rng = random.Random(SEED)
    db: Session = SessionLocal()
    try:
        clinic = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
        if not clinic:
            log.error("沒 clinic")
            return 1

        # idempotent: 先刪 extended_mock 的 medications + baselines
        if not args.dry_run:
            n_med = db.execute(
                delete(PatientMedication).where(
                    PatientMedication.clinic_id == clinic.id,
                    PatientMedication.source == SOURCE_TAG,
                )
            ).rowcount
            n_base = db.execute(
                delete(PatientBaseline).where(
                    PatientBaseline.clinic_id == clinic.id,
                    PatientBaseline.source == SOURCE_TAG,
                )
            ).rowcount
            log.info("先刪舊 extended: %d medications + %d baselines", n_med, n_base)

        # 拿所有 demo patient
        patients = db.scalars(
            select(Patient).where(
                Patient.clinic_id == clinic.id,
                Patient.is_demo_data.is_(True),
            )
        ).all()
        log.info("處理 %d patient", len(patients))

        # patient -> 其 chronic 名稱 set
        chronic_by_pid: dict[UUID, set[str]] = {}
        for prob in db.scalars(
            select(PatientProblem).where(PatientProblem.clinic_id == clinic.id)
        ).all():
            chronic_by_pid.setdefault(prob.patient_id, set()).add(prob.problem_name)

        now = datetime(2026, 6, 27, tzinfo=timezone.utc)
        common = {
            "clinic_id": clinic.id,
            "source": SOURCE_TAG,
            "is_demo_data": True,
        }

        n_med_added = 0
        n_base_added = 0

        for p in patients:
            age = (now.year - p.date_of_birth.year) if p.date_of_birth else 50
            chronics = chronic_by_pid.get(p.id, set())

            # === 1. 長期用藥 (從 chronic 推) ===
            for chronic in chronics:
                meds = CHRONIC_TO_MEDS.get(chronic)
                if not meds:
                    continue
                for med_name, dosage, freq in meds:
                    med = PatientMedication(
                        id=uuid4(),
                        patient_id=p.id,
                        medication_name=med_name,
                        category=MedicationCategory.LONG_TERM.value,
                        dosage=dosage,
                        frequency=freq,
                        medication_source=MedicationSource.SELF_REPORT.value,
                        is_active=True,
                        notes=f"從 {chronic} 推導 (extended demo)",
                        **common,
                    )
                    db.add(med)
                    n_med_added += 1

            # === 2. Baseline ===
            # 2.1 平常 BP (objective)
            if "Hypertension" in chronics:
                sbp_base, dbp_base = rng.randint(135, 155), rng.randint(82, 95)
            elif age >= 65:
                sbp_base, dbp_base = rng.randint(122, 138), rng.randint(72, 85)
            else:
                sbp_base, dbp_base = rng.randint(108, 128), rng.randint(65, 80)
            db.add(PatientBaseline(
                id=uuid4(),
                patient_id=p.id,
                category=BaselineCategory.OBJECTIVE.value,
                baseline_source=BaselineSource.CLINICAL.value,
                value_text=f"平常 BP {sbp_base}/{dbp_base}",
                measured_at=now,
                **common,
            ))
            n_base_added += 1

            # 2.2 BMI (objective)
            if "Type 2 Diabetes" in chronics or "Hyperlipidemia" in chronics:
                bmi = round(rng.uniform(25.0, 30.5), 1)
            elif age >= 65:
                bmi = round(rng.uniform(22.0, 27.0), 1)
            else:
                bmi = round(rng.uniform(20.0, 25.5), 1)
            db.add(PatientBaseline(
                id=uuid4(),
                patient_id=p.id,
                category=BaselineCategory.OBJECTIVE.value,
                baseline_source=BaselineSource.CLINICAL.value,
                value_text=f"BMI {bmi}",
                measured_at=now,
                **common,
            ))
            n_base_added += 1

            # 2.3 嗜好 (habit) -- 吸菸 (15% chance, 男性更高)
            smoke_chance = 0.22 if p.gender == "M" else 0.06
            if rng.random() < smoke_chance:
                pack_years = rng.randint(5, 35)
                db.add(PatientBaseline(
                    id=uuid4(),
                    patient_id=p.id,
                    category=BaselineCategory.HABIT.value,
                    baseline_source=BaselineSource.SELF_REPORT.value,
                    value_text=f"吸菸 {rng.choice([10, 15, 20])} 支/天 ({pack_years} pack-years)",
                    measured_at=now,
                    **common,
                ))
                n_base_added += 1
            else:
                db.add(PatientBaseline(
                    id=uuid4(),
                    patient_id=p.id,
                    category=BaselineCategory.HABIT.value,
                    baseline_source=BaselineSource.SELF_REPORT.value,
                    value_text="不吸菸",
                    measured_at=now,
                    **common,
                ))
                n_base_added += 1

            # 2.4 飲酒 (25% chance some, 男性更高)
            drink_chance = 0.30 if p.gender == "M" else 0.12
            if rng.random() < drink_chance:
                pattern = rng.choice([
                    "偶爾飲酒 (聚餐場合)", "每週啤酒 2-3 瓶", "每週紅酒 1-2 杯",
                ])
                db.add(PatientBaseline(
                    id=uuid4(),
                    patient_id=p.id,
                    category=BaselineCategory.HABIT.value,
                    baseline_source=BaselineSource.SELF_REPORT.value,
                    value_text=pattern,
                    measured_at=now,
                    **common,
                ))
                n_base_added += 1
            else:
                db.add(PatientBaseline(
                    id=uuid4(),
                    patient_id=p.id,
                    category=BaselineCategory.HABIT.value,
                    baseline_source=BaselineSource.SELF_REPORT.value,
                    value_text="不飲酒",
                    measured_at=now,
                    **common,
                ))
                n_base_added += 1

        if args.dry_run:
            db.rollback()
            log.info("[DRY RUN] 預計 +%d medications +%d baselines", n_med_added, n_base_added)
        else:
            db.commit()
            log.info("=" * 60)
            log.info("Extend medications + baselines 完成")
            log.info("  patient_medications + %d", n_med_added)
            log.info("  patient_baselines   + %d", n_base_added)
            log.info("=" * 60)
        return 0
    except Exception:
        db.rollback()
        log.exception("extend_medications_baselines 失敗, rollback")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
