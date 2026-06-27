"""
============================================================
scripts/normalize_patient_names.py -- 修 patient name × age mismatch
============================================================
問題: extend_mock_patients.py 生成時 name 暗示的年齡層跟實際 dob 算出
的 age 不對 (e.g. "Generic Super Senior 11" F 36y, "Demo Geriatric 3"
F 63y), UI 顯示這些 name 看起來很詭異.

修法:
  age < 18      -> Generic Peds {num}
  18 <= age <35 -> Generic Youth {num}
  35 <= age <60 -> Generic Adult {num}
  60 <= age <75 -> Generic Senior {num}
  age >= 75     -> Generic Super Senior {num}

只動 name 暗示 tier 跟實際 age 不對的, 保留所有 demo 紅旗 patient
(TEST-0001..TEST-0010 之類) + 我擴的中文名 patient (黃曉欣等).

用法:
    cd backend && .venv/Scripts/python -m scripts.normalize_patient_names
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Patient

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def age_to_tier(age: int) -> str:
    if age < 18:
        return "Peds"
    if age < 35:
        return "Youth"
    if age < 60:
        return "Adult"
    if age < 75:
        return "Senior"
    return "Super Senior"


# name 含這些關鍵字才修 (避免動到 Demo Penicillin Allergy / 中文名 / 王阿姨)
TIER_KEYWORDS = re.compile(r"\b(peds|youth|adult|senior|super[- ]?senior|geriatric|mid[- ]?age|teen|child)\b", re.IGNORECASE)

# 從 name 抓出 number suffix
NUM_SUFFIX = re.compile(r"(\d+)\s*$")


def main() -> int:
    db = SessionLocal()
    try:
        today = date.today()
        patients = db.scalars(select(Patient)).all()
        logger.info("total patients: %d", len(patients))

        fixed = 0
        for p in patients:
            if not p.name or not p.date_of_birth:
                continue
            if not TIER_KEYWORDS.search(p.name):
                continue   # 沒有 tier 關鍵字 (純中文名 / 真實 demo 紅旗 name) -> 不動

            age = today.year - p.date_of_birth.year
            if (today.month, today.day) < (p.date_of_birth.month, p.date_of_birth.day):
                age -= 1
            correct_tier = age_to_tier(age)

            m = NUM_SUFFIX.search(p.name)
            num = m.group(1) if m else ""

            # 已正確 tier -> skip
            if correct_tier.lower() in p.name.lower():
                continue
            # super senior 比對特殊 (兩個字)
            if correct_tier == "Super Senior" and "super senior" in p.name.lower():
                continue

            new_name = f"Generic {correct_tier} {num}".strip()
            logger.info("  %s %sy: %r -> %r", p.id_number, age, p.name, new_name)
            p.name = new_name
            fixed += 1

        db.commit()
        logger.info("DONE: renamed %d patients", fixed)
        return 0
    except Exception:
        db.rollback()
        logger.exception("normalize patient names failed")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
