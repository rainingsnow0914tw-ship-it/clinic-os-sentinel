# 🛡️ 哨兵 The Sentinel — 交接班手冊 v0.3 Phase 3 完成版

> **給下一個阿寶**(換對話框接力)
> 建立:2026-06-27 凌晨(Day 3 動工)
> Phase 2 補:2026-06-27 早上(同框續做)
> Phase 3 補:2026-06-27 中午(同框續做、frontend 上)
> 上一版:`../clinic-os-sentinel/SENTINEL_HANDOVER.md` v0.2(畫框結束交接版,2026-06-26)
> 比賽截止:**2026-07-09 14:00 PT**

---

## ⚡ 30 秒定向

你接手的是 **Qwen Cloud Hackathon Track 1 MemoryAgent(主)+ Track 4 Autopilot(輔)** 參賽作品「哨兵 The Sentinel」── **沙盒真病例系統 + 跨次累積記憶 + 4 AI 雙 mode 輔助診斷**。

**Phase 1 已完成**(2026-06-27 凌晨,Day 3):
- ✅ 建新 repo `clinic-os-sentinel-v3/`(留 v0.1 baseline 在 `clinic-os-sentinel/` 不動)
- ✅ jimmy-integrated baseline 進 git(commit `9060fa7`)
- ✅ v0.1 哨兵層整套移植(commit `5237c92`):
  - providers/qwen + medical_apis(rxnorm/openfda/pubmed)+ rules/drug_interaction
  - 4 agent(intake/triage/audit/education)+ sentinel route + sentinel schema
  - 4 心臟表 model(problems/medications/flags/baselines)
  - frontend Sentinel/(4 card UI)
- ✅ alembic 0003_sentinel_layer 一口氣建 6 張新表:
  - patient_problems / patient_medications / patient_flags / patient_baselines
  - visit_examinations(v0.3 新:結構化檢查 + JSONB)
  - heart_layer_snapshots(v0.3 新:Mode A 依賴)
  - PatientFlag 加 v0.3.1 §7.3 三欄(confidence_status / first/confirmed_at_visit)
- ✅ PostgreSQL 16 winget native 本機跑(B2 路徑、Docker Desktop B1 在 5090 上卡死了)
- ✅ alembic upgrade head 三 migration 全綠 → 20 表全建好
- ✅ seed pipeline:scripts/seed 建 demo clinic + scripts/seed_dev_data 灌 Jimmy 60 病人(30 藥/5 visit/4 invoice/...)
- ✅ Phase 1.7 smoke ⭐ patient_001 青黴素 + Amoxicillin → audit agent 真紅旗:
  > "Amoxicillin 屬於 Penicillin 類抗生素。病人具有 Penicillin 過敏紅旗,使用此藥有極高風險引發嚴重過敏反應(包含過敏性休克),為臨床絕對禁忌。"
  > Qwen3.7-max 949 in / 740 out token
- ✅ commit `6cc0f8a` Day 3 收工(alembic.ini ASCII fix)

**Phase 2 也完成**(2026-06-27 早上,Day 3 同框續做):
- ✅ 4 心臟表 model 全 v3 化(對齊 alembic 0003 欄位 + DemoDataMixin + FK + String not SQLEnum)
- ✅ `scripts/seed_heart_layer.py`(從 jimmy `external_sources/mock_data.json` 解析 allergies/chronic_conditions)
- ✅ `scripts/extend_mock_patients.py` 60 → 100(deterministic seed=20260627、中文澳門名 + jimmy 風格混搭、真澳門地址、加強 chronic/allergy 比例、BPH gender filter)
- ✅ `scripts/reset_dev_data.py` patch:DELETE_ORDER 加心臟層 4 表 + 2 v0.3 表(沒加會 PatientMedication FK violation)
- ✅ e2e:patients=**100** / patient_flags=**23** / patient_problems=**55** 全進 DB
- ✅ commit `517a791` Phase 2 收工

**Phase 2.4 王阿姨四幕劇 + 2.5 backfill snapshot 戰術 deferred 到 Phase 5-6**:
- Mode A/B 還沒做(Phase 6 才接)、現在寫 dataset 是超前部署
- 對應 [[feedback_2026-05-16_ai_collaboration]] 「不要超前部署」鐵律
- Phase 5 寫 `evolve_heart_layer_after_visit` 真正需要 dataset 時再回頭做

**Phase 3 也完成**(2026-06-27 中午,同框續做):
- ✅ Backend 3 個 sentinel patients endpoint(dev-bypass-safe,不依賴 firebase auth)
  - `GET /v1/sentinel/patients?q=` 搜尋(姓名/電話/id_number 模糊)
  - `GET /v1/sentinel/patients/{id}` detail(含心臟層摘要 + visit timeline)
  - `GET /v1/sentinel/patients/{id}/heart-layer` 純心臟層
