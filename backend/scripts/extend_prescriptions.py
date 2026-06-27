"""
============================================================
scripts/extend_prescriptions.py -- 補 prescription (Phase 2.4d)
============================================================
為 source='extended_mock' 的 visit 灌 chronic-aware prescription。
jimmy mock 只有 5 個 prescription 對應 5 個 jimmy visit, 我擴的 164
visit 全沒處方 → frontend Rx 段 95% 空白。

dx -> drug code mapping 用 substring 規則:
  高血壓 -> AMLODIPINE_5
  糖尿病 -> METFORMIN_500
  上呼吸道 -> PARA_500 + CETIRIZINE_10
  扁桃腺炎 -> AMOX_500 + PARA_500
  腸胃炎 -> LOPERAMIDE_2 + ORS_SACHET
  ...

idempotent: source='extended_mock' 區隔, 重跑會自己刪重灌
(reset_dev_data 守門 source='mock' 不會誤殺)。
============================================================
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    Drug,
    Prescription,
    PrescriptionItem,
    Visit,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(message)s")
log = logging.getLogger("extend_rx")

SEED = 20260627
SOURCE_TAG = "extended_mock"


# dx substring -> list of (drug_code, usage_text, days)
DX_TO_DRUGS: list[tuple[list[str], list[tuple[str, str, int]]]] = [
    # 慢性病類 -- 長期用藥 (30 天)
    (["高血壓"],          [("AMLODIPINE_5", "1#qd am", 30)]),
    (["心房顫動"],         [("AMLODIPINE_5", "1#qd", 30)]),
    (["心衰"],            [("LOSARTAN_50", "1#qd am", 30)]),
    (["腎臟病"],           [("LOSARTAN_50", "1#qd am", 30)]),
    (["糖尿病"],           [("METFORMIN_500", "1#bid pc", 30)]),
    (["高血脂"],           [("ATORVASTATIN_20", "1#qd hs", 30)]),
    # 慢性病 + 對症
    (["甲狀腺"],           [("VIT_C_500", "1#qd", 30)]),
    (["攝護腺"],           [("PARA_500", "1#prn", 5)]),
    (["憂鬱"],            [("VIT_C_500", "1#qd am", 30)]),
    (["失智", "認知障礙"],  [("VIT_C_500", "1#qd am", 30)]),
    # 急性感染 (抗生素 + 對症)
    (["扁桃腺炎"],         [("AMOX_500", "1#tid", 7), ("PARA_500", "1#tid prn", 5)]),
    (["支氣管炎"],         [("AMOX_500", "1#tid", 7), ("AMBROXOL_30", "1#tid", 5)]),
    (["細菌感染"],         [("CEPHALEXIN_250", "1#qid", 7), ("PARA_500", "1#tid prn", 5)]),
    (["COPD"],            [("AZITHROMYCIN_250", "1#qd", 5), ("AMBROXOL_30", "1#tid", 5)]),
    # 急性上呼吸道
    (["上呼吸道", "URTI", "鼻咽炎"],
                          [("PARA_500", "1#tid prn", 5), ("CETIRIZINE_10", "1#qd", 5), ("AMBROXOL_30", "1#tid", 5)]),
    (["咽喉炎"],           [("PARA_500", "1#tid prn", 5), ("COUGH_SYRUP", "10ml tid", 5)]),
    (["感染後咳嗽", "Post-infectious"],
                          [("AMBROXOL_30", "1#tid", 7), ("COUGH_SYRUP", "10ml tid prn", 7)]),
    (["氣喘"],            [("FLUTICASONE_SPRAY", "2噴bid", 30)]),
    # 鼻
    (["過敏性鼻炎"],       [("LORATADINE_10", "1#qd", 14), ("FLUTICASONE_SPRAY", "2噴qd", 30)]),
    # 腸胃
    (["腸胃炎", "腹瀉"],   [("LOPERAMIDE_2", "1#prn", 3), ("ORS_SACHET", "1包qid", 3), ("PROBIOTIC_SACHET", "1包bid", 3)]),
    (["胃食道逆流", "GERD"], [("OMEPRAZOLE_20", "1#qd ac", 14), ("ANTACID_LIQUID", "10ml prn", 14)]),
    # 皮膚
    (["接觸性皮膚炎"],     [("HYDROCORTISONE_1", "局部bid", 7), ("CETIRIZINE_10", "1#qd", 7)]),
    (["蕁麻疹"],           [("CETIRIZINE_10", "1#qd prn", 7), ("CHLORPHENIRAMINE_4", "1#hs prn", 7)]),
    # 神經 / 肌肉骨骼
    (["緊張型頭痛", "頸椎"], [("PARA_500", "1#tid prn", 5)]),
    (["偏頭痛"],           [("IBU_400", "1#tid prn", 3), ("PARA_500", "1#qid prn", 5)]),
    (["下背痛", "肌肉拉傷", "扭傷"],
                          [("IBU_400", "1#tid pc", 5)]),
    (["關節炎", "OA"],     [("IBU_400", "1#bid pc", 7)]),
    (["前庭", "BPPV"],     [("PARA_500", "1#prn", 3)]),
    # 五官
    (["結膜炎"],           [("ARTIFICIAL_TEARS", "1滴qid", 7), ("ANTIBIOTIC_DROPS", "1滴qid", 7)]),
    (["外耳炎"],           [("ANTIHISTAMINE_DROPS", "2滴bid", 7)]),
    # 其他
    (["失眠", "焦慮"],     [("PARA_500", "1#hs prn", 5)]),
    (["發燒"],            [("PARA_500", "1#qid prn", 3)]),
    (["疲倦"],            [("VIT_C_500", "1#qd", 30)]),
    (["痛風"],            [("IBU_400", "1#tid", 5)]),
    (["骨質疏鬆"],         [("VIT_C_500", "1#qd", 30)]),  # demo 沒 calcium / VitD
]

DEFAULT_RX = [("PARA_500", "1#tid prn", 3)]


def pick_drugs_for_dx(dx: str) -> list[tuple[str, str, int]]:
    if not dx:
        return DEFAULT_RX
    for keywords, drugs in DX_TO_DRUGS:
        if any(k in dx for k in keywords):
            return drugs
    return DEFAULT_RX


def parse_daily_count(usage_text: str) -> int:
    """從 usage 字串簡單推每日次數 (qd=1, bid=2, tid=3, qid=4, prn 算 0.5)"""
    if "qd" in usage_text or "qid" in usage_text:
        # qid 比較少, 先測 qid
        if "qid" in usage_text:
            return 4
        return 1
    if "tid" in usage_text:
        return 3
    if "bid" in usage_text or "hs" in usage_text:
        return 2 if "bid" in usage_text else 1
    return 1


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

        # idempotent: 先刪 source='extended_mock' 的 prescription_items + prescriptions
        if not args.dry_run:
            n_item = db.execute(
                delete(PrescriptionItem).where(
                    PrescriptionItem.clinic_id == clinic.id,
                    PrescriptionItem.source == SOURCE_TAG,
                )
            ).rowcount
            n_rx = db.execute(
                delete(Prescription).where(
                    Prescription.clinic_id == clinic.id,
                    Prescription.source == SOURCE_TAG,
                )
            ).rowcount
            log.info("先刪舊 extended: %d prescriptions + %d items", n_rx, n_item)

        # drug code -> Drug ORM
        drug_by_code: dict[str, Drug] = {
            d.code: d for d in db.scalars(select(Drug).where(Drug.clinic_id == clinic.id)).all()
        }
        log.info("drug pool: %d", len(drug_by_code))

        # 拿所有 extended_mock visit (跳過 jimmy 5 個, 它們已有 prescription)
        visits = db.scalars(
            select(Visit).where(
                Visit.clinic_id == clinic.id,
                Visit.source == SOURCE_TAG,
                Visit.diagnosis.isnot(None),
            )
        ).all()
        log.info("處理 %d extended visit", len(visits))

        common = {
            "clinic_id": clinic.id,
            "source": SOURCE_TAG,
            "is_demo_data": True,
        }

        n_rx_added = 0
        n_item_added = 0
        skipped_no_drug = 0

        for v in visits:
            drug_specs = pick_drugs_for_dx(v.diagnosis or "")

            # 建 prescription row
            rx_uuid = uuid4()
            rx = Prescription(
                id=rx_uuid,
                visit_id=v.id,
                status="confirmed",
                **common,
            )
            db.add(rx)
            n_rx_added += 1

            # 建 prescription_items (跳過 DB 沒的 drug code)
            for drug_code, usage, days in drug_specs:
                drug = drug_by_code.get(drug_code)
                if not drug:
                    skipped_no_drug += 1
                    continue

                daily = parse_daily_count(usage)
                total_qty = max(daily * days, 1)
                unit_price = drug.unit_price or Decimal("1.0")
                total_price = unit_price * Decimal(total_qty)

                item = PrescriptionItem(
                    id=uuid4(),
                    prescription_id=rx_uuid,
                    drug_id=drug.id,
                    usage_text=usage,
                    daily_dose=Decimal(daily),
                    days=days,
                    total_quantity=total_qty,
                    unit_price_at_time=unit_price,
                    total_price=total_price,
                    **common,
                )
                db.add(item)
                n_item_added += 1

        if args.dry_run:
            db.rollback()
            log.info("[DRY RUN] 預計 +%d rx +%d items, skipped %d (drug not in DB)",
                     n_rx_added, n_item_added, skipped_no_drug)
        else:
            db.commit()
            log.info("=" * 60)
            log.info("Extend prescriptions 完成")
            log.info("  prescriptions       + %d", n_rx_added)
            log.info("  prescription_items  + %d", n_item_added)
            if skipped_no_drug:
                log.warning("  skipped (drug not in DB pool): %d", skipped_no_drug)
            log.info("=" * 60)
        return 0
    except Exception:
        db.rollback()
        log.exception("extend_prescriptions 失敗, rollback")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
