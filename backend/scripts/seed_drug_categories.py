"""
============================================================
scripts/seed_drug_categories.py -- 灌既有 30 個 drug 的分類
============================================================
司機 6/28 反饋: Rx 寫入要支援分類選單 (退燒/止痛/抗生素/...).
本 script 對既有 30 個 drug 套 DRUG_CATEGORY_MAP, update 進 DB.

idempotent: 重跑 = 沒改變 (UPDATE 寫同樣值).

用法: cd backend && .venv/Scripts/python -m scripts.seed_drug_categories
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Drug

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# code -> category (中文, user-friendly)
DRUG_CATEGORY_MAP: dict[str, str] = {
    "AMOX_500":             "抗生素",
    "MUPIROCIN_2":          "外用藥膏",
    "PROBIOTIC_SACHET":     "益生菌補充劑",
    "IBU_400":              "止痛消炎",
    "ANTIFUNGAL_CREAM":     "外用藥膏",
    "LORATADINE_10":        "抗組織胺過敏",
    "COUGH_SYRUP":          "化痰止咳",
    "LOSARTAN_50":          "降血壓",
    "FLUTICASONE_SPRAY":    "鼻噴霧",
    "ANTACID_LIQUID":       "胃藥",
    "WOUND_PACK":           "傷口包紮",
    "METFORMIN_500":        "降血糖",
    "HYDROCORTISONE_1":     "外用藥膏",
    "ORS_SACHET":           "電解質補充",
    "LOPERAMIDE_2":         "止瀉",
    "CEPHALEXIN_250":       "抗生素",
    "ATORVASTATIN_20":      "降血脂",
    "OMEPRAZOLE_20":        "胃藥",
    "AMBROXOL_30":          "化痰止咳",
    "AMLODIPINE_5":         "降血壓",
    "PARA_500":             "退燒止痛",
    "ANTIHISTAMINE_DROPS":  "眼藥水",
    "FAMOTIDINE_20":        "胃藥",
    "CHLORPHENIRAMINE_4":   "抗組織胺過敏",
    "VIT_C_500":            "益生菌補充劑",
    "GUAIFENESIN_SYRUP":    "化痰止咳",
    "SALINE_SPRAY":         "鼻噴霧",
    "ARTIFICIAL_TEARS":     "眼藥水",
    "AZITHROMYCIN_250":     "抗生素",
    "CETIRIZINE_10":        "抗組織胺過敏",
}


def main() -> int:
    db = SessionLocal()
    try:
        drugs = db.scalars(select(Drug)).all()
        logger.info("total drugs: %d", len(drugs))

        updated = 0
        unmapped = []
        for d in drugs:
            cat = DRUG_CATEGORY_MAP.get(d.code)
            if not cat:
                unmapped.append(d.code)
                continue
            if d.category != cat:
                d.category = cat
                updated += 1
                logger.info("  %s (%s) -> %s", d.code, d.name, cat)

        if unmapped:
            logger.warning("unmapped codes (留 NULL): %s", unmapped)

        db.commit()
        logger.info("DONE: updated %d drugs, unmapped %d", updated, len(unmapped))
        return 0
    except Exception:
        db.rollback()
        logger.exception("seed_drug_categories failed")
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
