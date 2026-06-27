"""
============================================================
scripts/cleanup_smoke_leftover.py -- 清我自己 smoke test 留的污染
============================================================
司機 audit 抓到 TEST-0050 有兩個一模一樣的 visit (2026-06-27 + 2026-07-11
「頭暈持續 1 週 + 偶爾忘事」), 是我 Phase 5 smoke 跑兩輪留的.

清理 3 個 smoke leftover visit + 連帶資料:
- TEST-0002 2026-06-28 「胸悶 1 個月 + 走路會喘」(Phase 6.1 snapshot smoke)
- TEST-0050 2026-06-27 「頭暈持續 1 週 + 偶爾忘事」(Phase 5 smoke R1)
- TEST-0050 2026-07-11 「頭暈持續 1 週 + 偶爾忘事」(Phase 5 smoke R2 重複 R1)

連帶處理:
- 砍 visit_examinations / ai_drafts / heart_layer_snapshots / prescriptions
- 砍 baselines (source='agent' + measured_at = smoke visit_date)
- 砍 flag (first_observed_at_visit IN smoke_visit_ids)
- 改 problems.diagnosed_at 為 None (chronic 保留, 但去掉 smoke 那天當診斷日)
- 改 medications.created_at 不動 (source='agent' 的 created_at = seed time, OK)

用法:
    cd backend && .venv/Scripts/python -m scripts.cleanup_smoke_leftover
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    AiDraft,
    HeartLayerSnapshot,
    Patient,
    PatientBaseline,
    PatientFlag,
    PatientProblem,
    Prescription,
    PrescriptionItem,
    Visit,
    VisitExamination,
)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# smoke leftover visit 特徵: source='manual' + 特定 CC keyword
SMOKE_CC_PATTERNS = [
    "頭暈持續 1 週 + 偶爾忘事",   # Phase 5 smoke
    "胸悶 1 個月 + 走路會喘",       # Phase 6.1 smoke
]


def main() -> int:
    db = SessionLocal()
    try:
        # 找 smoke leftover visit
        smoke_visits = db.scalars(
            select(Visit).where(
                Visit.source == "manual",
                Visit.chief_complaint.in_(SMOKE_CC_PATTERNS),
            )
        ).all()
        logger.info("找到 %d 個 smoke leftover visit:", len(smoke_visits))
        for v in smoke_visits:
            patient = db.get(Patient, v.patient_id)
            logger.info("  - %s %s | CC=%r", patient.id_number, v.visit_date.date(), v.chief_complaint)

        if not smoke_visits:
            logger.info("沒有 smoke leftover, exit")
            return 0

        smoke_vids = [v.id for v in smoke_visits]
        smoke_dates = [v.visit_date for v in smoke_visits]
        smoke_patient_ids = list({v.patient_id for v in smoke_visits})

        # 1. 砍 flag (first_observed_at_visit IN smoke + 該 flag 是 source='agent')
        flags_to_kill = db.scalars(
            select(PatientFlag).where(
                PatientFlag.first_observed_at_visit.in_(smoke_vids),
                PatientFlag.source == "agent",
            )
        ).all()
        for f in flags_to_kill:
            logger.info("  砍 flag: %s %r", f.id, f.content[:40])
        db.execute(delete(PatientFlag).where(
            PatientFlag.first_observed_at_visit.in_(smoke_vids),
            PatientFlag.source == "agent",
        ))

        # 2. 砍 baseline (source='agent' + measured_at IN smoke_dates + patient IN smoke patients)
        baselines_to_kill = db.scalars(
            select(PatientBaseline).where(
                PatientBaseline.source == "agent",
                PatientBaseline.patient_id.in_(smoke_patient_ids),
                PatientBaseline.measured_at.in_(smoke_dates),
            )
        ).all()
        logger.info("砍 %d 條 evolve baseline (smoke 加的)", len(baselines_to_kill))
        db.execute(delete(PatientBaseline).where(
            PatientBaseline.source == "agent",
            PatientBaseline.patient_id.in_(smoke_patient_ids),
            PatientBaseline.measured_at.in_(smoke_dates),
        ))

        # 3. 砍 prescription_items + prescription
        rx_ids = [
            r.id for r in db.scalars(
                select(Prescription).where(Prescription.visit_id.in_(smoke_vids))
            ).all()
        ]
        if rx_ids:
            db.execute(delete(PrescriptionItem).where(PrescriptionItem.prescription_id.in_(rx_ids)))
            db.execute(delete(Prescription).where(Prescription.id.in_(rx_ids)))
            logger.info("砍 %d 個 prescription", len(rx_ids))

        # 4. 砍 snapshot / ai_drafts / examination
        db.execute(delete(HeartLayerSnapshot).where(HeartLayerSnapshot.visit_id.in_(smoke_vids)))
        db.execute(delete(AiDraft).where(AiDraft.visit_id.in_(smoke_vids)))
        db.execute(delete(VisitExamination).where(VisitExamination.visit_id.in_(smoke_vids)))

        # 5. 砍 visit
        db.execute(delete(Visit).where(Visit.id.in_(smoke_vids)))
        logger.info("砍 %d 個 visit", len(smoke_vids))

        # 6. 改 problems.diagnosed_at = None for smoke patient (chronic 保留, 去掉 smoke 那天當診斷日)
        n_p = db.execute(
            update(PatientProblem)
            .where(
                PatientProblem.patient_id.in_(smoke_patient_ids),
                PatientProblem.problem_source == "inferred_from_visit",
                PatientProblem.diagnosed_at.in_([d.date() for d in smoke_dates]),
            )
            .values(diagnosed_at=None, problem_source="self_report",
                    notes="既往診斷 (smoke 留下的 inferred_from_visit 已清, 改為自報慢性病)")
        ).rowcount
        logger.info("改 %d 個 problem diagnosed_at -> None", n_p)

        db.commit()
        logger.info("DONE: cleanup complete")
        return 0
    except Exception:
        db.rollback()
        logger.exception("cleanup failed")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
