# DATABASE_SCHEMA — Clinic OS V1

> PostgreSQL 15+
> Source of truth：這份文件 > Alembic migration > SQLAlchemy model
> 任何欄位變動必須先改這份文件，再寫 migration

---

## 慣例

- 所有 PK 用 `UUID v4`（`gen_random_uuid()`），不用 auto-increment（多區域、merge 友善）
- 所有 timestamp 用 `TIMESTAMPTZ`（含時區）
- 所有 soft delete 欄位叫 `deleted_at`（NULL = 未刪除）
- 所有 enum 用 PostgreSQL native enum type（不用 VARCHAR + check）
- 所有金額用 `NUMERIC(12, 2)`，不用 FLOAT
- 所有需要彈性結構的用 `JSONB`，不用 TEXT
- 所有 multi-tenant 表必有 `clinic_id` + 該 column 上有 index

---

## ENUM Types

```sql
CREATE TYPE membership_role AS ENUM ('owner', 'doctor', 'nurse', 'reception');
CREATE TYPE visit_status AS ENUM ('draft', 'ready_for_billing', 'completed', 'voided');
CREATE TYPE prescription_status AS ENUM ('draft', 'confirmed', 'dispensed', 'voided');
CREATE TYPE invoice_status AS ENUM ('draft', 'issued', 'voided');
CREATE TYPE document_status AS ENUM ('draft', 'confirmed', 'voided');
CREATE TYPE document_type AS ENUM ('sick_leave', 'referral_letter', 'medical_certificate');
CREATE TYPE pricing_mode AS ENUM ('per_unit', 'per_package', 'flat_fee', 'manual', 'included_in_consultation');
CREATE TYPE calculation_mode AS ENUM ('calculated_by_days', 'fixed_quantity', 'manual_quantity');
CREATE TYPE movement_type AS ENUM ('purchase', 'dispense', 'adjustment', 'return', 'void_reverse', 'expired');
CREATE TYPE invoice_item_type AS ENUM ('consultation', 'medication', 'lab', 'procedure', 'certificate', 'other');
CREATE TYPE fee_category AS ENUM ('consultation', 'medication', 'lab', 'procedure', 'certificate', 'other');
CREATE TYPE ai_draft_type AS ENUM ('soap_note', 'referral_letter', 'sick_leave', 'inventory_warning', 'visit_summary', 'billing_review');
CREATE TYPE ai_draft_status AS ENUM ('generated', 'accepted', 'edited', 'rejected');
CREATE TYPE agent_task_status AS ENUM ('queued', 'running', 'waiting_for_human', 'completed', 'failed', 'cancelled');
CREATE TYPE agent_protocol AS ENUM ('internal', 'api', 'mcp', 'a2a', 'webhook');
CREATE TYPE integration_type AS ENUM ('lab', 'accounting', 'pharmacy_supplier', 'payment', 'sms', 'email', 'ai_agent', 'a2a_agent');
CREATE TYPE lab_order_status AS ENUM ('draft', 'ordered', 'result_received', 'reviewed', 'cancelled');
```

---

## 1. 核心多租戶表

### `clinics`
```sql
CREATE TABLE clinics (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  address         TEXT,
  phone           VARCHAR(50),
  email           VARCHAR(255),
  receipt_header  TEXT,                          -- 收據抬頭模板
  logo_url        TEXT,
  timezone        VARCHAR(64) DEFAULT 'Asia/Macau',
  currency        VARCHAR(8)  DEFAULT 'MOP',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);
```

### `users`
```sql
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firebase_uid  VARCHAR(128) UNIQUE NOT NULL,    -- 來自 Firebase Auth
  name          VARCHAR(255) NOT NULL,
  email         VARCHAR(255) UNIQUE NOT NULL,
  phone         VARCHAR(50),
  status        VARCHAR(32) DEFAULT 'active',    -- active / suspended
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_firebase_uid ON users(firebase_uid);
```

### `clinic_memberships`
```sql
CREATE TABLE clinic_memberships (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                UUID NOT NULL REFERENCES clinics(id),
  user_id                  UUID NOT NULL REFERENCES users(id),
  role                     membership_role NOT NULL,
  custom_permissions_json  JSONB DEFAULT '{}'::jsonb,
  is_active                BOOLEAN NOT NULL DEFAULT true,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(clinic_id, user_id)
);
CREATE INDEX idx_memberships_user ON clinic_memberships(user_id);
CREATE INDEX idx_memberships_clinic ON clinic_memberships(clinic_id);
```

