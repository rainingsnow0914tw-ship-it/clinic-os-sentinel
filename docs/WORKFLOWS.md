# WORKFLOWS — Clinic OS V1

> 本文件定義系統的核心 workflow。
> 每個 workflow 都明確標出：誰觸發 → 系統做什麼 → 寫哪些表 → 必要 invariants

---

## W-1：完整看診流程

```
前台搜尋病人
  ↓
（沒有）→ 建立病人
（有）→ 開啟病人檔案
  ↓
建立 visit (status=draft)
  ↓
醫生填病歷、開藥
  ↓
系統即時計算藥量、藥費、庫存
  ↓
醫生按「完成就診」→ POST /visits/{id}/complete
  ├─ visit.status = ready_for_billing
  ├─ prescription.status = confirmed
  ├─ invoice draft 建立
  └─ ✗ 不扣庫存
  ↓
前台按「確認收費」→ POST /invoices/{id}/issue
  ├─ invoice.status = issued + invoice_number 產生
  ├─ FEFO 扣庫存 + stock_movements
  ├─ prescription.status = dispensed
  ├─ visit.status = completed
  └─ Receipt PDF 生成 + GCS 上傳
```

**關鍵原則**：扣庫存的時機是「**確認收費**」，不是「完成就診」。
**為什麼**：醫生開完藥，病人可能反悔不拿藥，這時候還沒扣庫存比較好回頭。

---

## W-2：開藥即時計算

當醫生 `POST /prescriptions/{id}/items`，伺服器：

1. 讀 `drugs.{pricing_mode, selling_price}`
2. 根據 `calculation_mode` 算 `total_quantity`：
   - `calculated_by_days`：`ceil(dose_quantity × frequency_per_day × duration_days)`
   - `fixed_quantity`：用 drug 預設
   - `manual_quantity`：用 `manual_quantity`
3. 算 `total_price`：
   - `per_unit`：`total_quantity × selling_price`
   - `per_package`：`ceil(total_quantity / units_per_purchase_unit) × selling_price`
   - `flat_fee`：`selling_price`
   - `included_in_consultation`：0
   - `manual`：用前端傳的
4. 查可用庫存：
   ```sql
   SELECT COALESCE(SUM(quantity_current), 0) AS available
   FROM drug_batches
   WHERE drug_id = ? AND clinic_id = ? AND quantity_current > 0
     AND expiry_date > CURRENT_DATE;
   ```
5. 比較 `total_quantity` vs `available`：
   - `available >= total_quantity`：`stock_status = ok`
   - `0 < available < total_quantity`：`stock_status = insufficient`
   - `available == 0`：`stock_status = out_of_stock`
6. 找最快過期的批號（提示，不鎖定）：
   ```sql
   SELECT batch_number, expiry_date, quantity_current
   FROM drug_batches
   WHERE drug_id = ? AND quantity_current > 0
   ORDER BY expiry_date ASC LIMIT 1;
   ```

**重要**：這一步**不**動庫存。只是查詢與計算。

---

## W-3：完成就診（complete visit）

`POST /clinics/{cid}/visits/{vid}/complete`

服務 atomic transaction：

```python
with db.transaction():
    visit = get_visit(vid)
    require_status(visit, "draft")
    require_doctor_or_owner()

    # 1. 確認 prescription
    rx = get_or_create_prescription(visit_id=vid)
    rx.status = "confirmed"

    # 2. 重新計算所有 prescription_items 的 total_quantity / total_price
    for item in rx.items:
        recalculate(item)

    # 3. 建立或重建 invoice draft
    invoice = upsert_invoice_draft(visit)
    invoice.medication_fee = sum(i.total_price for i in rx.items)
    invoice.consultation_fee = lookup_default_consultation_fee(clinic)
    invoice.total_amount = compute_total(invoice)

    # 4. 重建 invoice_items（先刪原有的，再從 prescription_items 建）
    delete_invoice_items_by_invoice(invoice.id)
    for px_item in rx.items:
        create_invoice_item(invoice, px_item, item_type="medication")
    create_invoice_item(invoice, item_type="consultation", ...)

    # 5. visit 狀態
    visit.status = "ready_for_billing"

    # 6. audit
    write_audit("visit.complete", entity=visit)
```

