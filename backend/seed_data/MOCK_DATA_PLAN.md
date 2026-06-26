# Mock Data Plan

> 這份是給 Jimmy（Gemini）的交付規格 + 阿寶（Claude）的接收口徑。
> 確保 Jimmy 的內容貼進來時，pipeline 不需要任何修改就能跑。

---

## 為什麼要 mock data

1. **整合測試**：Sprint 2~5 業務流程開發時不需要每次手動 seed
2. **示範 / Demo**：給投資人、合作診所、新進員工看「系統長怎樣」
3. **Bug 重現**：把 bug 對應的資料情境壓進 mock，自動化重現
4. **權限矩陣壓測**：跨角色（doctor / nurse / reception）操作要能用 mock 全跑一遍

---

## 交付格式

**唯一接收口**：`backend/seed_data/mock_data.json`

不要交付 Markdown table、Excel、CSV、Notion 表格。pipeline 只認這份 JSON。

格式必須符合 [JSON 結構規範](#json-結構規範)，並通過 `python -m scripts.validate_mock_data` 驗證。

---

## JSON 結構規範

### Top-level

```json
{
  "metadata": { "version": "...", "generator": "...", "purpose": "..." },
  "patients": [ ... ],
  "drugs": [ ... ],
  "drug_batches": [ ... ],
  "visits": [ ... ],
  "prescription_items": [ ... ],
  "invoices": [ ... ],
  "stock_movements": [ ... ]
}
```

⚠️ **不要**自己塞 `prescriptions` 或 `invoice_items` 陣列。
這兩個由 seed script 自動推導：
- `prescriptions` 從 `prescription_items` 的 `visit_ref` group by 建立
- `invoice_items` 從 `invoices` + `prescription_items` 自動展開

### 引用規則

- 所有跨表 reference 一律用 `*_ref` 字串（不是 UUID）
- `*_ref` 值在同類陣列內必須唯一（例如 `patient-001` 在 patients 裡只能出現一次）
- pipeline 在 seed 時把 `*_ref` 解析成真實 UUID

| Reference 欄位 | 指向 | 範例 |
|---|---|---|
| `patient_ref` | patients[*].ref | `"patient-001"` |
| `drug_ref` | drugs[*].ref | `"drug-amox"` |
| `visit_ref` | visits[*].ref | `"visit-002"` |
| `batch_ref` | drug_batches[*].ref | `"batch-amox-A"` |
| `related_prescription_item_ref` | prescription_items[*].ref | `"pi-003"` |
| `related_invoice_ref` | invoices[*].ref | `"inv-003"` |

### 金額格式

- 金額一律用 **字串** 格式儲存，最多兩位小數：`"30.00"`、`"105.50"`
- ❌ 不要寫 `30`（整數）或 `30.0`（一位小數）
- 原因：避免 JS / JSON 的 float 精度問題

### 日期格式

- 日期欄位（出生日、有效期限等）：ISO date 字串 `"2026-08-31"`
- 時間欄位（visit_date 等）：ISO datetime + 時區 `"2026-04-25T10:30:00+08:00"`

---

## 必要欄位清單

### `patients`
- `ref` *、`name` *、`gender`（M/F/other）、`date_of_birth`、`phone`、`id_number`

### `drugs`
- `ref` *、`code` *、`name` *、`unit` *（tablet/ml/cap）、`unit_price` *

### `drug_batches`
- `ref` *、`drug_ref` *、`batch_no` *、`expiry_date` *
- `quantity_received` *、`quantity_remaining` *、`cost_per_unit` *、`received_date` *

### `visits`
- `ref` *、`patient_ref` *、`visit_date` *
- `chief_complaint`、`diagnosis`、`status` *

### `prescription_items`
- `ref` *、`visit_ref` *、`drug_ref` *
- `usage_text`、`daily_dose` *、`days` *
- `total_quantity` *、`unit_price_at_time` *、`total_price` *

### `invoices`
- `ref` *、`visit_ref` *、`invoice_no`
- `consultation_fee` *、`medication_fee` *、`other_fee` *、`total_amount` *
- `status` *、`issued_at`
- 若 `status="voided"`：`void_reason` 必填、`voided_at` 必填

### `stock_movements`
- `ref` *、`batch_ref` *、`movement_type` *、`quantity_change` *
- `related_prescription_item_ref` 或 `related_invoice_ref`（看類型）
- `note`

(* = 必填)

---

## Validation 必須通過

`python -m scripts.validate_mock_data` 會檢查：

1. ✅ 所有 `*_ref` 指向實際存在的物件
2. ✅ `prescription_items.total_quantity == daily_dose × days`
3. ✅ `prescription_items.total_price == total_quantity × unit_price_at_time`
4. ✅ `invoices.medication_fee == sum(對應 visit 的 prescription_items.total_price)`
5. ✅ `invoices.total_amount == consultation + medication + other`
6. ✅ `voided` invoice 必須有 `void_reason` 與對應的 `void_reverse` stock_movement
7. ✅ 至少存在一個跨 batch 的 dispense 場景（FEFO 演示用）
8. ✅ 同一 prescription_item 的 dispense movement 加總 = `prescription_item.total_quantity`

---

## Jimmy 交付後阿寶的整合流程

1. Chloe 把 Jimmy 的 JSON 貼到 `backend/seed_data/mock_data.json`
2. 跑 `python -m scripts.validate_mock_data` 看通不通
3. 不通 → 把錯誤清單貼回去給 Jimmy 修
4. 通 → 跑 `ENVIRONMENT=dev python -m scripts.seed_dev_data`
5. 進 DB 看資料是否符合預期
6. 跑 `ENVIRONMENT=dev python -m scripts.reset_dev_data` 確認可清乾淨

---

## 版本標記

每次 Jimmy 更新 mock data，都要更新 `metadata.version`，並在 `metadata.changelog` 列差異。