`custom_permissions_json` 範例：
```json
{
  "can_manage_inventory": true,
  "can_view_revenue_report": true,
  "can_manage_users": false,
  "can_void_invoice": true
}
```

---

## 2. 病人與就診

### `patients`
```sql
CREATE TABLE patients (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                UUID NOT NULL REFERENCES clinics(id),
  full_name                VARCHAR(255) NOT NULL,
  gender                   VARCHAR(16),
  date_of_birth            DATE,
  phone                    VARCHAR(50),
  id_number                VARCHAR(64),          -- 身分證/護照（敏感）
  address                  TEXT,
  emergency_contact_name   VARCHAR(255),
  emergency_contact_phone  VARCHAR(50),
  allergies                TEXT,
  chronic_conditions       TEXT,
  notes                    TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at               TIMESTAMPTZ
);
CREATE INDEX idx_patients_clinic ON patients(clinic_id);
CREATE INDEX idx_patients_name_trgm ON patients USING gin (full_name gin_trgm_ops);
CREATE INDEX idx_patients_phone ON patients(clinic_id, phone);
```

### `visits`
```sql
CREATE TABLE visits (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                 UUID NOT NULL REFERENCES clinics(id),
  patient_id                UUID NOT NULL REFERENCES patients(id),
  doctor_user_id            UUID REFERENCES users(id),
  visit_date                TIMESTAMPTZ NOT NULL DEFAULT now(),
  chief_complaint           TEXT,
  history_present_illness   TEXT,
  examination_findings      TEXT,
  diagnosis                 TEXT,
  treatment_plan            TEXT,
  doctor_notes              TEXT,
  status                    visit_status NOT NULL DEFAULT 'draft',
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_visits_clinic_date ON visits(clinic_id, visit_date DESC);
CREATE INDEX idx_visits_patient ON visits(patient_id, visit_date DESC);
CREATE INDEX idx_visits_doctor ON visits(doctor_user_id);
```

---

## 3. 藥物與庫存

### `drugs`（主檔）
```sql
CREATE TABLE drugs (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                UUID NOT NULL REFERENCES clinics(id),
  brand_name               VARCHAR(255) NOT NULL,
  generic_name             VARCHAR(255),
  strength                 VARCHAR(64),          -- 例：500mg
  dosage_form              VARCHAR(64),          -- tablet / syrup / cream
  stock_unit               VARCHAR(32) NOT NULL, -- 扣庫存的單位（tab）
  purchase_unit            VARCHAR(32),          -- 採購單位（box）
  units_per_purchase_unit  INTEGER DEFAULT 1,    -- 1 box = 100 tab
  default_instruction      TEXT,
  selling_price            NUMERIC(12,2) NOT NULL DEFAULT 0,
  pricing_mode             pricing_mode NOT NULL DEFAULT 'per_unit',
  warning_notes            TEXT,
  low_stock_threshold      INTEGER DEFAULT 0,
  is_active                BOOLEAN NOT NULL DEFAULT true,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_drugs_clinic ON drugs(clinic_id) WHERE is_active = true;
CREATE INDEX idx_drugs_name_trgm ON drugs USING gin (brand_name gin_trgm_ops);
```

### `drug_batches`（批號庫存）
```sql
CREATE TABLE drug_batches (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id          UUID NOT NULL REFERENCES clinics(id),
  drug_id            UUID NOT NULL REFERENCES drugs(id),
  batch_number       VARCHAR(128),
  expiry_date        DATE NOT NULL,
  received_date      DATE,
  purchase_price     NUMERIC(12,2),
  quantity_current   INTEGER NOT NULL,
  quantity_initial   INTEGER NOT NULL,
  supplier_name      VARCHAR(255),
  storage_location   VARCHAR(128),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_batches_drug_expiry ON drug_batches(drug_id, expiry_date) WHERE quantity_current > 0;
CREATE INDEX idx_batches_clinic ON drug_batches(clinic_id);
```