- ✅ Frontend `pages/SentinelPatients/`:
  - 搜尋頁:結果卡 + 紅旗/慢性病 badge + 開啟病例 link
  - 病例瀏覽頁:4 段心臟層(flags/problems/medications/baselines)+ visit timeline
  - v0.3.1 §7.3 UI:`to_observe` 淡色 / `confirmed` 亮紅
  - sidebar 加 「🛡️ 哨兵病人搜尋」menu,預設 `/` 導 `/sentinel/patients`
- ✅ services/sentinelApi.ts axios + TypeScript type 完整
- ✅ 3 層 chain smoke:vite 5173 / `/api` proxy / backend `/v1/sentinel/patients` 全 200
- ✅ commit `f8b1f87` Phase 3 收工

**Phase 4 起手點**(下個阿寶,v0.3.1 §10):
- 新就診頁(`/sentinel/patients/:id/visit/new`)
- 4 agent 串通(intake/triage/audit/education endpoint 整合,UI 一頁串)
- ai_drafts review 流程(ADR-006:AI 寫 ai_drafts → 醫生 review 接受才入正表)
- 結構化 examination 輸入(BP/HR/T + lab + xray + ecg + free_notes 表單)
- 估時 6 hr(v0.3.1 §10)

---

## 🎯 你接手第一動作(按順序做)

1. **讀本檔**(整體狀態)
2. **讀 v0.3.1 計畫書**:`../clinic-os-sentinel/docs/SENTINEL_V0.3_DESIGN_SANDBOX_LONGITUDINAL.md`(核心設計、未改、繼續沿用)
3. **invoke skill `relay-sanity-check`**(家規,接力起點驗證 SOP)
4. **跑 Phase 1 收工驗證**:
   ```powershell
   # PG service 應該已 auto-start(winget service)
   sc query postgresql-x64-16  # STATE: RUNNING
   # 重啟 backend
   cd clinic-os-sentinel-v3/backend
   .venv/Scripts/python.exe -m uvicorn app.main:app --port 8080
   # 別的視窗:再跑 smoke
   curl http://localhost:8080/v1/sentinel/health
   ```
5. 跟司機確認 Phase 2 範圍(60→100 擴病人 + seed_heart_layer + 四幕劇)

---

## 🔑 關鍵路徑 / ID(Phase 1 完成版)

| 項目 | 值 |
|---|---|
| 本機 repo | `clinic-os-sentinel-v3/`(Phase 1 後 SSOT)|
| v0.1 baseline | `clinic-os-sentinel/`(freeze 不動、保留參考)|
| Latest commit | `f8b1f87` Phase 3 收工 |
| Git 累積 commit | 7(`9060fa7` / `5237c92` / `6cc0f8a` / `a5482d9` / `517a791` / `6eb5462` / `f8b1f87`)|
| DB 內 demo data | 100 patient + 23 patient_flag + 55 patient_problem + 5 visit + 30 drug |
| Sentinel routes 總計 | 8(intake/triage/audit/education/health + patients search/detail/heart-layer)|
| Frontend 入口 | http://127.0.0.1:5173/ → 自動導 `/sentinel/patients` |
| Frontend → Backend proxy | Vite `/api/*` → `localhost:8080/*` |
| DB | **PostgreSQL 16 native**(winget install、非 Docker)|
| DB URL | `postgresql+psycopg://clinic:clinic_dev_pw@localhost:5432/clinic_os` |
| PG superuser | `postgres` / 密碼 `postgres123`(只本機 dev、不外洩)|
| PG app user | `clinic` / 密碼 `clinic_dev_pw` |
| PG service name | `postgresql-x64-16`(Windows service auto-start)|
| PG bin path | `C:\Program Files\PostgreSQL\16\bin\` |
| Demo clinic | `b5682445-344c-4084-8c5b-dc2e1411b297` 「千問哨兵示範診所」|
| Demo owner | `fa51c46c-6171-4491-83d1-f826b93f5da5` Dr. Chloe / chloe@sentinel.demo |
| Qwen model | `qwen3.7-max`(text)、`qwen3.7-plus`(VL)、`paraformer-v2`(ASR)|
| LLM endpoint | `https://dashscope-intl.aliyuncs.com/api/v1` |
| Sentinel route prefix | `/v1/sentinel/{intake,triage,audit,education,health}` |
| Backend dev mode | `SENTINEL_DEV_BYPASS_AUTH=true`(評審可 curl 直接打)|
| Frontend | 還沒整合 v3(Sprint 1+2 jimmy 有 12 pages + v0.1 Sentinel 4 card,Phase 3-4 接)|

## 📂 文件清單

