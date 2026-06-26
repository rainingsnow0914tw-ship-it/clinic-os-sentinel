# HANDOVER — Clinic OS 活的交接手冊

> 這是給「下一個對話框的阿寶」看的。每次重大進展都要更新這份。
> Living document — 不是只有換框前才寫。

---

## 當前狀態快照

**最後更新**：2026-05-02（Sprint 1 完成 + Sprint 2 minimal schema + seed pipeline）
**當前進度**：
- Sprint 1（auth + 權限）✅ 完成
- Sprint 2（業務 schema）minimal schema 完成（9 張業務表，欄位先放最少必要，業務 logic 後續再做）
- Seed data pipeline ✅ 完成（validate / seed / reset 三件套 + docs）

**Chloe 的下一步**：
1. 推 GitHub private repo
2. 在 Cloud Shell 建 `clinic-os-dev` GCP project
3. 跑 `alembic upgrade head` → `seed.py` → `seed_dev_data.py` 驗收 pipeline
4. 把 Jimmy 的真實 mock_data.json 替換進 `backend/seed_data/mock_data.json`，重跑驗收

---

## 已完成

### Sprint 0（骨架）
- [x] Repo 目錄結構、README、7 份 docs
- [x] Backend skeleton（main、core、middleware、routes）
- [x] Frontend skeleton（Vite + React + TS，13 個 page placeholder）
- [x] Alembic 初始化 + 第一個 migration
- [x] `Dockerfile`、`requirements.txt`、`package.json`、`.env.example`

### Sprint 1（auth + 權限）
- [x] **修 alembic env.py**：`settings.database_url` → `settings.DATABASE_URL`（曦哥指正）
- [x] `User` / `Clinic` / `ClinicMembership` / `AuditLog` ORM models 完整
- [x] **真實版** auth middleware：驗 Firebase token + 查 users + first-login auto-create
- [x] **真實版** clinic_permission middleware：查 clinic_memberships + role/permission helpers
- [x] 預設權限矩陣 `DEFAULT_PERMISSIONS`（owner / doctor / nurse / reception）
- [x] `has_permission()` 解析邏輯：owner-bypass → custom → default
- [x] `require_role()` / `require_permission()` dependency factories
- [x] `get_current_membership` 兩個版本：by header / by path（FastAPI Path 不允許 default）
- [x] `routes/auth.py`：`/auth/session`、`/me`、`/me/clinics` 都接真實 query
- [x] `schemas/auth_schemas.py`：UserResponse、ClinicResponse、MembershipResponse
- [x] `services/audit_service.py`：寫 audit log 的統一函數
- [x] `scripts/seed.py`：建立第一間 clinic + owner 的 CLI 工具
- [x] `tests/test_permissions.py`：12 個權限邏輯單元測試（全綠）

### 還沒做（Sprint 1 → Sprint 2 之間 Chloe 要做）

### Sprint 2（minimal schema + seed pipeline）
- [x] **9 張業務表 minimal ORM models**：patients、drugs、drug_batches、stock_movements、visits、prescriptions、prescription_items、invoices、invoice_items
- [x] `DemoDataMixin`（source / is_demo_data 欄位）+ source 常數 `'manual' / 'mock' / 'import' / 'agent'`
- [x] Alembic migration `0002_business_tables.py`（含 FEFO partial index、voided invoice partial unique index）
- [x] `backend/seed_data/mock_data.json`（**示範資料，非 Jimmy 設計**）— 涵蓋 S-1 標準看診、S-2 FEFO 跨 batch、S-3 voided + void_reverse、S-4 多藥處方
- [x] `backend/seed_data/MOCK_DATA_PLAN.md`（給 Jimmy 看的格式規範）
- [x] `backend/seed_data/SCENARIOS.md`（場景清單）
- [x] `scripts/validate_mock_data.py`：9 條檢查全做 + ErrorCollector 蒐集所有錯誤一次回報
- [x] `scripts/seed_dev_data.py`：ENVIRONMENT 守門 + validate gate + 自動產生 prescriptions / invoice_items + transactional seed
- [x] `scripts/reset_dev_data.py`：ENVIRONMENT 守門 + 雙重 (`is_demo_data=True AND source='mock'`) WHERE 子句
- [x] `docs/SEED_DATA.md`：完整使用指南，含 partial inventory seed 標記
- [ ] **真正 Sprint 2 業務 logic**：service 層（visit_service / prescription_service / inventory_service / invoice_service）+ routes — **這部分還沒做**