**Invariants**：
- 操作完成後 `prescription.status='confirmed'` 且 `visit.status='ready_for_billing'`
- 庫存**不**改變
- `invoice.status` 仍為 `draft`

---

## W-4：確認收費 + 發藥（issue invoice）

`POST /clinics/{cid}/invoices/{iid}/issue`

服務 atomic transaction：

```python
with db.transaction():
    invoice = get_invoice(iid)
    require_status(invoice, "draft")
    require_can_issue_invoice()

    # 1. 收據編號
    invoice.invoice_number = next_invoice_number(clinic_id)

    # 2. 發藥扣庫存
    rx = get_prescription_by_visit(invoice.visit_id)
    if rx and rx.status == "confirmed":
        for item in rx.items:
            dispense_item_fefo(item)   # 見 W-5
        rx.status = "dispensed"

    # 3. invoice
    invoice.status = "issued"
    invoice.issued_at = now()
    invoice.issued_by_user_id = current_user.id
    invoice.payment_method = body.payment_method
    invoice.discount_amount = body.discount_amount or 0

    # 4. visit 收尾
    visit = get_visit(invoice.visit_id)
    visit.status = "completed"

    # 5. 生成 PDF（同步 or 排隊？V1 同步）
    pdf_url = render_receipt_pdf(invoice)
    invoice.pdf_url = pdf_url

    # 6. audit
    write_audit("invoice.issue", entity=invoice)
```

**Invariants**：
- 失敗時整個 transaction rollback（庫存不改、編號不消耗）
- 庫存不足會 raise `InsufficientStock`，回 HTTP 409

---

## W-5：FEFO 扣庫存（dispense_item_fefo）

```python
def dispense_item_fefo(prescription_item):
    remaining = prescription_item.total_quantity
    while remaining > 0:
        # 鎖定最快過期批號
        batch = db.query(DrugBatch).filter(
            DrugBatch.drug_id == prescription_item.drug_id,
            DrugBatch.clinic_id == current_clinic_id,
            DrugBatch.quantity_current > 0,
            DrugBatch.expiry_date > today(),
        ).order_by(DrugBatch.expiry_date.asc()).with_for_update().first()

        if not batch:
            raise InsufficientStock(prescription_item)

        take = min(remaining, batch.quantity_current)
        batch.quantity_current -= take
        remaining -= take

        write_stock_movement(
            drug_id=prescription_item.drug_id,
            drug_batch_id=batch.id,
            movement_type="dispense",
            quantity_change=-take,
            related_prescription_item_id=prescription_item.id,
            related_invoice_id=current_invoice_id,
        )
```

**Invariants**：
- 永遠先扣最快過期的批號
- `with_for_update()` 防止 race condition
- 任一筆 batch 不足會拆多筆 movement

---

## W-6：作廢收據

`POST /clinics/{cid}/invoices/{iid}/void`

```python
with db.transaction():
    invoice = get_invoice(iid)
    require_status(invoice, "issued")
    require_can_void_invoice()

    invoice.status = "voided"
    invoice.voided_at = now()
    invoice.voided_by_user_id = current_user.id
    invoice.void_reason = body.reason

    # 回補庫存（針對該 invoice 的 dispense movements）
    rx = get_prescription_by_visit(invoice.visit_id)
    if rx and rx.status == "dispensed":
        movements = list_dispense_movements_for_invoice(invoice.id)
        for m in movements:
            batch = get_batch(m.drug_batch_id)
            batch.quantity_current += abs(m.quantity_change)
            write_stock_movement(
                drug_id=m.drug_id,
                drug_batch_id=batch.id,
                movement_type="void_reverse",
                quantity_change=abs(m.quantity_change),
                related_invoice_id=invoice.id,
            )
        rx.status = "voided"

    write_audit("invoice.void", entity=invoice, reason=body.reason)
```

---

## W-7：病假紙生成

