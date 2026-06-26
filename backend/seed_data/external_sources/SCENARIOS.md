# 10 Core Testing Scenarios

1.  **普通感冒開藥 (Standard Workflow):** `visit_004` (感冒) -> 開立 Paracetamol -> `invoice_004` (狀態 issued，現金付款)。
2.  **FEFO 扣庫存 (FEFO Deduction):** `visit_002` 處方 Amoxicillin 25 顆。對應 `stock_movements` 顯示 `batch_amox_01` 扣 20 顆，`batch_amox_02` 扣 5 顆。
3.  **收據作廢回補 (Invoice Voiding):** `invoice_003` 狀態為 `voided`，對應的 `stock_movements` 有一筆 `movement_type: "void_reverse"` 將藥物加回庫存。
4.  **庫存不足 (Insufficient Stock):** `visit_005` 處方 Paracetamol 20 顆，但庫存僅 10 顆，狀態標示 `stock_status: "insufficient"`。
5.  **青黴素過敏提醒 (Allergy Warning):** `patient_001` (過敏史: Penicillin)，在 `visit_001` 的草稿中包含 `drug_amox_500`，用以測試前端阻擋邏輯。
6.  **病假紙生成 (Sick Leave Certificate):** `document_001` 關聯 `patient_013`，狀態為 `confirmed`。
7.  **轉診信生成 (Referral Letter):** `document_002` 關聯 `patient_012`，由 AI 草稿生成並確認。
8.  **Invoice Draft -> Issued (收費流程):** `invoice_001` (草稿) 與 `invoice_002` (已結帳，有 50 元 discount_amount)。
9.  **AI Draft Accepted (AI 協作):** `ai_draft_001` (SOAP note) 狀態為 `accepted`，並同步更新至 `visit_004` 的 `doctor_notes`。
10. **Agent Task Waiting (A2A 準備):** `task_001` (庫存檢查) 狀態為 `waiting_for_human`，等待 user 審核低水位警報。