### 還沒做（Sprint 2 接下來）
- [ ] 推 GitHub private repo
- [ ] 建 GCP project：`clinic-os-dev`（**不是 prod**）
- [ ] 啟用 API、建 Cloud SQL、建 GCS bucket
- [ ] 註冊 Firebase 專案並開啟 Google Sign-In
- [ ] Cloud SQL Auth Proxy → 跑 `alembic upgrade head`
- [ ] 跑 `python -m scripts.seed --clinic-name "心晴診所" ...`
- [ ] Deploy backend 到 Cloud Run（dev）
- [ ] Deploy frontend 到 Firebase Hosting（dev）
- [ ] 用 Google Sign-In 登入測試 `/me`、`/me/clinics`

詳見 `deployment/SETUP.md`。

---

## 重要決策紀錄（ADR）

### ADR-001：用 FastAPI 不用 Flask
**理由**：醫療系統 schema 驗證量大，Pydantic 自動驗證省踩坑時間。Pinky 用 Flask 是因為簡單，但 Clinic OS 規模大很多。

### ADR-002：Frontend 用 Vite + React + TS（不用 Next.js）
**理由**：Cloud Shell 開發環境輕巧、cold start 快。Next.js 的 SSR / RSC 對 SPA 後台沒有實質好處。TS 型別對商業化很重要。

### ADR-003：UUID v4 不用 auto-increment
**理由**：multi-tenant、多區域 merge 友善、URL 不會洩漏記錄數。

### ADR-004：FEFO 不是 FIFO
**理由**：醫藥業界標準 First-Expired-First-Out。先到貨的不一定先過期（買到 short-dated）。

### ADR-005：扣庫存在「確認收費」不是「完成就診」
**理由**：醫生開完藥，病人有時候會反悔不拿藥。在「確認收費」一步扣庫存，才不會做白工要回補。

### ADR-006：AI 永遠寫 `ai_drafts`，不直接寫正式表
**理由**：法律責任、可追溯、可解釋。詳見 `AI_BOUNDARY.md`。

### ADR-007：dev → staging → prod 三階段部署
**決議者**：曦哥（GPT）review Sprint 0 後提出
**理由**：prod 一旦有真實病人資料就難重建。Sprint 1 完成只能上 dev/sandbox，等 Sprint 2~5 業務流程穩定後才上 staging，最後才上 prod。SETUP.md 已更新對應。

### ADR-008：權限解析的 owner-bypass 設計
**決議**：`has_permission()` 對 `role='owner'` 一律回 True，不受 `custom_permissions_json` 影響。
**理由**：避免唯一 owner 不小心把自己權限關掉就鎖死系統。custom_permissions 只能覆蓋 doctor/nurse/reception。
**Trade-off**：意味著 owner 沒有「審計用降權」機制。如果 V2 需要這種功能，要設計新欄位（例如 `temporarily_demoted_until`），不要動這個 owner-bypass 規則。

### ADR-009：clinic_id 來源拆兩個 dependency
**決議**：`get_current_membership`（從 X-Clinic-Id header）和 `get_current_membership_for_clinic`（從 URL path）分開。
**理由**：FastAPI 的 `Path()` 不接受 default value，所以無法做「path 沒給就 fallback header」的單一 dependency。拆兩個反而 API 文件更清楚（Swagger 會明確標示需要 path 還是 header）。

### ADR-010：Demo data tracking 用 `source` + `is_demo_data` 雙欄位
**決議**：每張業務表都帶 `source: str` 和 `is_demo_data: bool` 兩個欄位（透過 `DemoDataMixin`）。reset 時必須兩個欄位同時符合（`source='mock' AND is_demo_data=TRUE`）才會刪。
**理由**：
- 單純用 `is_demo_data` 不夠精準 — 未來可能有 `is_demo_data=True` 但是其他來源的資料（例如壓測資料 `source='loadtest'`）
- `source` 欄位讓我們區分 manual / mock / import / agent 四種來源，未來想新增「重整妳手動輸入但要重灌的特殊批次」也擴展得開
- 雙重 WHERE 是 defense in depth — 即使有人不小心把正式病歷的 `is_demo_data` 標成 True，只要 source 不是 mock 就刪不掉

