"""
============================================================
scripts/validate_mock_data.py
============================================================
驗證 backend/seed_data/mock_data.json。

設計原則：
1. 純 JSON 驗證，**完全不碰 DB**
2. 蒐集所有錯誤再一次回報（不要遇到第一個就 abort），方便一輪修
3. 規格內所有 10 條檢查都實作

跑法：
    cd backend
    python -m scripts.validate_mock_data
    python -m scripts.validate_mock_data --file path/to/another.json

退出碼：
    0 = 通過
    1 = 至少有一條錯誤
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


DEFAULT_MOCK_PATH = Path(__file__).resolve().parents[1] / "seed_data" / "mock_data.json"


# ============================================================
# 錯誤蒐集器
# ============================================================
class ErrorCollector:
    """蒐集所有 validation error 一次回報。"""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ============================================================
# 資料 helpers
# ============================================================
def to_decimal(value: Any, *, field: str, errors: ErrorCollector) -> Decimal | None:
    """把字串/數字轉 Decimal；轉不了就記錯並回 None。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        errors.error(f"  {field}: 無法解析為 Decimal: {value!r}")
        return None


def quantize(d: Decimal) -> Decimal:
    """金額統一到小數兩位。"""
    return d.quantize(Decimal("0.01"))


# ============================================================
# 主流程
# ============================================================
def validate(data: dict) -> ErrorCollector:
    errors = ErrorCollector()

    # ─── 1. Top-level 結構 ───────────────────────────────
    required_arrays = [
        "patients", "drugs", "drug_batches",
        "visits", "prescription_items",
        "invoices", "stock_movements",
    ]
    for key in required_arrays:
        if key not in data:
            errors.error(f"[結構] 缺少 top-level 陣列: {key}")
        elif not isinstance(data[key], list):
            errors.error(f"[結構] {key} 不是 array")

    # 不允許 top-level 出現 prescriptions / invoice_items（由 seed 自動產生）
    for forbidden in ["prescriptions", "invoice_items"]:
        if forbidden in data and data[forbidden]:
            errors.warning(
                f"[結構] mock_data.json 包含 '{forbidden}'，"
                f"但 pipeline 會自動產生這個陣列。手動提供的內容會被忽略。"
            )

    if not errors.ok:
        return errors

    # ─── 2. 建索引（ref → 物件）─────────────────────────
    patients_by_ref = _index_by_ref(data["patients"], "patients", errors)
    drugs_by_ref = _index_by_ref(data["drugs"], "drugs", errors)
    batches_by_ref = _index_by_ref(data["drug_batches"], "drug_batches", errors)
    visits_by_ref = _index_by_ref(data["visits"], "visits", errors)
    presc_items_by_ref = _index_by_ref(
        data["prescription_items"], "prescription_items", errors
    )
    invoices_by_ref = _index_by_ref(data["invoices"], "invoices", errors)
    movements_by_ref = _index_by_ref(
        data["stock_movements"], "stock_movements", errors
    )

    # ─── 3. Reference 完整性（檢查 1）───────────────────
    _validate_refs(
        data,
        patients_by_ref=patients_by_ref,
        drugs_by_ref=drugs_by_ref,
        batches_by_ref=batches_by_ref,
        visits_by_ref=visits_by_ref,
        presc_items_by_ref=presc_items_by_ref,
        invoices_by_ref=invoices_by_ref,
        errors=errors,
    )

    # ─── 4. prescription_items 內部一致（檢查 2、3）─────
    _validate_prescription_items(
        data["prescription_items"],
        drugs_by_ref=drugs_by_ref,
        errors=errors,
    )

    # ─── 5. invoice 內部一致（檢查 4、5）────────────────
    _validate_invoices(
        data["invoices"],
        prescription_items=data["prescription_items"],
        errors=errors,
    )

    # ─── 6. stock_movements（檢查 6）────────────────────
    _validate_stock_movements(
        data["stock_movements"],
        batches_by_ref=batches_by_ref,
        presc_items_by_ref=presc_items_by_ref,
        invoices_by_ref=invoices_by_ref,
        errors=errors,
    )

    # ─── 7. voided invoice 規則（檢查 7、8）─────────────
    _validate_voided_invoices(
        data["invoices"],
        prescription_items=data["prescription_items"],
        stock_movements=data["stock_movements"],
        errors=errors,
    )

    # ─── 8. FEFO 跨 batch（檢查 9）──────────────────────
    _validate_fefo_scenario(data["stock_movements"], errors)

    # ─── 9. dispense 數量等於 prescription_item 總量 ────
    _validate_dispense_totals(
        data["prescription_items"],
        data["stock_movements"],
        errors=errors,
    )

    return errors


