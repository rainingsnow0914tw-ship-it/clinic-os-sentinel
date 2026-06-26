# API_SPEC — Clinic OS V1

> Base URL: `https://clinic-os-api-{hash}.run.app/v1`
> Auth: `Authorization: Bearer <Firebase ID Token>`
> Active clinic: `X-Clinic-Id: <uuid>` (header)

---

## 通用規則

### Request
- `Content-Type: application/json`
- 所有 mutation 都吃 JSON body
- 所有 query 都用 query string

### Response
- 成功：HTTP 2xx + JSON body
- 失敗：HTTP 4xx/5xx + `{ "error": { "code": "...", "message": "...", "details": {...} } }`

### 錯誤碼
| Code | HTTP | 意義 |
|---|---|---|
| `auth_required` | 401 | 沒有 token 或 token 無效 |
| `forbidden` | 403 | 權限不足 |
| `clinic_mismatch` | 403 | 試圖存取不屬於自己的 clinic 資源 |
| `not_found` | 404 | 資源不存在 |
| `validation_error` | 422 | 欄位驗證失敗 |
| `conflict` | 409 | 狀態衝突（例：作廢已作廢的收據） |
| `insufficient_stock` | 409 | 庫存不足 |
| `internal_error` | 500 | 後端錯 |

### Pagination
- `?page=1&page_size=20`（預設 page_size=20，max=100）
- Response 含 `meta: { page, page_size, total }`

---

## 1. Auth & User

### `POST /auth/session`
驗證 Firebase ID token，回傳 user 資料 + clinic 列表。

Request: 用 `Authorization: Bearer` header（不需要 body）

Response:
```json
{
  "user": {
    "id": "uuid",
    "name": "Dr. Chan",
    "email": "chan@example.com"
  },
  "clinics": [
    { "id": "uuid", "name": "Chloe Family Clinic", "role": "doctor",
      "permissions": { "can_view_revenue_report": false } }
  ]
}
```

### `GET /me`
回傳當前 user 資訊。

### `GET /me/clinics`
回傳當前 user 屬於的 clinic 列表。

### `POST /clinics/{clinic_id}/users`
邀請新成員加入診所（owner only）。

Request:
```json
{
  "email": "new@example.com",
  "name": "Nurse Lee",
  "role": "nurse",
  "custom_permissions": { "can_manage_inventory": true }
}
```

### `PATCH /clinics/{clinic_id}/users/{user_id}/role`
改成員角色（owner only）。

### `PATCH /clinics/{clinic_id}/users/{user_id}/permissions`
改成員 custom permissions（owner only）。

---

## 2. Clinics

### `GET /clinics/{clinic_id}`
取得診所資訊。

### `PATCH /clinics/{clinic_id}`
修改診所資料（owner only）。

---

## 3. Patients

### `GET /clinics/{clinic_id}/patients?q=陳&page=1`
搜尋病人（依姓名、電話、id_number 模糊）。

### `POST /clinics/{clinic_id}/patients`
建立病人。任何角色都可。

### `GET /clinics/{clinic_id}/patients/{patient_id}`
取得單一病人（含過敏史、慢性病）。

### `PATCH /clinics/{clinic_id}/patients/{patient_id}`
修改病人。

> ⚠️ 不提供 `DELETE`。停用病人改 `status` 欄位（V2）。

---

## 4. Visits

### `POST /clinics/{clinic_id}/visits`
建立就診紀錄。

Request:
```json
{
  "patient_id": "uuid",
  "doctor_user_id": "uuid",
  "chief_complaint": "..."
}
```

回傳新 visit（status=`draft`）。

### `GET /clinics/{clinic_id}/patients/{patient_id}/visits?page=1`
病人就診歷史。

### `GET /clinics/{clinic_id}/visits/{visit_id}`
取得 visit 完整資料（含 prescription、invoice、documents）。

### `PATCH /clinics/{clinic_id}/visits/{visit_id}`
修改 visit 內容（doctor only，且 status 必須為 `draft`）。

### `POST /clinics/{clinic_id}/visits/{visit_id}/complete`
**完成就診**：

伺服器動作：
1. `prescription.status = confirmed`
2. `visit.status = ready_for_billing`
3. 建立或更新 invoice draft（含 invoice_items）
4. 計算 `medication_fee` + `total_amount`
5. 寫 `audit_logs`

注意：**不扣庫存**。

### `POST /clinics/{clinic_id}/visits/{visit_id}/void`
作廢 visit（owner only，需 reason）。

---

## 5. Drugs / Inventory

### `GET /clinics/{clinic_id}/drugs?q=Panadol&active=true`
查藥品主檔。