> 🔑 **FEFO query**：`WHERE drug_id=? AND quantity_current > 0 ORDER BY expiry_date ASC LIMIT 1`

### `stock_movements`（庫存異動 ledger）
```sql
CREATE TABLE stock_movements (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                   UUID NOT NULL REFERENCES clinics(id),
  drug_id                     UUID NOT NULL REFERENCES drugs(id),
  drug_batch_id               UUID REFERENCES drug_batches(id),
  movement_type               movement_type NOT NULL,
  quantity_change             INTEGER NOT NULL,    -- 正數=入、負數=出
  related_visit_id            UUID REFERENCES visits(id),
  related_prescription_item_id UUID,                -- 不加 FK，避免循環
  related_invoice_id          UUID,
  reason                      TEXT,
  created_by_user_id          UUID REFERENCES users(id),
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_movements_drug_time ON stock_movements(drug_id, created_at DESC);
CREATE INDEX idx_movements_clinic_time ON stock_movements(clinic_id, created_at DESC);
```

> ⚠️ **任何** `drug_batches.quantity_current` 變動必須同時寫一筆 `stock_movements`。
> Service layer 負責這個 invariant，禁止直接 UPDATE drug_batches。

### `stock_reservations`（V1 預留）
```sql
CREATE TABLE stock_reservations (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                UUID NOT NULL REFERENCES clinics(id),
  prescription_item_id     UUID,
  drug_id                  UUID NOT NULL REFERENCES drugs(id),
  drug_batch_id            UUID REFERENCES drug_batches(id),
  quantity_reserved        INTEGER NOT NULL,
  status                   VARCHAR(32) NOT NULL DEFAULT 'reserved',
  expires_at               TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 4. 處方

### `prescriptions`
```sql
CREATE TABLE prescriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id       UUID NOT NULL REFERENCES clinics(id),
  visit_id        UUID NOT NULL REFERENCES visits(id),
  patient_id      UUID NOT NULL REFERENCES patients(id),
  doctor_user_id  UUID REFERENCES users(id),
  status          prescription_status NOT NULL DEFAULT 'draft',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_prescriptions_visit ON prescriptions(visit_id);
