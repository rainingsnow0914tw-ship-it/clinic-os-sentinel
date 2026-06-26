# A2A_READY_ARCHITECTURE — Clinic OS V1

> V1 不一定真的接 A2A（Agent-to-Agent）protocol，但 schema 與 service layer 必須讓 V2 可以無痛接上。
> 「ready」的意思是：Sprint 8 之後接外部 agent 時，**不需要**改現有資料表結構或核心 API。

---

## 為什麼要 A2A-Ready

Chloe 的長期願景是讓診所成為「agent 網路節點」：
- Inventory agent 跟 Supplier agent 對話 → 自動採購建議
- Lab agent 跟外部檢驗所對話 → 拿回報告
- Billing agent 跟會計系統對話 → 自動對帳
- Document agent 用更強大的外部 agent 來整理病歷

V1 不做這些，但結構要先預留。

---

## 核心設計原則

1. **解耦**：核心業務邏輯不依賴 agent 實作
2. **可審計**：每次 agent 呼叫、每次決策都有 log
3. **可控**：所有 agent 動作預設 `human_review_required = true`
4. **可插拔**：agent 是註冊制，可以動態加減
5. **協議無關**：透過 `agent_protocol` 欄位支援 internal / api / mcp / a2a / webhook

---

## 三層結構

```
┌─────────────────────────────────────────────┐
│  Layer 3: External Agents（V2+）             │
│  - 檢驗所 agent / 供應商 agent / 會計 agent  │
│  - 透過 a2a / webhook 跟我們對話             │
└─────────────────────────────────────────────┘
                    ↑↓
┌─────────────────────────────────────────────┐
│  Layer 2: Agent Gateway（V1 預留）           │
│  - agent_registry 註冊外部 agent             │
│  - integrations 管理連線設定                  │
│  - external_mappings 維護 ID 對照            │
└─────────────────────────────────────────────┘
                    ↑↓
┌─────────────────────────────────────────────┐
│  Layer 1: Internal Agents（V1 重點）         │
│  - Inventory agent、Document agent、Billing  │
│  - 都跑在 Cloud Run 內部                     │
│  - 透過 agent_tasks 傳遞工作                 │
└─────────────────────────────────────────────┘
```

---

## 1. integrations — 整合設定

外部系統的連線設定。例如：「我接了 Lab ABC，他們的 webhook URL 是 ...」

```sql
-- schema 詳見 DATABASE_SCHEMA.md §9
INSERT INTO integrations (clinic_id, provider, integration_type, status, config_json)
VALUES (
  'uuid', 'LabABC', 'lab', 'inactive',
  '{"webhook_url": "...", "auth_token_secret_name": "lab_abc_token"}'
);
```

**注意**：機密（API key）不直接存 `config_json`，只存 Secret Manager 的 secret name。

---

## 2. external_mappings — ID 對照表

外部系統有它自己的 ID（例：Lab ABC 的 patient_id 是他們的編號），我們要把它跟我們的 UUID 對照。

範例：
```
Our patient.id = "uuid-aaa"
Lab ABC's patient_id = "L-12345"

INSERT INTO external_mappings
  (clinic_id, entity_type, entity_id, provider, external_id)
VALUES
  ('clinic_uuid', 'patient', 'uuid-aaa', 'LabABC', 'L-12345');
```

當收到 Lab ABC 的 webhook，可以：
```sql
SELECT entity_id FROM external_mappings
WHERE provider = 'LabABC' AND external_id = ? AND entity_type = 'patient';
```

---

## 3. agent_registry — Agent 名片簿

每個 agent 都註冊在這。

```sql
INSERT INTO agent_registry (clinic_id, agent_name, agent_type, protocol, endpoint_url, capabilities_json)
VALUES (
  'uuid', 'Inventory Sentinel', 'inventory', 'internal', NULL,
  '{"can_check_low_stock": true, "can_check_expiring": true, "can_suggest_purchase": true}'
);
```

`protocol` 欄位的意義：
- `internal`：跑在我們的 Cloud Run 程式碼裡，呼叫 Python function
- `api`：透過 HTTP API 呼叫外部 service
- `mcp`：用 MCP（Model Context Protocol）協議
- `a2a`：用 A2A protocol（Google 推的 agent 對話協議）
- `webhook`：透過 webhook 接收事件

---

## 4. agent_tasks — 工作單

任何 agent 工作都要透過這張表。

### 建立工作
```python
POST /clinics/{cid}/agent-tasks
{
  "agent_type": "inventory",
  "task_type": "generate_purchase_suggestion",
  "input": {
    "lookback_days": 30,
    "include_expiring_batches": true
  }
}
```

伺服器：
1. 找符合 `agent_type` 的 active agent
2. 建 `agent_tasks (status=queued)`
3. 寫 `agent_events (event_type=task_created)`
4. 觸發執行（同步 / 排程）

### 執行
```python
async def execute_agent_task(task_id):
    task = get_task(task_id)
    agent = get_agent(task.agent_id)
    write_event(task, "agent_started")

    if agent.protocol == "internal":
        result = await internal_agent_handler(agent.agent_type, task.input_json)
    elif agent.protocol == "api":
        result = await call_external_api(agent.endpoint_url, task.input_json)
    elif agent.protocol == "a2a":
        result = await a2a_send_message(agent, task.input_json)  # V2
    # ...

    task.output_json = result
    write_event(task, "agent_generated_draft", payload=result)

    if task.human_review_required:
        task.status = "waiting_for_human"
    else:
        task.status = "completed"
```