### `POST /clinics/{clinic_id}/drugs`
建立藥品（owner / can_manage_inventory）。

Request:
```json
{
  "brand_name": "Panadol",
  "generic_name": "Paracetamol",
  "strength": "500mg",
  "dosage_form": "tablet",
  "stock_unit": "tab",
  "purchase_unit": "box",
  "units_per_purchase_unit": 100,
  "selling_price": 5,
  "pricing_mode": "per_unit",
  "low_stock_threshold": 100
}
```

### `PATCH /clinics/{clinic_id}/drugs/{drug_id}`
修改藥品。改價格會寫 audit log。

---

### `GET /clinics/{clinic_id}/drug-batches?drug_id=&expiring_within_days=90`
查批號庫存。

### `POST /clinics/{clinic_id}/drug-batches`
新增進貨批號。

Request:
```json
{
  "drug_id": "uuid",
  "batch_number": "B20251201",
  "expiry_date": "2027-12-01",
  "received_date": "2026-05-01",
  "purchase_price": 200,
  "quantity_initial": 100,
  "supplier_name": "ABC Supply"
}
```

伺服器動作：
1. 建立 `drug_batches`（quantity_current = quantity_initial）
2. 寫 `stock_movements`（type=`purchase`）
3. 寫 audit log

### `PATCH /clinics/{clinic_id}/drug-batches/{batch_id}`
修改批號（限定欄位：批號、storage_location，不可改 quantity）。

### `GET /clinics/{clinic_id}/stock-movements?drug_id=&from=&to=`
庫存異動 ledger。

### `POST /clinics/{clinic_id}/stock-adjustments`
手動調整庫存（owner only）。

Request:
```json
{
  "drug_batch_id": "uuid",
  "quantity_change": -5,
  "reason": "破損"
}
```

---

## 6. Prescriptions

### `POST /clinics/{clinic_id}/visits/{visit_id}/prescriptions`
建立 prescription（doctor only）。

### `POST /clinics/{clinic_id}/prescriptions/{prescription_id}/items`
加開一個藥。

Request:
```json
{
  "drug_id": "uuid",
  "dose_quantity": 1,
  "dose_unit": "tab",
  "frequency_per_day": 2,
  "duration_days": 3,
  "calculation_mode": "calculated_by_days",
  "instruction_text": "每日2次，每次1顆，飯後服用"
}
```

伺服器即時計算並回傳：
```json
{
  "id": "uuid",
  "total_quantity": 6,
  "total_price": 30.00,
  "stock_status": "ok",
  "available_quantity": 120,
  "earliest_expiry_batch": { "batch_number": "B...", "expiry_date": "2027-01-01" }
}
```

### `PATCH /clinics/{clinic_id}/prescription-items/{item_id}`
修改藥量、頻次、天數。重新計算 total。

### `DELETE /clinics/{clinic_id}/prescription-items/{item_id}`
移除藥（限 status=draft）。

### `POST /clinics/{clinic_id}/prescriptions/{prescription_id}/confirm`
確認處方（呼叫 `complete visit` 時自動觸發）。

### `POST /clinics/{clinic_id}/prescriptions/{prescription_id}/dispense`
**正式發藥扣庫存**（前台 / nurse，視 clinic 設定）。

伺服器動作：
1. `prescription.status = dispensed`
2. 對每個 `prescription_item`：FEFO 找批號 → 扣庫存 → 寫 `stock_movements`
3. atomic transaction，任一步失敗整批 rollback
4. 寫 audit log

注意：**這個動作通常被 invoice issue 觸發，不應該前台直接呼叫**。

### `POST /clinics/{clinic_id}/prescriptions/{prescription_id}/void`
作廢處方。已 dispensed 的會回補庫存（`movement_type=void_reverse`）。

---

## 7. Invoices

### `POST /clinics/{clinic_id}/visits/{visit_id}/invoice-draft`
重新生成 invoice draft（自動由 `complete visit` 觸發；手動 endpoint 給後續加項目用）。

### `PATCH /clinics/{clinic_id}/invoices/{invoice_id}`
修改 invoice draft（加項目、改折扣、改付款方式）。限 status=draft。

### `POST /clinics/{clinic_id}/invoices/{invoice_id}/issue`
**確認收費並發藥**：

Request:
```json
{
  "payment_method": "cash",
  "discount_amount": 0
}
```

伺服器動作（atomic）：
1. 產生 `invoice_number`（per-clinic 流水號）
2. `invoice.status = issued`、`issued_at=now()`、`issued_by_user_id=...`
3. 對應 `prescription` 觸發 dispense 流程（FEFO 扣庫存）
4. `visit.status = completed`
5. 生成 receipt PDF → 上傳 GCS → 寫 `pdf_url`
6. 寫 audit log

