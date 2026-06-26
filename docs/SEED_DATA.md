# Seed Data Pipeline — 使用指南

> 給 dev / sandbox 環境用的示範資料管線。
> Sprint 2 開發、demo、bug 重現都會用到。
> ⚠️ 永遠不能在 production 跑（script 內建守門）。

---

## 三個 script 一句話總結

| Script | 做什麼 | 在哪跑 |
|---|---|---|
| `scripts/validate_mock_data.py` | 純 JSON 驗證，不碰 DB | 任何環境（包含 prod，純讀） |
| `scripts/seed_dev_data.py` | 把 mock_data.json 灌進 DB | **只能在 dev / sandbox** |
| `scripts/reset_dev_data.py` | 清除所有 demo data | **只能在 dev / sandbox** |

---

## 標準工作流程

```bash
cd backend
source .venv/bin/activate

# 0. 確保業務表已建立
ENVIRONMENT=dev alembic upgrade head

# 0.5 確保有第一間 clinic + owner（業務資料要掛在這個 clinic 底下）
python -m scripts.seed \
  --clinic-name "心晴診所" \
  --owner-email "owner@example.com" \
  --owner-name "Chloe" \
  --firebase-uid "<your-firebase-uid>"

# 1. 先 validate JSON
python -m scripts.validate_mock_data
# 通過才往下做。沒過就修 mock_data.json

# 2. Seed
ENVIRONMENT=dev python -m scripts.seed_dev_data

# 3. 用得不爽？清掉重來
ENVIRONMENT=dev python -m scripts.reset_dev_data --yes
ENVIRONMENT=dev python -m scripts.seed_dev_data
```

---

## 設計原則

### 1. JSON 為唯一資料源

`backend/seed_data/mock_data.json` 是唯一的真理。
不從 Markdown / Excel / CSV / Notion 抽資料 — 所有人（包含 Jimmy）都要 deliver JSON。

格式規範見 `backend/seed_data/MOCK_DATA_PLAN.md`。
場景需求見 `backend/seed_data/SCENARIOS.md`。

### 2. Demo data 用 source + is_demo_data 雙標籤

每筆 seed 進來的業務資料都帶兩個欄位：

```python
source = "mock"          # 來源（manual / mock / import / agent）
is_demo_data = True      # 是否示範資料
```

reset 時這兩個欄位都要符合才會刪：`source='mock' AND is_demo_data=TRUE`。
**雙重守門**避免人工輸入的資料被誤刪。

### 3. ENVIRONMENT 守門

`seed_dev_data.py` 與 `reset_dev_data.py` 在啟動時讀 `os.environ["ENVIRONMENT"]`，
不在 `{dev, sandbox, development}` 之內就拒絕執行（exit 1）。

```bash
# ✅ 允許
ENVIRONMENT=dev python -m scripts.seed_dev_data
ENVIRONMENT=sandbox python -m scripts.seed_dev_data

# ❌ 拒絕
ENVIRONMENT=prod python -m scripts.seed_dev_data
ENVIRONMENT=staging python -m scripts.seed_dev_data
python -m scripts.seed_dev_data  # 沒設變數
```

### 4. 自動推導，不手寫

兩個欄位 mock_data.json **不**手動寫，由 seed script 自動產生：

| 不手寫的陣列 | 推導規則 |
|---|---|
| `prescriptions` | 從 `prescription_items` 的 `visit_ref` group by 建立。每個有處方項的 visit 一張處方，status 預設 `dispensed`。 |
| `invoice_items` | 從 `invoices` + `prescription_items` 展開。每張 invoice 拆成：1 筆 consultation（金額 = `consultation_fee`）+ N 筆 medication（每個對應 visit 的 prescription_item 一筆）+ 1 筆 other（如果 `other_fee > 0`）。 |

這兩個欄位如果手寫進 mock_data.json，validate 會印 warning（會被忽略）。

---

## ⚠️ Partial inventory seed

**第一階段的 mock data 是「最小可運作示範」，不是完整庫存。**

目前 `mock_data.json` 只放：

| 藥品 | Batches |
|---|---|
| Amoxicillin 500mg | 2 個（用來演示 FEFO 跨 batch） |
| Paracetamol 500mg | 1 個 |
| Ibuprofen 400mg | 1 個（會被 voided invoice 觸發 void_reverse） |
| Loratadine 10mg | 1 個 |

