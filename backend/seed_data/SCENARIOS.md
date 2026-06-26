# Mock Data Scenarios

> 每個情境是 mock data 必須涵蓋的「真實診所場景」。
> Jimmy 設計 mock data 時要保證每個情境至少有一個對應的 entity 組合。

---

## S-1：標準看診（普通流程）

**目標**：覆蓋最常見的「掛號→看診→開藥→收費」單一 batch 場景。

**需要**：
- 1 位 patient
- 1 個 visit（status=invoiced）
- 1~2 個 prescription_items（每個藥都從同一 batch 扣足量）
- 1 個 invoice（status=issued）
- 對應的 stock_movements

**示範資料對應**：visit-001（陳大文，喉嚨痛）

---

## S-2：FEFO 跨 batch 扣藥

**目標**：證明 FEFO 演算法能正確處理「一張處方的某藥，從多個 batch 扣」的情境。

**需要**：
- 1 個 drug（例如 Amoxicillin）
- 至少 2 個 batches，第一個（更早過期）剩餘量不足以單獨開出整張處方
- 1 個 prescription_item，total_quantity > 第一個 batch 的剩餘量
- 對應的 2 個 stock_movements：
  - 第一筆 movement 把第一個 batch 扣到 0
  - 第二筆從第二個 batch 扣剩餘需求

**示範資料對應**：visit-002（林小華，Amox 35 顆 = batch-A 的 20 + batch-B 的 15）

⚠️ 兩個 movement 的 `quantity_change` 加總必須等於 `prescription_item.total_quantity`（負值）。

---

## S-3：Voided invoice + 庫存回補

**目標**：證明作廢流程能正確：(a) 把 invoice 標 voided 並寫 void_reason；(b) 對應的 stock 用 `void_reverse` movement 回補。

**需要**：
- 1 個 visit
- 1~N 個 prescription_items
- 1 個 invoice（status=voided）+ `void_reason` + `voided_at`
- 對應每個原 dispense 的 `void_reverse` movement（同 batch、quantity_change 為正、絕對值相等）

**示範資料對應**：visit-003（王伯伯，Ibuprofen 9 顆 dispensed 後整單作廢）

⚠️ Validation 規則：
- voided invoice 必須有 void_reason
- 對應的 prescription_items 的 dispense quantity，必須有等量的 `void_reverse` 把它沖回

---

## S-4：多個 prescription_items 在同一處方

**目標**：證明一張處方可以開多個藥，金額加總正確。

**需要**：
- 1 visit
- 同一 visit_ref 的 ≥ 2 prescription_items
- 對應 invoice.medication_fee = items.total_price 加總

**示範資料對應**：visit-001 開了 Amox + Paracetamol 兩個

---

## S-5（未來）：partial dispense / 退藥

不在第一階段示範範圍。Sprint 4 業務 logic 完成後再加。

---

## S-6（未來）：藥品 expire（過期報銷）

不在第一階段。但 stock_movements 的 `movement_type='expire'` 已預留欄位。

---

## S-7（未來）：藥品 adjust（盤點調整）

不在第一階段。`movement_type='adjust'` 已預留。

---

## 第一階段必須涵蓋

- [x] S-1：標準看診
- [x] S-2：FEFO 跨 batch
- [x] S-3：Voided + void_reverse
- [x] S-4：多藥處方

S-5 / S-6 / S-7 留給 Sprint 4 業務 logic 開發時再補。