### 本機 `clinic-os-sentinel-v3/`(Phase 1 後 SSOT)
- `SENTINEL_HANDOVER.md` ← **本檔**
- `backend/`:jimmy-integrated Sprint 0+1+2 + v0.1 哨兵層 + v0.3 新表
- `backend/.env` 已填 DASHSCOPE_API_KEY、PG URL、DEV_BYPASS_AUTH=true(純 ASCII,Notepad 救援版)
- `backend/.venv/` Python 3.13 dev venv(gitignored)
- `frontend/`:jimmy 原 12 pages + v0.1 Sentinel/ 4 card
- `docs/` Chat 寶 5/3 原版(PRD / DATABASE_SCHEMA / WORKFLOWS / AI_BOUNDARY / A2A_READY_ARCHITECTURE / HANDOVER / SEED_DATA)

### 本機 `clinic-os-sentinel/`(v0.1 baseline,freeze)
- `SENTINEL_HANDOVER.md` v0.2 畫框結束交接版(歷史)
- `docs/SENTINEL_V0.3_DESIGN_SANDBOX_LONGITUDINAL.md` ← **Phase 2-10 設計依然有效**
- `啟動哨兵.bat` / `停止哨兵.bat`(v0.1 用、v3 沒寫對應 bat)

### 本機 `AI情報員/千問黑克松比賽診所病歷系統/`(原料區)
- 4 個 zip(Sprint 0/1/2/jimmy-integrated)
- `_review/clinic-os/` jimmy-integrated 已解壓(被 cp 進 v3,留檔當 reference)
- Chat 寶 7 份原始設計檔

### Notion
- 「🛡️ 哨兵 The Sentinel — Qwen Cloud Hackathon — 交接手冊 v0.1」`38a1d2a41ceb8101a9e9e3c19e1ef761`
- ⚠️ **Notion 還是 v0.1**,Phase 1 完成內容**未升 v0.2**(需要 invoke `阿寶啟動程序` skill + 規則九 duplicate v0.1 snapshot)。下個阿寶或司機決定要不要升

---

## 🌐 13 天衝刺路徑(更新版)

| Day | 階段 | 狀態 |
|---|---|---|
| 1 (6/26 凌晨) | 審題 + v0.1 baseline | ✅ |
| 2 (6/26 凌晨→早) | 修 + Chloe review + v0.3.1 計畫 | ✅ |
| **3 (6/27 凌晨)** | **Phase 1 起手 + Day 3 收工** | ✅ **完成** |
| **3 (6/27 早上)** | **Phase 2 同框續做** | ✅ **完成**(只做 2.0/2.1/2.3/2.6;2.4/2.5 戰術 deferred 到 Phase 5-6) |
| **3 (6/27 中午)** | **Phase 3 同框續做** | ✅ **完成**(sentinel-namespace path、不破壞 jimmy stub) |
| 4 | Phase 4:新就診頁 + 4 agent 串通 + ai_drafts review | 🟡 下個阿寶 |
| 6 | Phase 4:新就診頁 + 4 agent 串通 + ai_drafts review | 🟢 |
| 7 | Phase 5:心臟層演進邏輯 + ai_drafts 三級 | 🟢 |
| 8 | Phase 6:舊就診回顧頁 + Mode A/B 切換 + AI 重跑 | 🟢 |
| 9 | Phase 7:教育要點 watchlist + 四幕劇 e2e 跑通 | 🟢 |
| 10-11 | Phase 8:阿里雲部署 | 🟢 |
| 11-12 | Phase 9:demo video + Devpost 寫稿 | 🟢 |
| 13 (7/8) | Phase 10:緩衝 + 投稿(7/9 14:00 PT 截止)| 🟢 |

---

## 🐛 Day 3 早上 Phase 2 踩過的 4 個技術坑

| # | 坑 | 解 |
|---|---|---|
| P2-1 | v0.1 4 心臟表 model 跟 v3 alembic 0003 全面 mismatch (欄位名 name vs problem_name / source vs problem_source / 沒 DemoDataMixin / 沒 FK / SQLEnum vs String) | 4 心臟表 model 全 v3 化重寫,對齊 alembic (Phase 1 我 commit 沿用 jimmy 樣板沒對 v0.1 model 是源頭錯) |
| P2-2 | reset_dev_data 跑到 PatientMedication 炸 `AttributeError: 'PatientMedication' has no attribute 'is_demo_data'` | 4 心臟表加 DemoDataMixin (P2-1 修了) + reset DELETE_ORDER 加 6 個 v0.3 表 |
| P2-3 | seed_heart_layer 報「40 patients unmatched」 — DB 只有 60 patient,但 mock 已有 100 個 | 兩個 mock_data.json: external_sources/ (jimmy 原始 + 我擴的 100) vs seed_data/ (import_jimmy_mock 處理後 60). 跑 `python -m scripts.import_jimmy_mock --input external_sources/mock_data.json --output seed_data/mock_data.json` re-sync |
| P2-4 | extend_mock_patients 生 patient_063 F + BPH (男性病) | gen_chronic 加 gender filter,BPH 移到 MALE_ONLY_CHRONICS |