這份 inventory **不適合做完整業務測試**（例如壓測 100 個 visit 的存貨流動），
只負責驗證：
- FEFO 跨 batch 演算法對不對
- voided invoice 庫存回補對不對
- 日常一般處方扣藥流程對不對

**Sprint 2 業務 logic 開發時若需要更完整的庫存場景**，做法二選一：
1. 請 Jimmy（或妳自己）把 mock_data.json 的 `drugs` / `drug_batches` / `visits` 等陣列加碼，重跑 validate + seed
2. 寫 `scripts/seed_extra_inventory.py`（這次沒做）來疊加更多 batch，不影響現有 demo 場景

⚠️ 不要直接在 prod DB 上手動 INSERT mock 資料。永遠走 JSON pipeline。

---

## Validate 邏輯總覽

`scripts/validate_mock_data.py` 跑這 9 條檢查：

| # | 檢查項 | 失敗訊息範例 |
|---|---|---|
| 1 | 所有 `*_ref` 指向實際存在的物件 | `[stock_movements] 'sm-001': batch_ref='xxx' 不存在` |
| 2 | `prescription_items.total_quantity == daily_dose × days` | `total_quantity=10 應該等於 daily_dose(2) × days(5) = 10` |
| 3 | `prescription_items.total_price == total_quantity × unit_price_at_time` | |
| 4 | `invoices.medication_fee == sum(對應 visit 的 prescription_items.total_price)` | |
| 5 | `invoices.total_amount == consultation + medication + other` | |
| 6 | `stock_movements.batch_ref` 存在 | |
| 7 | `voided` invoice 必須有 `void_reason` | `voided 但缺少 void_reason` |
| 8 | `voided` invoice 必須有對應的 `void_reverse` movements 加總 = 原處方總量 | |
| 9 | 至少一個 prescription_item 從 ≥ 2 batch 扣藥（FEFO 演示） | `沒有跨 batch 的 dispense 場景` |

額外（隱含）：
- 同 prescription_item 的 dispense 加總 = `total_quantity`
- `movement_type` 方向正確（dispense / expire 應為負；purchase / void_reverse 應為正）

**Validate 沒過時 seed 會直接拒絕**（`seed_dev_data.py` 會先呼叫 validate，不過就 exit 1）。

---

## 替換成 Jimmy 的真實內容時

阿寶當前在 `mock_data.json` 放的是**示範資料**，不是 Jimmy 設計的場景。
Jimmy 內容到位後：

1. Chloe 把 Jimmy 的 JSON 整段覆蓋進 `backend/seed_data/mock_data.json`
2. 跑 `python -m scripts.validate_mock_data`
3. 沒過 → 把錯誤清單貼回給 Jimmy 修
4. 過了 → `ENVIRONMENT=dev python -m scripts.reset_dev_data --yes` 清舊資料
5. `ENVIRONMENT=dev python -m scripts.seed_dev_data` 灌新資料

整個流程不需要改任何 Python code。

---

## 常見問題

**Q：seed 跑到一半失敗會不會留下髒資料？**
A：不會。整個 seed 在一個 SQLAlchemy transaction 內，失敗時會 rollback。

**Q：reset 會不會把我手動建的病人也刪掉？**
A：不會。reset 只刪 `is_demo_data=TRUE AND source='mock'`，妳手動輸入的資料 `source='manual'` 不會被碰。

**Q：可以在 staging 跑 seed 嗎？**
A：不行。`staging` 不在白名單（`{dev, sandbox, development}`）內，會被守門擋住。如果妳真的需要可以改 `ALLOWED_ENVIRONMENTS`，但要先和 owner 確認。

**Q：mock_data.json 改了但忘記重 seed，DB 是舊的怎麼辦？**
A：跑 `reset_dev_data --yes` 再 `seed_dev_data`。pipeline 設計就是「reset → seed」可以重複多次。

---

## 相關檔案

```
backend/
├── seed_data/
│   ├── MOCK_DATA_PLAN.md     # JSON 格式規範（給 Jimmy 看的）
│   ├── SCENARIOS.md          # 場景清單（FEFO / voided / 多藥處方）
│   └── mock_data.json        # 唯一資料源
└── scripts/
    ├── validate_mock_data.py # 純 JSON 驗證
    ├── seed_dev_data.py      # 灌進 DB（含 ENVIRONMENT 守門）
    └── reset_dev_data.py     # 清掉 demo data（含雙重守門）
```