```
醫生在 visit 中按「開病假紙」
  ↓
POST /visits/{id}/documents/sick-leave
  body: { start_date, end_date, reason, use_ai_draft: true }
  ↓
（use_ai_draft）伺服器先呼叫 AI → 寫 ai_drafts (status=generated)
  ↓
建 medical_documents (status=draft, content_json 預填)
  ↓
回傳 document_id
  ↓
前端展示草稿，醫生可編輯（PATCH /documents/{id}）
  ↓
醫生確認 → POST /documents/{id}/confirm
  ├─ medical_documents.status = confirmed
  ├─ 用 document_templates.template_content 渲染
  ├─ wkhtmltopdf 或 weasyprint 生成 PDF
  ├─ 上傳 GCS → 寫 pdf_url
  └─ audit log
```

**Invariants**：
- AI 寫到 `ai_drafts`，不寫 `medical_documents`
- 醫生確認時若編輯過，更新 `medical_documents.content_json` 然後渲染

---

## W-8：轉診信生成

同 W-7，差別：
- `document_type = referral_letter`
- AI prompt 不同（拉本次 visit + 過往 N 次 visit 摘要）
- 模板結構不同（含轉診原因、要求科別、目標醫院/醫生）

---

## W-9：AI 草稿 review flow

```
AI 生成 → ai_drafts (status=generated)
  ↓
前端列出 → GET /ai-drafts?visit_id=
  ↓
醫生看內容
  ├─ 編輯 → PATCH /ai-drafts/{id}（status=edited）
  ├─ 接受 → POST /ai-drafts/{id}/accept
  │         ├─ status=accepted
  │         └─ 內容寫入對應正式表（依 draft_type）
  └─ 拒絕 → POST /ai-drafts/{id}/reject (status=rejected)
```

**寫入正式表的對應**：

| draft_type | 寫到 |
|---|---|
| `soap_note` | `visits.{chief_complaint, history_present_illness, examination_findings, diagnosis, treatment_plan}` |
| `referral_letter` | `medical_documents.content_json` |
| `sick_leave` | `medical_documents.content_json` |
| `inventory_warning` | 不寫正式表，只是提醒 |
| `visit_summary` | 不寫正式表，只是顯示 |
| `billing_review` | 不寫正式表，只是提醒 |

---

## W-10：庫存進貨

```
POST /drug-batches
  body: { drug_id, batch_number, expiry_date, quantity_initial, ... }
  ↓
建 drug_batches (quantity_current = quantity_initial)
  ↓
寫 stock_movements (type=purchase, quantity_change=+quantity_initial)
  ↓
audit log
```

---

## W-11：手動庫存調整

```
POST /stock-adjustments
  body: { drug_batch_id, quantity_change: -5, reason: "破損" }
  ↓
require owner
  ↓
batch.quantity_current += quantity_change
  ↓
寫 stock_movements (type=adjustment, reason=...)
  ↓
audit log
```

---

## W-12：AI Inventory Alert

```
（每天 06:00 cron / 手動觸發）
  ↓
POST /agent-tasks (agent_type=inventory, task_type=daily_alert)
  ↓
agent 內部跑：
  - SELECT drugs WHERE current_stock < low_stock_threshold
  - SELECT drug_batches WHERE expiry_date <= today + 90 days AND quantity_current > 0
  - 拉 30 天用量，預測缺料
  ↓
寫 ai_drafts (draft_type=inventory_warning, content=...)
  ↓
建 agent_tasks (status=waiting_for_human)
  ↓
Owner 在 dashboard 看到 → 確認/忽略
```

---

## 全域 Invariants

> 任何 workflow 不可違反這些原則：

1. 所有寫操作必須是 atomic transaction
2. 所有 mutation 必須在 commit 前寫 audit log
3. 任何 `drug_batches.quantity_current` 變動必有對應 `stock_movements`
4. AI 永遠不直接寫除了 `ai_drafts` 外的表
5. `clinic_id` 必須匹配當前 user 的 active clinic（middleware 強制）
6. 軟刪除：`deleted_at`，不要 DELETE
7. PDF 永遠 server-side 生成，前端不負責產生