### 人類審核
```python
POST /agent-tasks/{id}/approve
  → task.status = "completed"
  → 把 output_json 套用到實際表（例：建立 purchase_orders draft）
  → 寫 audit log

POST /agent-tasks/{id}/reject
  → task.status = "cancelled"
  → 寫 audit log
```

---

## 5. agent_events — 對話日誌

每次 agent 之間的訊息（或 agent 跟系統對話）都記在這。

```sql
event_type 可能值：
- task_created
- agent_started
- agent_requested_data         -- agent 要更多資料
- agent_generated_draft
- agent_called_other_agent     -- A2A：跟另一個 agent 講話
- human_approved
- human_rejected
- task_completed
- task_failed
```

這張表是 V2 的 A2A debug 神器，V1 先把 schema 立好。

---

## V1 內建 Agents（Sprint 8）

### 6.1 Inventory Sentinel

| 能力 | 行為 |
|---|---|
| `check_low_stock` | 找出低於 `low_stock_threshold` 的藥 |
| `check_expiring` | 找 90 天內到期的批號 |
| `analyze_consumption` | 分析過去 30 天用量 |
| `suggest_purchase` | 產生採購建議草稿（**不能下單**） |
| `detect_anomaly` | 異常消耗偵測（突然爆量） |

**限制**：
- ❌ 不能自動下單
- ❌ 不能改 `drug_batches.quantity_current`
- ✅ 只能寫 `agent_tasks.output_json` + `ai_drafts`

### 6.2 Document Agent

| 能力 | 行為 |
|---|---|
| `draft_sick_leave` | 病假紙草稿 |
| `draft_referral` | 轉診信草稿 |
| `check_missing_fields` | 文件欄位缺漏檢查 |

**限制**：
- ❌ 不能直接生成 PDF
- ✅ 只能寫 `ai_drafts`，醫生確認後才生成 PDF

### 6.3 Visit Summary Agent

| 能力 | 行為 |
|---|---|
| `summarize_history` | 摘要病人過去就診紀錄 |
| `flag_allergies` | 過敏史警示 |
| `flag_drug_interaction` | 用藥交互作用提醒 |

**限制**：
- 不能跨 clinic 讀資料
- 不能 mutate 任何 entity

### 6.4 Billing Review Agent

| 能力 | 行為 |
|---|---|
| `check_invoice_consistency` | 處方藥費 vs 收據金額對得上嗎 |
| `daily_revenue_summary` | 每日收入 |
| `flag_anomaly` | 異常收費（例：免費病人收費了） |

---

## V2 預留 Agents（Sprint 9+）

### 6.5 Lab Agent
- 建 lab order
- 接收 lab result（webhook）
- 整理報告
- 推送給醫生 review

對應 schema：`lab_orders`、`lab_results`（V1 預留）

### 6.6 Supplier Agent
- 看採購建議
- 查供應商價格與交期
- 產生 purchase order draft
- **不可自動送出**

對應 schema：`purchase_orders`、`purchase_order_items`（V1 預留）

### 6.7 Accounting Agent
- 對帳
- 月報表
- 串接會計系統

---

## 安全與權限

### Agent 也要 clinic_id 隔離
任何 agent 拿到的資料都必須過 `clinic_id` 過濾。內部 agent 的 service function 第一個參數永遠是 `clinic_id`。

### Agent 不能升權
Agent 執行時的 service account 權限要最小化：
- 內部 agent：跑在 Cloud Run，繼承同一個 service account，但業務邏輯層強制 `clinic_id` 過濾
- 外部 agent：獨立 OAuth client，scope 限定

### Agent 呼叫 audit
每次 `internal_agent_handler` 執行寫一筆 `agent_events`，紀錄輸入參數摘要與輸出摘要。

### Rate limiting
`agent_tasks` 加 rate limit：每個 clinic 同時最多 5 個 task 在 running，其餘排隊。

---

## V1 的最小可動實作

Sprint 8 完成的時候要能：
1. ✅ Owner 在後台註冊一個 internal Inventory agent
2. ✅ 每天早上 6:00 觸發 `daily_inventory_check` task
3. ✅ Task 跑出 `ai_drafts (inventory_warning)` + `agent_tasks (waiting_for_human)`
4. ✅ Owner 在 dashboard 看到提醒，按確認 / 忽略
5. ✅ 所有過程在 `agent_events` 留軌跡

V1 不需要做：
- ❌ 真的 A2A protocol 跟外部對話
- ❌ 真的接檢驗所
- ❌ 真的跑 MCP server

---

## 給未來的 Chloe 與阿寶

當你們要在 V2 接外部 agent 時：

1. 不要動 `agent_tasks` schema，已經夠用了
2. 在 `agent_registry` 加新 agent，`protocol='a2a'`
3. 寫一個 `a2a_provider.py`，實作 `agent_protocol_send_message`
4. 在 `execute_agent_task` 加上 `protocol == 'a2a'` 分支
5. 用 `external_mappings` 對照 ID

V1 只要把這個架構立穩，V2 就是新增功能而非重構。