### `POST /clinics/{clinic_id}/invoices/{invoice_id}/void`
作廢收據。

Request:
```json
{ "reason": "病人退錢，藥未取" }
```

伺服器動作：
1. `invoice.status = voided`、`voided_at=now()`、`void_reason=...`
2. 若 prescription 已 dispensed → 觸發 `void_reverse` 回補庫存
3. 寫 audit log

### `GET /clinics/{clinic_id}/invoices/{invoice_id}/pdf`
回 redirect 302 到 GCS signed URL。

---

## 8. Medical Documents

### `POST /clinics/{clinic_id}/visits/{visit_id}/documents/sick-leave`
建立病假紙草稿。

Request:
```json
{
  "start_date": "2026-05-02",
  "end_date": "2026-05-05",
  "reason": "感冒",
  "use_ai_draft": true
}
```

`use_ai_draft=true` 時，先建一筆 `ai_drafts`，再以 AI 內容預填 `medical_documents.content_json`，狀態為 `draft`。

### `POST /clinics/{clinic_id}/visits/{visit_id}/documents/referral`
建立轉診信草稿。

### `PATCH /clinics/{clinic_id}/documents/{document_id}`
修改 content_json（限 draft）。

### `POST /clinics/{clinic_id}/documents/{document_id}/confirm`
確認文件並生成 PDF。

伺服器動作：
1. `status = confirmed`
2. 用 `document_templates.template_content` + `content_json` 渲染 → PDF → GCS
3. 寫 `pdf_url`
4. 寫 audit log

### `GET /clinics/{clinic_id}/documents/{document_id}/pdf`
取 PDF。

---

## 9. AI

### `POST /clinics/{clinic_id}/ai/visit-summary`
取病人就診摘要。

Request:
```json
{ "patient_id": "uuid", "lookback_visits": 5 }
```

回傳 `ai_drafts.id`。

### `POST /clinics/{clinic_id}/ai/soap-draft`
從口述/亂寫的病歷生成 SOAP 格式草稿。

Request:
```json
{
  "visit_id": "uuid",
  "raw_input": "病人發燒3天，咳嗽，喉嚨痛...",
  "input_source": "voice"
}
```

### `POST /clinics/{clinic_id}/ai/referral-draft`
轉診信草稿。

### `POST /clinics/{clinic_id}/ai/sick-leave-draft`
病假紙草稿。

### `POST /clinics/{clinic_id}/ai/inventory-alerts`
庫存提醒（觸發 inventory agent task）。

### `GET /clinics/{clinic_id}/ai-drafts?visit_id=&status=`
列出草稿。

### `POST /clinics/{clinic_id}/ai-drafts/{draft_id}/accept`
人類接受草稿，將內容寫入正式表（target 由 draft_type 決定）。

### `POST /clinics/{clinic_id}/ai-drafts/{draft_id}/reject`
拒絕草稿。

---

## 10. Agent Tasks（A2A-ready）

### `POST /clinics/{clinic_id}/agent-tasks`
建立任務。

Request:
```json
{
  "agent_type": "inventory",
  "task_type": "generate_purchase_suggestion",
  "related_entity_type": "drug",
  "related_entity_id": "drug_123",
  "input": {
    "lookback_days": 30,
    "include_expiring_batches": true
  }
}
```

### `GET /clinics/{clinic_id}/agent-tasks?status=&agent_type=`
列出任務。

### `GET /clinics/{clinic_id}/agent-tasks/{task_id}`
取任務（含 events）。

### `POST /clinics/{clinic_id}/agent-tasks/{task_id}/approve`
核准 agent 任務（人類）。

### `POST /clinics/{clinic_id}/agent-tasks/{task_id}/reject`
拒絕。

---

## 11. Settings / Templates

### `GET/POST/PATCH /clinics/{clinic_id}/document-templates`
管理文件模板（owner / can_manage_templates）。

### `GET/POST/PATCH /clinics/{clinic_id}/ai-prompt-templates`
管理 AI prompt（owner only）。

### `GET/POST/PATCH /clinics/{clinic_id}/fee-catalog`
管理費用項目（owner / can_manage_fees）。

---

## 12. Reports（基本）

### `GET /clinics/{clinic_id}/reports/daily-revenue?date=2026-05-02`
當日收入摘要。

### `GET /clinics/{clinic_id}/reports/low-stock`
低庫存清單。

### `GET /clinics/{clinic_id}/reports/expiring-soon?within_days=90`
快過期清單。

### `GET /clinics/{clinic_id}/reports/audit-logs?from=&to=&action=`
Audit log 查詢。
