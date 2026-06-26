"""
============================================================
scripts/seed_heart_layer.py -- 灌心臟層 (v0.3 Phase 2.1)
============================================================
從 seed_data/external_sources/mock_data.json 的 jimmy 原始檔
(含 allergies / chronic_conditions 字串) 解析後灌進:
- patient_flags     (allergies -> allergy flag, severity=red, source=self_report)
- patient_problems  (chronic_conditions -> active problem, source=self_report)

注意:
- import_jimmy_mock 把 jimmy mock 簡化丟掉 allergies/chronic_conditions,
  所以 seed_dev_data 用的 seed_data/mock_data.json 是「清乾淨版」沒這些欄位。
  本 script 直接讀 external_sources/ 原始檔 + 用 id_number 反查 DB UUID。

- 預設 dev 環境用 (跟 seed_dev_data 同樣 ENVIRONMENT=dev 守門)。

- idempotent: 重跑會先刪除該 clinic 的 demo flags + problems 再灌
  (DemoDataMixin is_demo_data=True 過濾, 不會誤砍人工資料)。

用法:
    ENVIRONMENT=dev python -m scripts.seed_heart_layer
    ENVIRONMENT=dev python -m scripts.seed_heart_layer --clinic-id <uuid>
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Patient,
    PatientFlag,
    PatientProblem,
    SOURCE_MOCK,
)

# 重用 v0.1 enum class 做應用層 validation (DB 是 String)
from app.models.patient_flag import FlagType, FlagSeverity, FlagSource, FlagTemporalMode
from app.models.patient_problem import ControlStatus, ProblemSource

# Windows console encoding (家規老坑)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
)
log = logging.getLogger("seed_heart_layer")


JIMMY_RAW_MOCK = (
    Path(__file__).resolve().parent.parent / "seed_data" / "external_sources" / "mock_data.json"
)

# 切分多個 allergen / condition 字串時用的 separator (含中英全形逗號 + 頓號)
SPLIT_PATTERN = re.compile(r"[,，;；、]\s*")

# 「沒有」的所有寫法 (case-insensitive)
NONE_TOKENS = {
    "", "none", "no", "nil", "n/a", "na", "nka", "nkda",
    "無", "沒有", "否", "無已知過敏", "無已知藥物過敏",
}


def assert_dev_environment() -> None:
    """跟 seed_dev_data 同樣守門, production 禁跑。"""
    env = os.environ.get("ENVIRONMENT", "").lower()
    if env != "dev":
        raise RuntimeError(
            f"seed_heart_layer 只能在 ENVIRONMENT=dev 跑 (現在={env!r})"
        )


def parse_list(raw: str | None) -> list[str]:
    """把 'Penicillin, Aspirin' 拆成 ['Penicillin', 'Aspirin']。"""
    if not raw:
        return []
    cleaned = raw.strip()
    if cleaned.lower() in NONE_TOKENS:
        return []
    parts = [p.strip() for p in SPLIT_PATTERN.split(cleaned) if p.strip()]
    # 過濾掉「無」這類 token
    return [p for p in parts if p.lower() not in NONE_TOKENS]


def _resolve_clinic(db: Session, clinic_id_arg: str | None) -> Clinic:
    """指定 clinic-id 就用, 否則取第一間 (跟 seed_dev_data 同邏輯)。"""
    if clinic_id_arg:
        c = db.get(Clinic, UUID(clinic_id_arg))
        if not c:
            raise RuntimeError(f"找不到 clinic id={clinic_id_arg}")
        return c
    c = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
    if not c:
        raise RuntimeError(
            "DB 沒任何 clinic, 先跑 scripts/seed.py 建第一間"
        )
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clinic-id", default=None, help="目標 clinic UUID (預設取第一間)")
    parser.add_argument("--mock-path", default=str(JIMMY_RAW_MOCK), help="jimmy 原始 mock 路徑")
    parser.add_argument("--dry-run", action="store_true", help="只解析, 不寫 DB")
    args = parser.parse_args()

    assert_dev_environment()

    mock_path = Path(args.mock_path)
    if not mock_path.exists():
        log.error("mock 檔不存在: %s", mock_path)
        return 1

    with mock_path.open(encoding="utf-8") as f:
        data = json.load(f)

    patients_mock: list[dict[str, Any]] = data.get("patients", [])
    log.info("讀進 %d 個 mock patient (含 allergies/chronic_conditions)", len(patients_mock))

    db: Session = SessionLocal()
    try:
        clinic = _resolve_clinic(db, args.clinic_id)
        log.info("目標 clinic: %s (%s)", clinic.name, clinic.id)

        # 建 id_number -> patient UUID map (demo data only)
        existing = db.scalars(
            select(Patient).where(
                Patient.clinic_id == clinic.id,
                Patient.is_demo_data.is_(True),
            )
        ).all()
        id_to_uuid: dict[str, UUID] = {
            p.id_number: p.id for p in existing if p.id_number
        }
        log.info("DB 內 demo patient: %d (用 id_number 反查 UUID)", len(id_to_uuid))

        # idempotent: 先刪該 clinic 的 demo 心臟層 (重跑乾淨)
        if not args.dry_run:
            del_flags = db.execute(
                delete(PatientFlag).where(
                    PatientFlag.clinic_id == clinic.id,
                    PatientFlag.is_demo_data.is_(True),
                )
            ).rowcount
            del_probs = db.execute(
                delete(PatientProblem).where(
                    PatientProblem.clinic_id == clinic.id,
                    PatientProblem.is_demo_data.is_(True),
                )
            ).rowcount
            log.info("先刪舊 demo: %d flags + %d problems", del_flags, del_probs)

        common = {
            "clinic_id": clinic.id,
            "source": SOURCE_MOCK,
            "is_demo_data": True,
        }

        flag_count = 0
        problem_count = 0
        unmatched = []

        for mp in patients_mock:
            id_number = mp.get("id_number")
            patient_uuid = id_to_uuid.get(id_number)
            if not patient_uuid:
                unmatched.append((id_number, mp.get("full_name") or mp.get("patient_ref")))
                continue

            # 過敏 -> patient_flag
            for allergen in parse_list(mp.get("allergies")):
                flag = PatientFlag(
                    patient_id=patient_uuid,
                    flag_type=FlagType.ALLERGY.value,
                    temporal_mode=FlagTemporalMode.PERMANENT.value,
                    severity=FlagSeverity.RED.value,
                    flag_source=FlagSource.SELF_REPORT.value,
                    content=allergen,
                    notes=f"從 jimmy mock allergies 解析 ({mp.get('patient_ref')})",
                    **common,
                )
                db.add(flag)
                flag_count += 1

            # 慢性病 -> patient_problem
            for condition in parse_list(mp.get("chronic_conditions")):
                prob = PatientProblem(
                    patient_id=patient_uuid,
                    problem_name=condition,
                    control_status=ControlStatus.ACTIVE.value,
                    problem_source=ProblemSource.SELF_REPORT.value,
                    notes=f"從 jimmy mock chronic_conditions 解析 ({mp.get('patient_ref')})",
                    **common,
                )
                db.add(prob)
                problem_count += 1

        if args.dry_run:
            db.rollback()
            log.info("[DRY RUN] 不寫 DB, 預計 +%d flags +%d problems", flag_count, problem_count)
        else:
            db.commit()
            log.info("=" * 60)
            log.info("Seed heart layer 完成")
            log.info("  patient_flags     + %d", flag_count)
            log.info("  patient_problems  + %d", problem_count)
            if unmatched:
                log.warning("  unmatched patients (id_number 沒對到 DB): %d", len(unmatched))
                for id_no, name in unmatched[:5]:
                    log.warning("    - %s / %s", id_no, name)
            log.info("=" * 60)

        return 0
    except Exception:
        db.rollback()
        log.exception("seed_heart_layer 失敗, 已 rollback")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