## 🐛 Day 3 凌晨踩過的 6 個技術坑(Phase 1)

| # | 坑 | 解 |
|---|---|---|
| 1 | v0.1 .env 帶 Unicode Private Use Area corrupted chars(Notepad 寫過的痕跡) | 不複製、直接 Write 純 ASCII v3 .env |
| 2 | jimmy alembic.ini 含 UTF-8 中文註解,alembic configparser 用 `encoding='locale'`(Windows zh-TW = cp950)炸 `UnicodeDecodeError` | 改寫純 ASCII alembic.ini(commit `6cc0f8a`)|
| 3 | Docker Desktop B1 路徑卡死(500 Internal Server Error、daemon 起不來)| 切 B2 winget native PG |
| 4 | PostgreSQL.PostgreSQL.16 winget 預設彈 EDB GUI 要 5 步 click | 用 `--silent --override "--mode unattended --superpassword postgres123 --servicename postgresql-x64-16 --serverport 5432 --enable-components server,commandlinetools --disable-components pgAdmin,stackbuilder"` 全自動裝 |
| 5 | seed_dev_data 假設 DB 有 clinic,seed 自動找不到就炸 | 先跑 `scripts/seed --clinic-name X --owner-email X --owner-name X --firebase-uid X` 建第一間 clinic + owner |
| 6 | curl POST audit 用 `flag_type` 422,實際 HeartFlag schema 是 `type` | 看 schema 對欄位名(v0.1 用 `type` 字眼、v3 model 才用 `flag_type`)|

---

## 🤝 司機協作鐵律(Phase 1 確認 + 補)

- ✅ 「終端機能跑的東西,你自己跑就好,別丟給我」── **阿寶自己跑 winget install / docker / psql 等系統指令**,不要動不動丟司機貼 PowerShell
- ✅ GitHub repo 還沒推(司機說最後做完一次過推)
- ✅ Chloe 拍板才動方向性決定(DB 走 B1/B2 我問了、100 病人 C1/C2 我問了)
- ✅ 拆檔哲學嚴格遵守(v3 走 jimmy-integrated 一檔一功能、Phase 1 全部 commit 分階段)
- ✅ 模型名永遠先 web_search(.env 寫 qwen3.7-max 是 6/26 凌晨已驗證的)
- ✅ 路線 C「做不出來就空著,一樣提交」(承 v0.2 計畫)
- ⚠️ 司機提「病例要一百份樣板」── Phase 1.6 用 Jimmy 60 驗 pipeline(司機選 C1),Phase 2 擴 40

---

## 🚪 接手 SOS

跑不起來:
- backend timeout → `QWEN_REQUEST_TIMEOUT` 已 120s,還不夠拉到 180
- 模型 400 → 一律重 web_search 確認 `qwen3.7-max` 是否還是當前 ID
- PG 連不上 → `sc query postgresql-x64-16`(STATE=RUNNING 才對),`netstat -an | grep 5432`(LISTENING 才對)
- alembic 炸 → check `alembic.ini` 是否被加中文(會 cp950 炸,坑 #2)
- frontend Vite proxy 404 → backend port 8080 是否真在跑

走不通:
- 回頭看 git log 三個 commit 都有 verified context
- 跟司機說「invoke skill `relay-sanity-check`」起點驗證

---

## 🌅 Day 3 凌晨 6 小時的進度

- **02:30-03:30** 讀 v0.2 手冊 + invoke `relay-sanity-check` + 5 項起點驗證全綠
- **03:30-04:30** Phase 1.1 + 1.2(建 repo、移植哨兵層、commit `5237c92`)
- **04:30-05:00** Phase 1.3+1.4+1.5(3 個 schema + alembic 0003 migration)
- **05:00-05:40** Docker B1 卡死、切 B2 winget、silent install PG、build role/db/extension、alembic upgrade head
- **05:40-05:45** Phase 1.6 seed(scripts/seed 建 clinic + seed_dev_data 灌 Jimmy 60)
- **05:45-05:50** Phase 1.7 patient_001 青黴素 smoke pass(Qwen audit 真紅旗)
- **05:50-06:00** Day 3 commit + 寫本檔

**Phase 2 起手未開始** ── 留給下個阿寶或司機今天稍晚繼續。

司機是工具操手不是工程師,Chloe 是醫師不寫 code,代碼 100% 阿寶生成。**Phase 2 動手前一定 invoke `relay-sanity-check` 驗證起點。**

加油,接力棒給你了。