def _index_by_ref(items: list, label: str, errors: ErrorCollector) -> dict:
    """把陣列依 'ref' 建索引；同時檢查 ref 唯一。"""
    out = {}
    for idx, item in enumerate(items):
        ref = item.get("ref")
        if not ref:
            errors.error(f"[{label}] 第 {idx} 筆缺少 'ref' 欄位")
            continue
        if ref in out:
            errors.error(f"[{label}] ref 重複: {ref!r}")
            continue
        out[ref] = item
    return out


# ─── 檢查 1：所有 *_ref 指向實際物件 ─────────────────────
def _validate_refs(
    data: dict,
    *,
    patients_by_ref: dict,
    drugs_by_ref: dict,
    batches_by_ref: dict,
    visits_by_ref: dict,
    presc_items_by_ref: dict,
    invoices_by_ref: dict,
    errors: ErrorCollector,
) -> None:
    # visits.patient_ref → patients
    for v in data["visits"]:
        if v.get("patient_ref") not in patients_by_ref:
            errors.error(
                f"[visits] {v.get('ref')!r}: patient_ref={v.get('patient_ref')!r} 不存在"
            )

    # drug_batches.drug_ref → drugs
    for b in data["drug_batches"]:
        if b.get("drug_ref") not in drugs_by_ref:
            errors.error(
                f"[drug_batches] {b.get('ref')!r}: drug_ref={b.get('drug_ref')!r} 不存在"
            )

    # prescription_items.visit_ref → visits / drug_ref → drugs
    for pi in data["prescription_items"]:
        if pi.get("visit_ref") not in visits_by_ref:
            errors.error(
                f"[prescription_items] {pi.get('ref')!r}: "
                f"visit_ref={pi.get('visit_ref')!r} 不存在"
            )
        if pi.get("drug_ref") not in drugs_by_ref:
            errors.error(
                f"[prescription_items] {pi.get('ref')!r}: "
                f"drug_ref={pi.get('drug_ref')!r} 不存在"
            )

    # invoices.visit_ref → visits
    for inv in data["invoices"]:
        if inv.get("visit_ref") not in visits_by_ref:
            errors.error(
                f"[invoices] {inv.get('ref')!r}: "
                f"visit_ref={inv.get('visit_ref')!r} 不存在"
            )

    # stock_movements.batch_ref → drug_batches
    # stock_movements.related_*_ref → 對應表
    for sm in data["stock_movements"]:
        ref = sm.get("ref")
        if sm.get("batch_ref") not in batches_by_ref:
            errors.error(
                f"[stock_movements] {ref!r}: "
                f"batch_ref={sm.get('batch_ref')!r} 不存在"
            )

        rel_pi = sm.get("related_prescription_item_ref")
        if rel_pi is not None and rel_pi not in presc_items_by_ref:
            errors.error(
                f"[stock_movements] {ref!r}: "
                f"related_prescription_item_ref={rel_pi!r} 不存在"
            )

        rel_inv = sm.get("related_invoice_ref")
        if rel_inv is not None and rel_inv not in invoices_by_ref:
            errors.error(
                f"[stock_movements] {ref!r}: "
                f"related_invoice_ref={rel_inv!r} 不存在"
            )


# ─── 檢查 2、3：prescription_items 計算 ──────────────────
def _validate_prescription_items(
    items: list, *, drugs_by_ref: dict, errors: ErrorCollector
) -> None:
    for pi in items:
        ref = pi.get("ref")
        daily_dose = to_decimal(pi.get("daily_dose"), field=f"pi[{ref}].daily_dose", errors=errors)
        days = pi.get("days")
        total_q = pi.get("total_quantity")
        unit_price = to_decimal(
            pi.get("unit_price_at_time"),
            field=f"pi[{ref}].unit_price_at_time",
            errors=errors,
        )
        total_p = to_decimal(
            pi.get("total_price"), field=f"pi[{ref}].total_price", errors=errors
        )

        if daily_dose is None or days is None or total_q is None:
            continue

        # 檢查 2: total_quantity = daily_dose × days
        # daily_dose 可能不是整數（例如 0.5 顆），但 total_quantity 應該是整數
        expected_q = daily_dose * Decimal(days)
        if Decimal(total_q) != expected_q:
            errors.error(
                f"[prescription_items] {ref!r}: "
                f"total_quantity={total_q} 應該等於 "
                f"daily_dose({daily_dose}) × days({days}) = {expected_q}"
            )

        if unit_price is None or total_p is None:
            continue

        # 檢查 3: total_price = total_quantity × unit_price_at_time
        expected_price = quantize(Decimal(total_q) * unit_price)
        if quantize(total_p) != expected_price:
            errors.error(
                f"[prescription_items] {ref!r}: "
                f"total_price={total_p} 應該等於 "
                f"total_quantity({total_q}) × unit_price({unit_price}) = {expected_price}"
            )


