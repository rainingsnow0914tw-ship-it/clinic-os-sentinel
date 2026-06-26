# Mock Data Architecture Plan

## 1. 資料設計邏輯 (Design Logic)
本套 Seed Data 專為小型診所的 Dev/Sandbox 環境設計，所有實體均透過 `_ref` 後綴的字串 ID 進行強關聯（例如 `patient_ref: "patient_001"`）。設計重點在於**關聯完整性**與**計算正確性**，確保從掛號、開藥、扣庫存到收費的 Workflow 能夠一氣呵成。

## 2. 病人分布 (Patient Distribution) - 共 60 人
*   **兒科 (Peds):** 9 人 (包含電話綁定家長的測試案例)
*   **青年 (Young Adults):** 11 人
*   **中年 (Middle-aged):** 20 人
*   **長者 (Seniors):** 15 人 (包含多重慢性病測試)
*   **超高齡 (Super Seniors):** 5 人

## 3. 藥物分布 (Drug Distribution) - 共 30 種
*   涵蓋止痛退燒、抗組織胺、抗生素、外用藥、慢性病等 8 大類。
*   **計價模式:** 包含 `per_unit` (按顆/瓶計費) 與 `manual` (手動計費)。
*   **庫存設定:** 包含管狀 (tube)、瓶裝 (bottle) 及散裝錠劑 (tab)。

## 4. 關鍵測試情境 (Key Scenarios)
1.  **FEFO 庫存扣減:** `drug_amox_500` 擁有兩個批號，測試開立 25 顆時，跨批號扣減的數學邏輯。
2.  **Allergy Warning (過敏警告):** `patient_001` (青黴素過敏) 在 `visit_001` 被開立 Amoxicillin。
3.  **庫存不足 (Insufficient Stock):** `drug_para_500` 庫存僅剩 10 顆，但處方開立 20 顆。
4.  **作廢回補 (Void & Reverse):** `invoice_003` 被標記為 `voided`，並觸發庫存的 `void_reverse`。
5.  **A2A Agent 任務:** 模擬背景 Agent 掃描過期藥物並生成盤點草稿。
