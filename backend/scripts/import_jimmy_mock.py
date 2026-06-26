"""
============================================================
scripts/import_jimmy_mock.py
============================================================
把外部 mock data（目前是 Jimmy 給的 schema）轉換成我這邊
backend/seed_data/mock_data.json 的 PLAN.md 規範格式。

設計原則：
1. 不改 ORM schema、不改 pipeline；只在 JSON 層做欄位映射
2. 多餘欄位（dose_unit, stock_status, address, allergies 等）忽略
3. Discount 用 other_fee 為負值的方式表達（避免 total_amount 對不上）
4. lab_fee + procedure_fee + certificate_fee + other_fee + (- discount) 全部合到 other_fee
5. 沒對應的 entity（fee_catalog / medical_documents / ai_drafts / agent_tasks
   / audit_logs / users / clinic）一律忽略並 log

跑法：
    python -m scripts.import_jimmy_mock \\
      --input /path/to/jimmy_mock.json \\
      --output backend/seed_data/mock_data.json
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# 欄位映射（Jimmy → 我）
# ============================================================
# 把 ref 字串重新命名（Jimmy 用 patient_001 / drug_amox_500 / batch_amox_01...
# 我們不要動 Jimmy 的 ref，因為他的 ref 跟其他 ref 互相 reference）
# 所以只把欄位「名稱」翻譯，不動 ref 「值」


def _decimal_str(value) -> str:
    """把 number → 字串（最多兩位小數）"""
    if value is None:
        return "0.00"
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


# ============================================================
# 各 entity 的轉換函數
# ============================================================
def _convert_patient(p: dict) -> dict:
    return {
        "ref": p["patient_ref"],
        "name": p["full_name"],
        "gender": p.get("gender"),
        "date_of_birth": p.get("date_of_birth"),
        "phone": p.get("phone"),
        "id_number": p.get("id_number"),
    }


def _convert_drug(d: dict) -> dict:
    return {
        "ref": d["drug_ref"],
        # code 用 drug_ref 字串本身（Jimmy 沒有獨立 code 欄位）
        "code": d["drug_ref"].upper().replace("DRUG_", ""),
        # 名字用 brand_name；如果沒有就退回 generic_name
        "name": d.get("brand_name") or d.get("generic_name") or d["drug_ref"],
        "unit": d.get("stock_unit", "unit"),
        "unit_price": _decimal_str(d.get("selling_price", 0)),
    }


def _convert_drug_batch(b: dict) -> dict:
    return {
        "ref": b["batch_ref"],
        "drug_ref": b["drug_ref"],
        "batch_no": b["batch_number"],
        "expiry_date": b["expiry_date"],
        "quantity_received": int(b["quantity_initial"]),
        "quantity_remaining": int(b["quantity_current"]),
        "cost_per_unit": _decimal_str(b.get("purchase_price", 0)),
        "received_date": b["received_date"],
    }


def _convert_visit(v: dict) -> dict:
    # 我們的 visit_date 接受 ISO datetime；Jimmy 用 'Z' 結尾，我們轉成 +00:00 兼容 fromisoformat
    visit_date = v.get("visit_date", "")
    if visit_date.endswith("Z"):
        visit_date = visit_date.replace("Z", "+00:00")

    # status 映射：Jimmy 用了 'ready_for_billing'，我的 minimal schema 沒這個值
    # 對應到 'completed'（看完診待收費）
    # 業務語義上一樣，等 Sprint 2 業務 logic 開發時再決定要不要把 ready_for_billing
    # 升格成 first-class status
    JIMMY_TO_OURS = {
        "ready_for_billing": "completed",
    }
    raw_status = v.get("status", "draft")
    status = JIMMY_TO_OURS.get(raw_status, raw_status)

    return {
        "ref": v["visit_ref"],
        "patient_ref": v["patient_ref"],
        "visit_date": visit_date,
        "chief_complaint": v.get("chief_complaint"),
        "diagnosis": v.get("diagnosis"),
        "status": status,
    }


def _convert_prescription_item(pi: dict) -> dict:
    # Jimmy 的 calculation_mode 兩種：
    #   - 'calculated_by_days': total = dose_quantity × frequency_per_day × duration_days
    #   - 'manual_quantity':    醫生直接給 total，不依賴 daily_dose × days
    #
    # 我的 schema 只認 daily_dose × days = total。
    # 所以對 manual mode，我們 normalize 成「daily_dose=total, days=1」
    # 讓 validate 的乘法檢查通過。這個 transform 是 lossy（失去原本的「手動」資訊），
    # 但對 minimal schema 而言 OK；之後 Sprint 2 業務 logic 補 calculation_mode 欄位後可以還原。

    total_qty = int(pi["total_quantity"])
    calc_mode = pi.get("calculation_mode", "calculated_by_days")

    if calc_mode == "manual_quantity":
        daily_dose = Decimal(total_qty)
        days = 1
    else:
        daily_dose = (
            Decimal(str(pi.get("dose_quantity", 1))) *
            Decimal(str(pi.get("frequency_per_day", 1)))
        )
        days = int(pi.get("duration_days", 1))

    return {
        "ref": pi["prescription_item_ref"],
        "visit_ref": pi["visit_ref"],
        "drug_ref": pi["drug_ref"],
        "usage_text": pi.get("instruction_text"),
        "daily_dose": str(daily_dose),
        "days": days,
        "total_quantity": total_qty,
        "unit_price_at_time": _decimal_str(pi["unit_price"]),
        "total_price": _decimal_str(pi["total_price"]),
    }


def _convert_invoice(inv: dict) -> dict:
    """
    Jimmy 有 lab_fee / procedure_fee / certificate_fee / discount_amount 等
    我的 schema 只有 consultation_fee / medication_fee / other_fee / total_amount。

    策略：
    other_fee = lab + procedure + certificate + jimmy_other - discount

    這樣 total = cons + med + other 仍然成立（因為 Jimmy 的 total 已經把
    discount 扣掉了）。
    """
    other_combined = (
        Decimal(str(inv.get("lab_fee", 0)))
        + Decimal(str(inv.get("procedure_fee", 0)))
        + Decimal(str(inv.get("certificate_fee", 0)))
        + Decimal(str(inv.get("other_fee", 0)))
        - Decimal(str(inv.get("discount_amount", 0)))
    )

    # void_reason 空字串轉 null（語意更清楚）
    void_reason = inv.get("void_reason")
    if void_reason == "":
        void_reason = None

    out = {
        "ref": inv["invoice_ref"],
        "visit_ref": inv["visit_ref"],
        "invoice_no": inv.get("invoice_number"),
        "consultation_fee": _decimal_str(inv.get("consultation_fee", 0)),
        "medication_fee": _decimal_str(inv.get("medication_fee", 0)),
        "other_fee": _decimal_str(other_combined),
        "total_amount": _decimal_str(inv.get("total_amount", 0)),
        "status": inv.get("status", "draft"),
    }
    if void_reason:
        out["void_reason"] = void_reason
    return out


def _convert_stock_movement(sm: dict) -> dict:
    out = {
        "ref": sm["movement_ref"],
        "batch_ref": sm["batch_ref"],
        "movement_type": sm["movement_type"],
        "quantity_change": int(sm["quantity_change"]),
        "note": sm.get("reason"),
    }
    if sm.get("related_prescription_item_ref"):
        out["related_prescription_item_ref"] = sm["related_prescription_item_ref"]
    if sm.get("related_invoice_ref"):
        out["related_invoice_ref"] = sm["related_invoice_ref"]
    return out


# ============================================================
# 主流程
# ============================================================
def convert(jimmy: dict) -> dict:
    """把 Jimmy 格式整體轉成我的格式。"""

    # 留 metadata 紀錄轉換來源
    out = {
        "metadata": {
            "version": "from-jimmy-via-adapter",
            "generator": "scripts/import_jimmy_mock.py",
            "source": "Jimmy (Gemini) mock data package",
            "purpose": (
                "Imported from Jimmy's external mock_data.json. "
                "Schema mapped to PLAN.md format. "
                "Some fields (dose_unit, stock_status, allergies, etc.) ignored."
            ),
        },
        "patients": [_convert_patient(p) for p in jimmy.get("patients", [])],
        "drugs": [_convert_drug(d) for d in jimmy.get("drugs", [])],
        "drug_batches": [
            _convert_drug_batch(b) for b in jimmy.get("drug_batches", [])
        ],
        "visits": [_convert_visit(v) for v in jimmy.get("visits", [])],
        "prescription_items": [
            _convert_prescription_item(pi)
            for pi in jimmy.get("prescription_items", [])
        ],
        "invoices": [_convert_invoice(inv) for inv in jimmy.get("invoices", [])],
        "stock_movements": [
            _convert_stock_movement(sm)
            for sm in jimmy.get("stock_movements", [])
        ],
    }

    # 報告忽略的 entity types
    ignored = []
    for k in [
        "clinic", "users", "fee_catalog",
        "medical_documents", "ai_drafts", "agent_tasks", "audit_logs",
    ]:
        if jimmy.get(k):
            v = jimmy[k]
            count = len(v) if isinstance(v, list) else 1
            ignored.append(f"{k}({count})")
    if ignored:
        logger.info(
            "ℹ️  忽略以下 entity（schema 未涵蓋或由 seed.py 處理）: %s",
            ", ".join(ignored),
        )

    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import Jimmy's external mock data into Clinic OS format"
    )
    parser.add_argument("--input", type=Path, required=True, help="Jimmy 的 JSON 路徑")
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[1] / "seed_data" / "mock_data.json",
        help="輸出路徑（預設覆蓋 seed_data/mock_data.json）",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error("❌ 找不到輸入檔: %s", args.input)
        return 1

    logger.info("讀取 Jimmy 的檔案: %s", args.input)
    jimmy = json.loads(args.input.read_text(encoding="utf-8"))

    converted = convert(jimmy)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(converted, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("✓ 寫入: %s", args.output)
    logger.info("─" * 60)
    logger.info("轉換後的筆數：")
    for key in [
        "patients", "drugs", "drug_batches",
        "visits", "prescription_items",
        "invoices", "stock_movements",
    ]:
        logger.info("  %-22s %d 筆", key, len(converted.get(key, [])))
    logger.info("─" * 60)
    logger.info("下一步：python -m scripts.validate_mock_data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