# ─── 檢查 4、5：invoice 金額 ─────────────────────────────
def _validate_invoices(
    invoices: list, *, prescription_items: list, errors: ErrorCollector
) -> None:
    # 先 group prescription_items by visit_ref
    pi_total_by_visit: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for pi in prescription_items:
        visit_ref = pi.get("visit_ref")
        price = to_decimal(
            pi.get("total_price"),
            field=f"pi[{pi.get('ref')}].total_price",
            errors=errors,
        )
        if visit_ref and price is not None:
            pi_total_by_visit[visit_ref] += price

    for inv in invoices:
        ref = inv.get("ref")
        visit_ref = inv.get("visit_ref")
        consultation = to_decimal(
            inv.get("consultation_fee"), field=f"inv[{ref}].consultation_fee", errors=errors
        )
        medication = to_decimal(
            inv.get("medication_fee"), field=f"inv[{ref}].medication_fee", errors=errors
        )
        other = to_decimal(
            inv.get("other_fee"), field=f"inv[{ref}].other_fee", errors=errors
        )
        total = to_decimal(
            inv.get("total_amount"), field=f"inv[{ref}].total_amount", errors=errors
        )

        if None in (consultation, medication, other, total):
            continue

        # 檢查 4: medication_fee 對得上 prescription_items
        expected_med = pi_total_by_visit.get(visit_ref, Decimal("0"))
        if quantize(medication) != quantize(expected_med):
            errors.error(
                f"[invoices] {ref!r}: medication_fee={medication} "
                f"應該等於 visit={visit_ref} 的 prescription_items 加總 ({expected_med})"
            )

        # 檢查 5: total_amount = consultation + medication + other
        expected_total = quantize(consultation + medication + other)
        if quantize(total) != expected_total:
            errors.error(
                f"[invoices] {ref!r}: total_amount={total} "
                f"應該等於 consultation+medication+other = {expected_total}"
            )


# ─── 檢查 6：stock_movements.batch_ref 已在 _validate_refs 處理 ───
def _validate_stock_movements(
    movements: list,
    *,
    batches_by_ref: dict,
    presc_items_by_ref: dict,
    invoices_by_ref: dict,
    errors: ErrorCollector,
) -> None:
    valid_types = {"purchase", "dispense", "adjust", "void_reverse", "expire"}
    for sm in movements:
        ref = sm.get("ref")
        mtype = sm.get("movement_type")
        if mtype not in valid_types:
            errors.error(
                f"[stock_movements] {ref!r}: movement_type={mtype!r} 不合法 "
                f"(必須是 {sorted(valid_types)})"
            )

        qty = sm.get("quantity_change")
        if not isinstance(qty, int) or qty == 0:
            errors.error(
                f"[stock_movements] {ref!r}: quantity_change={qty!r} "
                f"必須是非零整數"
            )
            continue

        # 方向檢查
        positive_types = {"purchase", "void_reverse"}
        negative_types = {"dispense", "expire"}
        if mtype in positive_types and qty <= 0:
            errors.error(
                f"[stock_movements] {ref!r}: {mtype} 的 quantity_change 應為正"
            )
        if mtype in negative_types and qty >= 0:
            errors.error(
                f"[stock_movements] {ref!r}: {mtype} 的 quantity_change 應為負"
            )


# ─── 檢查 7、8：voided invoice ───────────────────────────
def _validate_voided_invoices(
    invoices: list,
    *,
    prescription_items: list,
    stock_movements: list,
    errors: ErrorCollector,
) -> None:
    # 建 visit → prescription_items 索引
    pi_by_visit: dict[str, list] = defaultdict(list)
    for pi in prescription_items:
        if pi.get("visit_ref"):
            pi_by_visit[pi["visit_ref"]].append(pi)

    # 建 invoice → void_reverse movements 索引
    void_reverse_by_inv: dict[str, list] = defaultdict(list)
    for sm in stock_movements:
        if sm.get("movement_type") == "void_reverse":
            inv_ref = sm.get("related_invoice_ref")
            if inv_ref:
                void_reverse_by_inv[inv_ref].append(sm)

    for inv in invoices:
        if inv.get("status") != "voided":
            continue

        ref = inv.get("ref")

        # 檢查 7：必須有 void_reason
        if not inv.get("void_reason"):
            errors.error(f"[invoices] {ref!r}: voided 但缺少 void_reason")

        # 檢查 8：必須有對應的 void_reverse stock_movements
        # 規則：每個對應 visit 的 prescription_item 都該有等量回補
        visit_ref = inv.get("visit_ref")
        related_pis = pi_by_visit.get(visit_ref, [])
        if not related_pis:
            # 沒處方就不用回補（純 consultation 收據作廢）
            continue

        reverse_movements = void_reverse_by_inv.get(ref, [])
        if not reverse_movements:
            errors.error(
                f"[invoices] {ref!r}: voided 但找不到任何 void_reverse "
                f"stock_movement（related_invoice_ref={ref}）"
            )
            continue

        # 比對總量：reverse 加總應等於 prescription_items.total_quantity 加總
        # （簡化版：不檢查 batch-by-batch，只看總帳）
        expected_total = sum(int(pi.get("total_quantity", 0)) for pi in related_pis)
        actual_total = sum(int(sm.get("quantity_change", 0)) for sm in reverse_movements)
        if actual_total != expected_total:
            errors.error(
                f"[invoices] {ref!r}: void_reverse 總量={actual_total} "
                f"應該等於原處方總量 {expected_total}"
            )