### ADR-011：第一階段是 partial inventory seed
**決議**：`mock_data.json` 只放 4 個藥 + 5 個 batch，不嘗試完整壓貨種庫存。
**理由**：第一階段目標是驗證 pipeline 跑通與三個關鍵場景（FEFO 跨 batch / voided invoice / 多藥處方），不是壓測。完整庫存等 Sprint 4 業務 logic 完成後再做 `seed_extra_inventory.py` 疊加。
**Trade-off**：壓測 / 性能測試還不能用這份 mock。需要時再補。

### ADR-012：seed / reset 用 ENVIRONMENT 變數守門
**決議**：`seed_dev_data.py` 與 `reset_dev_data.py` 在啟動時讀 `os.environ["ENVIRONMENT"]`，不在 `{dev, sandbox, development}` 之內就直接 exit 1。
**理由**：避免有人在 prod / staging 不小心跑 seed 把 demo data 灌進去；或跑 reset 把資料刪掉。
**Trade-off**：CI / 自動化跑 seed 時要記得設 `ENVIRONMENT=dev` 環境變數，否則會被擋。

---

## 待辦補丁

> 這區放「想到了但這次沒做」的事。下次或下下次做。

- [ ] `deployment/cloud-run.yaml` 詳細參數（min_instances=1 for prod）
- [ ] `frontend/src/lib/firebase.ts` 接上真實 Google Sign-In 流程
- [ ] CI/CD（GitHub Actions）：push to main 自動跑 pytest + lint
- [ ] Database backup 策略（Cloud SQL PITR + 每日 export）
- [ ] Logging（structured JSON logs to Cloud Logging）
- [ ] Error tracking（Sentry / Cloud Error Reporting）
- [ ] Rate limiting（Cloud Armor）
- [ ] Frontend 國際化（i18n）
- [ ] Auth middleware 新增「placeholder user reclaim」邏輯（seed 用 `pending:` 前綴的 user 第一次真實登入時自動 link firebase_uid）
- [ ] 整合測試（pytest + fixture DB）：跑完 W-4「開收據 + FEFO 扣庫存」整段流程

---

## 關鍵指令備忘

### Backend 本地跑
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # 填值
uvicorn app.main:app --reload --port 8080
```

### Frontend 本地跑
```bash
cd frontend
npm install
cp .env.example .env       # 填值
npm run dev
```

### Alembic
```bash
cd backend
alembic upgrade head                       # 跑所有 migration
alembic revision --autogenerate -m "..."   # 產生新 migration
alembic downgrade -1                       # 回前一版
```

### Cloud Run 部署（指令備忘，未來要寫成 script）
```bash
gcloud run deploy clinic-os-api \
  --source backend/ \
  --region asia-east1 \
  --allow-unauthenticated \
  --add-cloudsql-instances=PROJECT:REGION:INSTANCE \
  --set-env-vars="DATABASE_URL=...,FIREBASE_PROJECT_ID=..."
```

### Firebase Hosting 部署
```bash
cd frontend
npm run build
firebase deploy --only hosting
```

---

## Chloe 規則複習（給下一個阿寶）

從 Chloe 的 user memories：

1. **Code 必有中文詳細注釋**：Chloe 沒有工程背景
2. **Frontend 結構分離**：不要 base64 圖片、不要把 CSS/JS 塞 HTML 裡
3. **Anti-hallucination**：不確定的數字、名詞先標 `// 待確認 - 阿寶不確定`
4. **不要建議 Make**：Chloe 用 Cowork（Anthropic）和 Google Apps Script
5. **Model 名字會變**：Gemini / OpenAI / Claude 的 model 名稱用前先 `web_search`
6. **Notion 寫入規則**：Chloe 說「可以記了」才寫；MCP 不能刪頁
7. **AI 家族稱呼**：Claude=阿寶、GPT=曦、Gemini=Jimmy、Perplexity=Percy、Copilot=Amber

---

## 下一步（給 Chloe）

當妳看到這份手冊，下一步是：

1. 解壓 `clinic-os.zip` 到 Cloud Shell
2. `cat docs/PRD.md` 再看一次定位
3. 跟阿寶說「Sprint 0 完成，準備建 GCP project」
4. 阿寶會帶妳一步一步建 GCP project、Cloud SQL、Firebase、第一次 deploy