```

### `prescription_items`
```sql
CREATE TABLE prescription_items (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id          UUID NOT NULL REFERENCES clinics(id),
  prescription_id    UUID NOT NULL REFERENCES prescriptions(id),
  drug_id            UUID NOT NULL REFERENCES drugs(id),
  dose_quantity      NUMERIC(10,2),         -- 一次幾顆
  dose_unit          VARCHAR(32),            -- tab / ml
  frequency_per_day  INTEGER,                -- 一天幾次
  duration_days      INTEGER,                -- 幾天
  calculation_mode   calculation_mode NOT NULL DEFAULT 'calculated_by_days',
  manual_quantity    INTEGER,
  total_quantity     INTEGER NOT NULL,       -- 系統計算或手動填
  instruction_text   TEXT,                   -- 顯示在處方上的中文用法
  unit_price         NUMERIC(12,2) NOT NULL DEFAULT 0,
  pricing_mode       pricing_mode NOT NULL DEFAULT 'per_unit',
  total_price        NUMERIC(12,2) NOT NULL DEFAULT 0,
  stock_status       VARCHAR(32),            -- ok / insufficient / warning
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_prescription_items_rx ON prescription_items(prescription_id);
```

> 🔑 **藥量公式**（calculation_mode='calculated_by_days'）：
> `total_quantity = ceil(dose_quantity * frequency_per_day * duration_days)`

---

## 5. 收據

### `fee_catalog`
```sql
CREATE TABLE fee_catalog (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id     UUID NOT NULL REFERENCES clinics(id),
  code          VARCHAR(64) NOT NULL,
  name          VARCHAR(255) NOT NULL,
  category      fee_category NOT NULL,
  default_price NUMERIC(12,2) NOT NULL DEFAULT 0,
  tax_type      VARCHAR(32),
  is_active     BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(clinic_id, code)
);
```

### `invoices`
```sql
CREATE TABLE invoices (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id           UUID NOT NULL REFERENCES clinics(id),
  patient_id          UUID NOT NULL REFERENCES patients(id),
  visit_id            UUID NOT NULL REFERENCES visits(id),
  invoice_number      VARCHAR(64),                 -- 發出時才填，UNIQUE per clinic
  consultation_fee    NUMERIC(12,2) DEFAULT 0,
  medication_fee      NUMERIC(12,2) DEFAULT 0,
  lab_fee             NUMERIC(12,2) DEFAULT 0,
  procedure_fee       NUMERIC(12,2) DEFAULT 0,
  certificate_fee     NUMERIC(12,2) DEFAULT 0,
  other_fee           NUMERIC(12,2) DEFAULT 0,
  discount_amount     NUMERIC(12,2) DEFAULT 0,
  total_amount        NUMERIC(12,2) NOT NULL DEFAULT 0,
  payment_method      VARCHAR(32),
  status              invoice_status NOT NULL DEFAULT 'draft',
  issued_by_user_id   UUID REFERENCES users(id),
  issued_at           TIMESTAMPTZ,
  voided_by_user_id   UUID REFERENCES users(id),
  voided_at           TIMESTAMPTZ,
  void_reason         TEXT,
  pdf_url             TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(clinic_id, invoice_number)
);
CREATE INDEX idx_invoices_visit ON invoices(visit_id);
CREATE INDEX idx_invoices_clinic_issued ON invoices(clinic_id, issued_at DESC);
```

### `invoice_items`
```sql
CREATE TABLE invoice_items (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                   UUID NOT NULL REFERENCES clinics(id),
  invoice_id                  UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  item_type                   invoice_item_type NOT NULL,
  description                 VARCHAR(255) NOT NULL,
  quantity                    NUMERIC(10,2) NOT NULL DEFAULT 1,
  unit_price                  NUMERIC(12,2) NOT NULL DEFAULT 0,
  total_price                 NUMERIC(12,2) NOT NULL DEFAULT 0,
  related_drug_id             UUID REFERENCES drugs(id),
  related_prescription_item_id UUID,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
```

---

## 6. 醫療文件

### `document_templates`
```sql
CREATE TABLE document_templates (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id         UUID NOT NULL REFERENCES clinics(id),
  document_type     document_type NOT NULL,
  template_name     VARCHAR(255) NOT NULL,
  template_content  TEXT NOT NULL,           -- Jinja2 template
  language          VARCHAR(16) DEFAULT 'zh-TW',
  version           INTEGER DEFAULT 1,
  is_active         BOOLEAN NOT NULL DEFAULT true,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `medical_documents`
```sql
CREATE TABLE medical_documents (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id             UUID NOT NULL REFERENCES clinics(id),
  patient_id            UUID NOT NULL REFERENCES patients(id),
  visit_id              UUID NOT NULL REFERENCES visits(id),
  document_type         document_type NOT NULL,
  template_id           UUID REFERENCES document_templates(id),
  status                document_status NOT NULL DEFAULT 'draft',
  content_json          JSONB NOT NULL,        -- 渲染用的變數
  pdf_url               TEXT,
  generated_by_ai       BOOLEAN DEFAULT false,
  confirmed_by_user_id  UUID REFERENCES users(id),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_visit ON medical_documents(visit_id);
```

---

## 7. AI 層

### `ai_prompt_templates`
```sql
CREATE TABLE ai_prompt_templates (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id              UUID NOT NULL REFERENCES clinics(id),
  task_type              VARCHAR(64) NOT NULL,    -- soap_note, referral, ...
  prompt_name            VARCHAR(255) NOT NULL,
  system_prompt          TEXT NOT NULL,
  user_prompt_template   TEXT NOT NULL,           -- Jinja2
  model                  VARCHAR(64) NOT NULL,
  version                INTEGER DEFAULT 1,
  is_active              BOOLEAN NOT NULL DEFAULT true,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `ai_drafts`
```sql
CREATE TABLE ai_drafts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id             UUID NOT NULL REFERENCES clinics(id),
  patient_id            UUID REFERENCES patients(id),
  visit_id              UUID REFERENCES visits(id),
  draft_type            ai_draft_type NOT NULL,
  input_source          VARCHAR(64),             -- voice / text / context
  prompt_version        INTEGER,
  ai_model              VARCHAR(64),
  content               TEXT NOT NULL,
  status                ai_draft_status NOT NULL DEFAULT 'generated',
  reviewed_by_user_id   UUID REFERENCES users(id),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_drafts_visit ON ai_drafts(visit_id);
```

---

## 8. Audit Log

### `audit_logs`
```sql
CREATE TABLE audit_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id       UUID NOT NULL REFERENCES clinics(id),
  user_id         UUID REFERENCES users(id),
  action          VARCHAR(64) NOT NULL,           -- patient.create, invoice.void, ...
  entity_type     VARCHAR(64) NOT NULL,
  entity_id       UUID,
  old_value_json  JSONB,
  new_value_json  JSONB,
  ip_address      VARCHAR(64),
  user_agent      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_clinic_time ON audit_logs(clinic_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
```

---

## 9. A2A-Ready 預留表

### `integrations`
```sql
CREATE TABLE integrations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id         UUID NOT NULL REFERENCES clinics(id),
  provider          VARCHAR(128) NOT NULL,
  integration_type  integration_type NOT NULL,
  status            VARCHAR(32) DEFAULT 'inactive',
  config_json       JSONB DEFAULT '{}'::jsonb,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `external_mappings`
```sql
CREATE TABLE external_mappings (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id      UUID NOT NULL REFERENCES clinics(id),
  entity_type    VARCHAR(64) NOT NULL,
  entity_id      UUID NOT NULL,
  provider       VARCHAR(128) NOT NULL,
  external_id    VARCHAR(255) NOT NULL,
  metadata_json  JSONB DEFAULT '{}'::jsonb,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(provider, external_id, entity_type)
);
```

### `agent_registry`
```sql
CREATE TABLE agent_registry (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id          UUID NOT NULL REFERENCES clinics(id),
  agent_name         VARCHAR(255) NOT NULL,
  agent_type         VARCHAR(64) NOT NULL,    -- inventory, document, billing...
  protocol           agent_protocol NOT NULL,
  endpoint_url       TEXT,
  capabilities_json  JSONB DEFAULT '{}'::jsonb,
  auth_config_json   JSONB DEFAULT '{}'::jsonb,
  status             VARCHAR(32) DEFAULT 'inactive',
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `agent_tasks`
```sql
CREATE TABLE agent_tasks (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id                UUID NOT NULL REFERENCES clinics(id),
  requested_by_user_id     UUID REFERENCES users(id),
  agent_id                 UUID REFERENCES agent_registry(id),
  task_type                VARCHAR(64) NOT NULL,
  input_json               JSONB NOT NULL,
  output_json              JSONB,
  status                   agent_task_status NOT NULL DEFAULT 'queued',
  priority                 INTEGER DEFAULT 0,
  human_review_required    BOOLEAN DEFAULT true,
  related_entity_type      VARCHAR(64),
  related_entity_id        UUID,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_tasks_clinic_status ON agent_tasks(clinic_id, status);
```

### `agent_events`
```sql
CREATE TABLE agent_events (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id           UUID NOT NULL REFERENCES clinics(id),
  agent_task_id       UUID NOT NULL REFERENCES agent_tasks(id),
  event_type          VARCHAR(64) NOT NULL,
  event_payload_json  JSONB DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_events_task ON agent_events(agent_task_id, created_at);
```

---

## 10. V2 預留（Sprint 8+）

```sql
-- Lab orders / results / purchase orders
-- Schema 已在規格 §10 列出，先 migration 但不寫業務邏輯
```

詳見 `A2A_READY_ARCHITECTURE.md` §4。

---

## 必要 Extensions

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- 病人名/藥名模糊搜尋
```

---

## Invariants（資料庫鐵律）

1. `drug_batches.quantity_current >= 0`（CHECK constraint）
2. 每筆 `drug_batches` 異動必有對應 `stock_movements`（service layer 保證）
3. `invoices.invoice_number` UNIQUE per `clinic_id`
4. `invoices.status='voided'` 必有 `voided_at` 與 `void_reason`
5. `prescriptions.status='dispensed'` 對應 visit.status='completed'
6. `ai_drafts.status='accepted'` 才能參考到正式表
7. 所有 multi-tenant 表的 `clinic_id` 必須匹配當前 user 的 active clinic