# ─── 檢查 9：FEFO 跨 batch ───────────────────────────────
def _validate_fefo_scenario(
    stock_movements: list, errors: ErrorCollector
) -> None:
    """至少存在一個 prescription_item 對應到 ≥ 2 個 dispense movement（不同 batch）"""
    by_pi_ref: dict[str, set] = defaultdict(set)
    for sm in stock_movements:
        if sm.get("movement_type") == "dispense":
            pi_ref = sm.get("related_prescription_item_ref")
            if pi_ref:
                by_pi_ref[pi_ref].add(sm.get("batch_ref"))

    cross_batch_pis = [
        pi_ref for pi_ref, batches in by_pi_ref.items() if len(batches) >= 2
    ]
    if not cross_batch_pis:
        errors.error(
            "[FEFO] 沒有跨 batch 的 dispense 場景。"
            "需要至少一個 prescription_item 從 ≥ 2 個 batch 扣藥（演示 FEFO）"
        )


# ─── 額外檢查：dispense 數量加總 = prescription_item.total_quantity 或 0 ──
def _validate_dispense_totals(
    prescription_items: list, stock_movements: list, errors: ErrorCollector
) -> None:
    """
    檢查每個 prescription_item 的 net dispensed（dispense - void_reverse）。

    合理結果只有兩個：
    - 0：未發藥（draft / 過敏 block / 庫存不足 / 已作廢回補）
    - == total_quantity：已完整發藥

    其他都是 error（V1 不支援 partial dispense）。
    """
    dispense_by_pi: dict[str, int] = defaultdict(int)
    void_reverse_by_pi: dict[str, int] = defaultdict(int)

    for sm in stock_movements:
        pi_ref = sm.get("related_prescription_item_ref")
        if not pi_ref:
            continue
        qty = int(sm.get("quantity_change", 0))
        mtype = sm.get("movement_type")
        if mtype == "dispense":
            dispense_by_pi[pi_ref] += abs(qty)
        elif mtype == "void_reverse":
            void_reverse_by_pi[pi_ref] += qty  # 已是正值

    for pi in prescription_items:
        ref = pi.get("ref")
        expected = int(pi.get("total_quantity", 0))
        dispensed = dispense_by_pi.get(ref, 0)
        reversed_qty = void_reverse_by_pi.get(ref, 0)
        net = dispensed - reversed_qty

        # 允許兩種狀態：完全沒扣、或剛好扣完
        if net not in (0, expected):
            errors.error(
                f"[dispense] prescription_item {ref!r}: "
                f"net dispensed={net} 應該是 0（未發藥/已抵銷）"
                f"或 {expected}（已發完）。"
                f"明細：dispense={dispensed}, void_reverse={reversed_qty}"
            )


# ============================================================
# CLI
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Clinic OS mock data JSON")
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_MOCK_PATH,
        help=f"mock_data.json 路徑（預設 {DEFAULT_MOCK_PATH}）"
    )
    args = parser.parse_args()

    if not args.file.exists():
        logger.error("❌ 檔案不存在: %s", args.file)
        return 1

    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("❌ JSON 解析失敗: %s", exc)
        return 1

    errors = validate(data)

    # 印 summary
    logger.info("─" * 60)
    logger.info("驗證檔案：%s", args.file)
    logger.info("─" * 60)

    if errors.warnings:
        logger.info("⚠️  Warnings (%d)：", len(errors.warnings))
        for w in errors.warnings:
            logger.info("   • %s", w)
        logger.info("")

    if errors.errors:
        logger.info("❌ Errors (%d)：", len(errors.errors))
        for e in errors.errors:
            logger.info("   • %s", e)
        logger.info("─" * 60)
        logger.info("總共 %d 個錯誤，未通過。", len(errors.errors))
        return 1

    # 通過時印統計
    logger.info("✅ 通過所有檢查")
    logger.info("")
    logger.info("資料統計：")
    for key in [
        "patients", "drugs", "drug_batches",
        "visits", "prescription_items",
        "invoices", "stock_movements",
    ]:
        logger.info("  %-22s %d 筆", key, len(data.get(key, [])))
    logger.info("─" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
