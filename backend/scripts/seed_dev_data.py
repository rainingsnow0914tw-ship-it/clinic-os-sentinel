"""
============================================================
scripts/seed_dev_data.py
============================================================
把 backend/seed_data/mock_data.json 灌進資料庫。

設計重點：
1. **環境守門**：只在 ENVIRONMENT in {dev, sandbox} 才允許跑。prod / staging 直接拒絕。
2. **跑 validate 之前不 seed**：把 validate_mock_data 的邏輯先當前置條件
3. **自動產生 prescriptions**：mock JSON 不放，從 prescription_items 的 visit_ref 推
4. **自動產生 invoice_items**：mock JSON 不放，從 invoices + prescription_items 推
5. 全程在一個 transaction 內，失敗整體 rollback
6. 所有寫入的 row 都 source='mock' / is_demo_data=True，方便 reset

跑法：
    cd backend
    ENVIRONMENT=dev python -m scripts.seed_dev_data

或指定其他來源：
    ENVIRONMENT=sandbox python -m scripts.seed_dev_data --file path/to/another.json

⚠️ 必須先有 clinics + users + clinic_memberships（透過 seed.py），這個腳本只負責
   seed 業務資料。
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    SOURCE_MOCK,
    Clinic,
    ClinicMembership,
    Drug,
    DrugBatch,
    Invoice,
    InvoiceItem,
    Patient,
    Prescription,
    PrescriptionItem,
    StockMovement,
    User,
    Visit,
)
from scripts.validate_mock_data import validate

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


DEFAULT_MOCK_PATH = Path(__file__).resolve().parents[1] / "seed_data" / "mock_data.json"

ALLOWED_ENVIRONMENTS = {"dev", "sandbox", "development"}


# ============================================================
# 環境守門
# ============================================================
def assert_dev_environment() -> str:
    env = os.environ.get("ENVIRONMENT", "").lower().strip()
    if env not in ALLOWED_ENVIRONMENTS:
        logger.error("─" * 60)
        logger.error("❌ 拒絕執行 seed_dev_data")
        logger.error("─" * 60)
        logger.error("ENVIRONMENT 變數 = %r", env or "（未設定）")
        logger.error("seed_dev_data 只允許在以下環境跑：%s", sorted(ALLOWED_ENVIRONMENTS))
        logger.error("如果妳真的要跑：")
        logger.error("    ENVIRONMENT=dev python -m scripts.seed_dev_data")
        logger.error("─" * 60)
        sys.exit(1)
    return env


# ============================================================
# 主流程
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Clinic OS dev mock data")
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_MOCK_PATH,
        help=f"mock_data.json 路徑（預設 {DEFAULT_MOCK_PATH}）",
    )
    parser.add_argument(
        "--clinic-id", type=str, default=None,
        help="目標 clinic UUID（不給則挑 DB 第一個 clinic）",
    )
    args = parser.parse_args()

    env = assert_dev_environment()
    logger.info("🟢 ENVIRONMENT=%s — seed 允許執行", env)

    # ─── 1. 讀檔 + validate ────────────────────────────
    if not args.file.exists():
        logger.error("❌ 找不到 mock data: %s", args.file)
        return 1

    data = json.loads(args.file.read_text(encoding="utf-8"))
    errors = validate(data)
    if not errors.ok:
        logger.error("❌ Validate 沒過，共 %d 個錯誤。終止 seed。", len(errors.errors))
        for e in errors.errors:
            logger.error("   • %s", e)
        return 1
    logger.info("✓ Validate 通過")

    # ─── 2. 連 DB + 找 clinic / owner ──────────────────
    db: Session = SessionLocal()
    try:
        clinic, owner_user = _resolve_clinic_and_owner(db, args.clinic_id)
        logger.info(
            "✓ 目標 clinic=%s (id=%s), owner=%s (id=%s)",
            clinic.name, clinic.id, owner_user.email, owner_user.id,
        )

        # ─── 3. seed entities（一個 transaction）────
        stats = _seed_all(db, data, clinic=clinic, owner_user=owner_user)
        db.commit()

        logger.info("─" * 60)
        logger.info("🎉 Seed 完成")
        logger.info("─" * 60)
        for table, count in stats.items():
            logger.info("  %-22s + %d 筆", table, count)
        logger.info("─" * 60)
        return 0
    except Exception as exc:
        db.rollback()
        logger.error("❌ Seed 失敗，整體 rollback: %s", exc, exc_info=True)
        return 1
    finally:
        db.close()


# ============================================================
# 找 clinic / owner
# ============================================================
def _resolve_clinic_and_owner(
    db: Session, clinic_id_str: str | None
) -> tuple[Clinic, User]:
    if clinic_id_str:
        try:
            clinic_id = UUID(clinic_id_str)
        except ValueError as exc:
            raise RuntimeError(f"無法解析 --clinic-id={clinic_id_str!r}") from exc
        clinic = db.get(Clinic, clinic_id)
        if not clinic:
            raise RuntimeError(f"找不到 clinic id={clinic_id}")
    else:
        clinic = db.execute(select(Clinic).order_by(Clinic.created_at)).scalars().first()
        if not clinic:
            raise RuntimeError(
                "DB 沒有任何 clinic。請先跑 scripts/seed.py 建立第一間診所。"
            )

    # 找該 clinic 的 owner
    owner_membership = (
        db.execute(
            select(ClinicMembership)
            .where(
                ClinicMembership.clinic_id == clinic.id,
                ClinicMembership.role == "owner",
                ClinicMembership.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if not owner_membership:
        raise RuntimeError(
            f"clinic id={clinic.id} 沒有 active owner，先跑 scripts/seed.py"
        )

    owner_user = db.get(User, owner_membership.user_id)
    return clinic, owner_user


# ============================================================
# 主 seed 邏輯
# ============================================================
def _seed_all(
    db: Session, data: dict, *, clinic: Clinic, owner_user: User
) -> dict[str, int]:
    """
    依正確順序 seed 所有 entity，並維護 ref → uuid 的映射。
    回傳每張表的筆數統計。
    """
    common = {
        "clinic_id": clinic.id,
        "source": SOURCE_MOCK,
        "is_demo_data": True,
    }

    # ref → uuid 索引
    patient_id_by_ref: dict[str, UUID] = {}
    drug_id_by_ref: dict[str, UUID] = {}
    batch_id_by_ref: dict[str, UUID] = {}
    visit_id_by_ref: dict[str, UUID] = {}
    presc_item_id_by_ref: dict[str, UUID] = {}
    invoice_id_by_ref: dict[str, UUID] = {}

    stats: dict[str, int] = {}

    # ─── patients ──────────────────────────────────────
    for p in data["patients"]:
        obj = Patient(
            id=uuid4(),
            name=p["name"],
            gender=p.get("gender"),
            date_of_birth=_to_date(p.get("date_of_birth")),
            phone=p.get("phone"),
            id_number=p.get("id_number"),
            **common,
        )
        db.add(obj)
        patient_id_by_ref[p["ref"]] = obj.id
    stats["patients"] = len(data["patients"])
    db.flush()

    # ─── drugs ─────────────────────────────────────────
    for d in data["drugs"]:
        obj = Drug(
            id=uuid4(),
            code=d["code"],
            name=d["name"],
            unit=d["unit"],
            unit_price=Decimal(str(d["unit_price"])),
            **common,
        )
        db.add(obj)
        drug_id_by_ref[d["ref"]] = obj.id
    stats["drugs"] = len(data["drugs"])
    db.flush()

    # ─── drug_batches ──────────────────────────────────
    for b in data["drug_batches"]:
        obj = DrugBatch(
            id=uuid4(),
            drug_id=drug_id_by_ref[b["drug_ref"]],
            batch_no=b["batch_no"],
            expiry_date=_to_date(b["expiry_date"]),
            quantity_received=int(b["quantity_received"]),
            quantity_remaining=int(b["quantity_remaining"]),
            cost_per_unit=Decimal(str(b["cost_per_unit"])),
            received_date=_to_date(b["received_date"]),
            **common,
        )
        db.add(obj)
        batch_id_by_ref[b["ref"]] = obj.id
    stats["drug_batches"] = len(data["drug_batches"])
    db.flush()

    # ─── visits ────────────────────────────────────────
    for v in data["visits"]:
        obj = Visit(
            id=uuid4(),
            patient_id=patient_id_by_ref[v["patient_ref"]],
            doctor_user_id=owner_user.id,  # demo 全掛在 owner 身上
            visit_date=_to_datetime(v["visit_date"]),
            chief_complaint=v.get("chief_complaint"),
            diagnosis=v.get("diagnosis"),
            status=v.get("status", "draft"),
            **common,
        )
        db.add(obj)
        visit_id_by_ref[v["ref"]] = obj.id
    stats["visits"] = len(data["visits"])
    db.flush()

    # ─── prescriptions（auto-generate from prescription_items.visit_ref）
    visits_with_items = sorted({pi["visit_ref"] for pi in data["prescription_items"]})
    presc_id_by_visit_ref: dict[str, UUID] = {}
    for visit_ref in visits_with_items:
        obj = Prescription(
            id=uuid4(),
            visit_id=visit_id_by_ref[visit_ref],
            status="dispensed",  # 配合 mock data 的 invoiced visit 狀態
            **common,
        )
        db.add(obj)
        presc_id_by_visit_ref[visit_ref] = obj.id
    stats["prescriptions"] = len(visits_with_items)
    db.flush()

    # ─── prescription_items ────────────────────────────
    for pi in data["prescription_items"]:
        obj = PrescriptionItem(
            id=uuid4(),
            prescription_id=presc_id_by_visit_ref[pi["visit_ref"]],
            drug_id=drug_id_by_ref[pi["drug_ref"]],
            usage_text=pi.get("usage_text"),
            daily_dose=Decimal(str(pi["daily_dose"])),
            days=int(pi["days"]),
            total_quantity=int(pi["total_quantity"]),
            unit_price_at_time=Decimal(str(pi["unit_price_at_time"])),
            total_price=Decimal(str(pi["total_price"])),
            **common,
        )
        db.add(obj)
        presc_item_id_by_ref[pi["ref"]] = obj.id
    stats["prescription_items"] = len(data["prescription_items"])
    db.flush()

    # ─── invoices ──────────────────────────────────────
    for inv in data["invoices"]:
        obj = Invoice(
            id=uuid4(),
            visit_id=visit_id_by_ref[inv["visit_ref"]],
            invoice_no=inv.get("invoice_no"),
            consultation_fee=Decimal(str(inv["consultation_fee"])),
            medication_fee=Decimal(str(inv["medication_fee"])),
            other_fee=Decimal(str(inv["other_fee"])),
            total_amount=Decimal(str(inv["total_amount"])),
            status=inv.get("status", "draft"),
            issued_at=_to_datetime(inv.get("issued_at")),
            void_reason=inv.get("void_reason"),
            voided_at=_to_datetime(inv.get("voided_at")),
            **common,
        )
        db.add(obj)
        invoice_id_by_ref[inv["ref"]] = obj.id
    stats["invoices"] = len(data["invoices"])
    db.flush()

    # ─── invoice_items（auto-generate）─────────────────
    # 規則：
    #   1. 每張 invoice 一筆 consultation item（金額 = consultation_fee）
    #   2. 每個對應 visit 的 prescription_item 一筆 medication item
    #   3. 若 other_fee > 0 → 一筆 other item
    invoice_items_count = 0
    for inv in data["invoices"]:
        invoice_id = invoice_id_by_ref[inv["ref"]]
        visit_ref = inv["visit_ref"]

        # consultation
        consultation_fee = Decimal(str(inv["consultation_fee"]))
        if consultation_fee > 0:
            db.add(InvoiceItem(
                id=uuid4(),
                invoice_id=invoice_id,
                item_type="consultation",
                description="診療費",
                quantity=1,
                unit_price=consultation_fee,
                line_total=consultation_fee,
                source_entity_type=None,
                source_entity_id=None,
                **common,
            ))
            invoice_items_count += 1

        # medication（從同 visit 的 prescription_items 展開）
        for pi in data["prescription_items"]:
            if pi["visit_ref"] != visit_ref:
                continue
            drug = next(d for d in data["drugs"] if d["ref"] == pi["drug_ref"])
            db.add(InvoiceItem(
                id=uuid4(),
                invoice_id=invoice_id,
                item_type="medication",
                description=f"{drug['name']} × {pi['total_quantity']} {drug['unit']}",
                quantity=int(pi["total_quantity"]),
                unit_price=Decimal(str(pi["unit_price_at_time"])),
                line_total=Decimal(str(pi["total_price"])),
                source_entity_type="prescription_item",
                source_entity_id=presc_item_id_by_ref[pi["ref"]],
                **common,
            ))
            invoice_items_count += 1

        # other
        other_fee = Decimal(str(inv["other_fee"]))
        if other_fee > 0:
            db.add(InvoiceItem(
                id=uuid4(),
                invoice_id=invoice_id,
                item_type="other",
                description="其他費用",
                quantity=1,
                unit_price=other_fee,
                line_total=other_fee,
                source_entity_type=None,
                source_entity_id=None,
                **common,
            ))
            invoice_items_count += 1
    stats["invoice_items"] = invoice_items_count
    db.flush()

    # ─── stock_movements ───────────────────────────────
    # ⚠️ 設計：mock 中 batch.quantity_remaining 是「當前 snapshot」，
    # stock_movements 是「相關歷史事件的紀錄」（不一定涵蓋所有歷史）。
    # 因此 seed 階段我們只插入 movement 紀錄，不重新模擬扣庫存。
    # 這跟 production 的「movements 是真理之源」不衝突 — production 一定每筆
    # 扣藥都有 movement，且程式維護 invariant；mock 是給 dev/sandbox 看的快照。
    for sm in data["stock_movements"]:
        rel_type = None
        rel_id = None
        if sm.get("related_prescription_item_ref"):
            rel_type = "prescription_item"
            rel_id = presc_item_id_by_ref[sm["related_prescription_item_ref"]]
        elif sm.get("related_invoice_ref"):
            rel_type = "invoice"
            rel_id = invoice_id_by_ref[sm["related_invoice_ref"]]

        obj = StockMovement(
            id=uuid4(),
            drug_batch_id=batch_id_by_ref[sm["batch_ref"]],
            movement_type=sm["movement_type"],
            quantity_change=int(sm["quantity_change"]),
            related_entity_type=rel_type,
            related_entity_id=rel_id,
            note=sm.get("note"),
            **common,
        )
        db.add(obj)
    stats["stock_movements"] = len(data["stock_movements"])
    db.flush()

    return stats


# ============================================================
# 小工具
# ============================================================
def _to_date(s: Any):
    if not s:
        return None
    return datetime.fromisoformat(s).date() if "T" not in s else datetime.fromisoformat(s).date()


def _to_datetime(s: Any):
    if not s:
        return None
    return datetime.fromisoformat(s)


if __name__ == "__main__":
    sys.exit(main())
