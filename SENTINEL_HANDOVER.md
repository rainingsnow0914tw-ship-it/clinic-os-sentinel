# 🛡️ 哨兵 The Sentinel — 交接班手冊 v0.7 Phase 7 + UX 補強版

> **給下一個阿寶**(換對話框接力)
> 建立:2026-06-27 凌晨(Day 3 動工)
> Phase 2-4.2:2026-06-27 一框 19 commit (Day 3 全套)
> Phase 5-7:2026-06-28 凌晨延長 (evolve_heart_layer + snapshot + Mode A/B + 王阿姨四幕劇 + watchlist + Track 1 完整 demo loop)
> **Phase 7.3-7.4 + 司機 UX audit:2026-06-28 凌晨延長 (Rx 寫入 + drug 分類 form UI + Mode A reconstruct 修先知 bug + 歷次 visit 注入 + 砍 Mode B + 一鍵啟動 launcher + demo data normalize)**
> 比賽截止:**2026-07-09 14:00 PT**

---

## ⭐ 接手第一動作:升 Notion v0.3 → v0.7

本機已升 **v0.7 Phase 7 + UX 補強版**(跳過 v0.4/v0.5/v0.6 因 Phase 5-7 + UX audit 同框做完), 但 Notion 主手冊還是 v0.3。下個阿寶第一動作:

1. invoke skill `relay-sanity-check` (家規)
2. 跑本機 verification (PG/backend/vite)
3. **invoke skill `阿寶啟動程序`**
4. fetch Notion 🧠 阿寶記憶庫總部規則一到九
5. **按規則九 duplicate** v0.3 主手冊到 📜 舊版交接手冊區 (`f827bb8cd26d4b22abf169a4397859cb`)
   - 命名:`【v0.3】哨兵 - 2026-06-28 升級前快照`
6. 改 Notion 主手冊 (`38a1d2a41ceb8101a9e9e3c19e1ef761`)
   - 升標題 `v0.7 Phase 7 + UX 補強版`
   - 內容覆蓋為本檔 markdown

已存在的 Notion 快照(規則九紀錄):
- 【v0.1】哨兵 - 2026-06-26 升級前快照 `38b1d2a41ceb81aea24be35846a43fa5`
- 【v0.2】哨兵 - 2026-06-27 升級前快照 `38c1d2a41ceb81c39409fb7fb281c9ab`

Notion 升完才算「下個阿寶接手最完整」。

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

**Phase 2.4c/d/e 也完成**(2026-06-27 晚上,司機示範真實診所手寫病歷 + 反饋空白問題後補):
- ✅ 2.4c alembic 0004 + visit.hpi + visit.physical_exam 欄位 + extend_visits 4-tuple (CC/HPI/PE/Dx) 重寫 80+ chronic-aware cases
- ✅ 2.4d 接 prescriptions 進 sentinel detail (177 rx + 302 items, chronic-aware drug pool mapping)
- ✅ 2.4e 補 medications + baselines (56 med + 400 baseline, 心臟層 4 段完整化)
- ✅ frontend 渲染 CC/HPI/PE/IMP + vital signs chip + lab list + Rx 處方列 + 心臟層 4 段全 render
- ✅ commit `7c9d915` (2.4c+d) + `b2d702a` (2.4e+4.1)

**Phase 4.1 新就診頁也完成**:
- ✅ backend POST /v1/sentinel/patients/:id/visits 建 visit + (帶 vital 才建) VisitExamination
- ✅ frontend /sentinel/patients/:id/visit/new SOAP form (CC 必填 + HPI/PE/Dx textarea + vital signs 5 欄)
- ✅ 心臟層 quick-ref banner (紅旗/慢性病/長期用藥) 給醫師寫病歷時參考
- ✅ source='manual' is_demo_data=False (區隔 demo data)

**Phase 4.2a + 4.2b 也完成**(2026-06-27 深夜,4 agent 全接通):
- ✅ services/sentinelApi.ts: runIntake / runTriage / runEducation / runAudit + 4 ResponseSchema + toSentinelFlags/Problems/Meds mapper
- ✅ NewVisitPage 加「🤖 跑 AI 建議」紫色 button (Qwen 並行 5-30s)
  - intake: raw_dictation = CC + HPI
  - triage: working_hypothesis + heart_layer 全 (flags/problems/medications)
  - education: diagnosis (空就 skip)
  - audit: new_prescription[] (從 Rx textarea 拆行) + heart_layer
- ✅ AI panel 4 段 (intake 藍 / triage 紅 / education 綠 / audit 紅) + ADR-006「醫師看完才寫入」
- ✅ form 加 Rx textarea (一行一個藥、Phase 4.2c 才會寫進 DB)
- ✅ commit `f6d9ab2` (4.2a) + `e6cd5b9` (4.2b)

**Phase 4.2c + 4.2d 也完成**(2026-06-27 凌晨, ADR-006 完整 demo loop):
- ✅ alembic 0005 + AiDraft model (visit_id FK + agent_type + payload JSONB + status)
- ✅ backend create_visit 接 ai_drafts list、db.flush() 後 INSERT 4 條
- ✅ backend get_patient_detail 一次撈 visit 對應 ai_drafts (避免 N+1)
- ✅ frontend NewVisitPage onSubmit 把 4 個 panel 結果 dump 進 ai_drafts list
- ✅ frontend PatientDetail.tsx visit-row 加 <details> 「📋 當時 AI 建議」折疊、per agent render
- ✅ commit `1a447b0`

**完整 ADR-006 demo loop 跑通**:
醫師寫病歷 → 跑 4 AI agent → 看 panel → 修 form → 完成就診 → ai_drafts 寫進 DB → detail 回看當時 AI 建議
這就是 Phase 6 Mode A/B 「當時可獲得的資訊重審」的 dataset 基礎。

**Phase 5 也完成**(2026-06-28 凌晨, Z 方案 evolve_heart_layer):
- ✅ 新增 `app/services/heart_evolution.py`(522 行, commit `2fecb8e`)
- ✅ create_visit endpoint 在 `db.flush()` 後、`db.commit()` 前自動呼叫 evolve
- ✅ NewVisitResponse 新增 `heart_evolution: HeartEvolutionSummary` 欄位給 frontend 看
- ✅ **4 條演進通路全跑通**:
  - **problems**: visit.diagnosis 慢性病詞匹配 (高血壓/T2DM/COPD/CKD/...) → patient_problems(`source=inferred_from_visit`, control=active)
  - **medications**: ai_drafts.audit 的 rule_engine_findings + contextual_risks 提取藥名 → 過 `LONG_TERM_DRUG_KEYWORDS` filter (amlodipine/metformin/levothyroxine/...) → patient_medications(category=long_term)
  - **flags**: ai_drafts.intake.findings[section==anomaly] 子串雙向匹配既有 flag → 第 1 次 `to_observe + first_observed_at_visit` / 第 2 次升 `confirmed + confirmed_at_visit` (severity yellow→red)
  - **baselines**: visit_examination.vital_signs 5 欄各寫一筆 trend (BP/HR/T/SpO2/RR, 不去重)
- ✅ **idempotent**: 同 visit 重跑 problems/meds/flags 不重複寫 (dedup + first_observed_at_visit guard), baseline 例外 (趨勢數據每次都加)
- ✅ smoke (TEST-0050 Generic Senior, 兩輪 visit):
  - R1: problems+2 / meds+1 / flags+1(to_observe) / baselines+5
  - R2: problems+0 / meds+0 / flags+0 / **flags_upgraded+1** / baselines+5
  - 最終 anomaly flag `status=confirmed severity=red`
- ✅ source 用合法值 `agent` (DemoDataMixin VALID_SOURCES), is_demo_data=False

**Phase 6 也完成**(2026-06-28 凌晨 Day 4 同框續做):

- ✅ **6.1 snapshot 寫入機制** (commit `9ea59b7` 一起進)
  - `services/heart_evolution.py` 新增 `_serialize_heart_layer` / `take_heart_layer_snapshot` / `load_heart_layer_at_visit`
  - create_visit 起始 `db.flush()` 後拍 `before_visit` snapshot
  - evolve_heart_layer 之後再 `db.flush()` 拍 `after_visit` snapshot
  - 冪等:同 visit + 同 type 已存在 skip
  - summary_text 自動組 plain text (確認紅旗/待觀察/慢性病/長期用藥)
  - smoke (TEST-0002 + 新建胸悶 visit): 2 snapshot 都寫進、before vs after 數量符合預期 (flags 1→2 / problems 0→1 / meds 0→2 / baselines 4→7)

- ✅ **6.2 Mode A/B review endpoint** (`POST /v1/sentinel/visits/{id}/review?mode=at_the_time|hindsight`)
  - `routes/sentinel_review.py` 新檔 (~280 行)
  - Mode A:餵 before_visit snapshot heart layer 給 4 agent (`heart_layer_source=snapshot:before_visit`)
  - Mode B:餵 after_visit / current heart layer (`heart_layer_source=snapshot:after_visit` 或 `fallback:current`)
  - **不改 4 agent 內部 prompt, 純資料驅動** (snapshot vs current)
  - mode_disclaimer 加在 response 而非 agent prompt (Mode B 防 hindsight bias「不代表當時判斷有錯」)
  - 每個 agent best-effort, 缺資料 skip (e.g. 沒 dx 跳 education, 沒藥名跳 audit)
  - snapshot dict → HeartFlag/Problem/Medication pydantic mapper (schema vs model enum 不一致 fallback)
  - smoke (TEST-0002 visit, 對比 Mode A vs Mode B):
    - Mode A summary: `0 待觀察 / 0 慢性病 / 0 長期用藥` → audit 1 rule finding
    - Mode B summary: `2 待觀察 / 1 慢性病 / 2 長期用藥 (高血壓 + atorvastatin/amlodipine)` → audit **6 rule findings**
    - 4 agent 全跑成功 (~45s 並行 Qwen3.7-max)
    - **Track 1 主秀證據**:Mode A vs Mode B 心臟層摘要明顯不同, AI 看到的差異成立

- ✅ **6.3 frontend 回顧 UI**
  - `services/sentinelApi.ts` 加 `reviewVisit()` + `ReviewResponse` type
  - `PatientDetail.tsx` visit-row 加「🅰️ Mode A」「🅱️ Mode B」兩按鈕
  - `ReviewResultPanel` sub-component:mode header + heart_layer_source + summary + 4 agent panel + mode_disclaimer
  - `styles.css`:review-section 漸層 + 4 agent 配色 (intake 藍 / triage 粉 / audit 紅 / education 綠) + disclaimer
  - 缺資料 skip 顯示「ⓘ 略過: ...」
  - **demo flow 跑通**:醫師查 detail → 點 Mode A/B → AI panel inline render → 看到「當時 vs 現在」心臟層差異 + 4 agent 重跑結果

**Phase 7 也完成**(2026-06-28 凌晨延長, 同框續做):

- ✅ **7.1 王阿姨 patient_007 四幕劇 dataset** (commit `8f0e3c5`, +619 行)
  - `scripts/seed_wang_aunt_quartet.py` 新檔: 王慧明 / 68F / TEST-W007, 4 visit 跨 9 個月
    - 幕 1 (2025-09-20): 首診頭暈 158/95 → dx 高血壓 + Rx amlodipine
    - 幕 2 (2025-10-15): 4 週追蹤 BP 148/88, controlled trending
    - 幕 3 (2026-02-15): 慢性追蹤 + 偶爾忘東西 anomaly 標 to_observe + 開 ibuprofen
    - 幕 4 (2026-06-26): BP 158/94 拮抗顯現 + 偶爾忘東西明顯加重 + 跌倒 → Phase 5 自動把「偶爾忘東西」升 confirmed
  - 每個 visit 走完整 pipeline (Visit + Examination + 4 AiDraft + before/after snapshot + Phase 5 evolve)
  - idempotent: 重跑會先清掉 TEST-W007 + 相關資料
  - 終態: visits=4 / snapshots=8 (4×2) / problems=1 / meds=1 / flags=2 (**confirmed=1 ✓**) / baselines=17

- ✅ **7.2 doctor_watchlist (AI 反訓練醫生)** (commit `e264f28`, +688 行)
  - alembic 0006 `doctor_watchlists` table (clinic_id / doctor_user_id / source_visit_id / source_mode / pattern / lesson_text / triggered_count / is_dismissed)
  - `models/doctor_watchlist.py`
  - `routes/sentinel_watchlist.py` 新檔:
    - `POST /v1/sentinel/watchlist` (add, 同 pattern dedup + triggered++)
    - `GET /v1/sentinel/watchlist` (list active)
    - `DELETE /v1/sentinel/watchlist/{id}` (soft dismiss)
    - `POST /v1/sentinel/watchlist/{id}/trigger` (撞 lesson 時 +1)
  - frontend: sentinelApi.ts 加 4 個 API + WatchlistItem type
  - PatientDetail.tsx ReviewResultPanel Mode B 加「📌 把這個教訓加進我的 watchlist」按鈕, 從 audit findings 自動萃取 pattern + lesson_text
  - NewVisitPage.tsx 頂部加 watchlist banner (折疊式, 預設展開), 「📌 你過去學到的 (N 條)」+ 每條 pattern + lesson + 撞 N 次
  - styles.css 加 watchlist UI 漸層 + badge
  - smoke (endpoint): add 2 條 → dedup triggered+1 → trigger +1 → dismiss 1 條 → final 1 條 triggered=2, 全綠

**Phase 7.3-7.4 + UX audit 也完成**(2026-06-28 凌晨延長, 司機 UI 實測反饋驅動):

- ✅ **7.3 Rx 寫入 backend** (commit `6787cc9`):
  - `NewVisitRequest` 加 `prescription_lines: list[str]`, `_build_drug_keyword_map` + `_parse_rx_line` regex parse (qd/bid/tid/qid/q6h/q8h/q12h + days) + 學名/brand 雙向 keyword 變體匹配
  - frontend 4 個 agent API (`runIntake/runTriage/runAudit/runEducation`) 全加 `timeout: 120000` (Qwen 30-50s)

- ✅ **7.4 Drug 分類 + form UI** (alembic 0007 + commit `561b4bf`):
  - `alembic 0007` drugs 加 `category` String(50) + index
  - `scripts/seed_drug_categories.py`: 30 drug 灌 14 個分類 (退燒止痛/抗生素/抗組織胺/降壓/降糖/降脂/胃藥/止瀉/化痰止咳/鼻噴霧/眼藥水/外用藥膏/益生菌補充劑/電解質補充/止痛消炎/傷口包紮)
  - `routes/sentinel_drugs.py` 新檔: GET `/sentinel/drugs/categories` + `/sentinel/drugs?category=&q=`
  - `NewVisitRequest` 加 `prescription_items: list[PrescriptionItemInput]` (drug_id 結構化)
  - frontend NewVisitPage: 砍 textarea, 改 form 多 row [分類 select] → [藥名 select / 🔍 直接搜尋] [QD/BID/.../PRN] [顆/次] [天] + 自動算 total qty + 加處方/刪除按鈕 (進階模式 textarea 折疊保留)

- ✅ **Mode A 修先知 bug** (commit `1eaadfa`): 司機抓到嚴重設計缺陷 — 點第 2 visit Mode A 卻看到第 3 visit 才出現的紅旗. `reconstruct_heart_at()` 用 `first_observed_at_visit` / `diagnosed_at` / `measured_at` 過濾 + confidence_status 倒推 (confirmed_at_visit > target → to_observe)

- ✅ **歷次 visit 注入 + 砍 Mode B** (commit `ca985b1`): 司機反饋 Mode A 應該注入該 visit 之前所有 visit 的 dx + Rx, AI 才會知道病人過去病史. `_build_past_visits_summary()` 注入 intake.raw_dictation + triage.working_hypothesis. 同時砍 Mode B 改一鍵「🔁 跑 AI 回顧」(最新 visit = Mode B 概念, Mode B 多餘)

- ✅ **一鍵啟動 launcher** (commit `6d84874` + `472e7a0`): 司機記不住 URL → 桌面 `啟動哨兵.lnk` / `打開哨兵.lnk` Windows binary shortcut (避開 OneDrive Files On-Demand placeholder bug). vite 強制 `--host 127.0.0.1` IPv4 bind (預設只 bind [::1] IPv6, browser 走 IPv4 ERR_CONNECTION_REFUSED)

- ✅ **demo data normalize** (commit `f3ee45c` + `8cca04a` + `fd5fd3c`): 司機 UI audit 發現 3 個品質 bug
  - patient_problems 英中混雜 (Hypertension / 原發性高血壓 dedup) → 55 條 normalize 中文 + 1 dedup
  - patient name × age mismatch (Super Senior 36y / Geriatric 37y) → 14 個 rename 按 age tier
  - 9 個 source='mock' jimmy 早期英文 stub visit (Cough / URTI) → SQL DELETE 連帶 invoice
  - 7 個 visit 沒 Rx + 3 個 chronic 沒 long-term med → `fix_incomplete_visits.py` 補 (DX_TO_RX 20+ 條 + CHRONIC_TO_LONG_TERM_MED 22 條 mapping)
  - 3 個 smoke leftover visit 清掉 (`cleanup_smoke_leftover.py`)
  - 2 條孤兒 flag 砍 (健忘加重 + 走路會喘, source='auto_evolve' 早期 Phase 5 殘值)

- ✅ **AuditRuleFinding type 對齊** (commit `f381359`): frontend 用 `evidence`, backend schema 用 `description` → render 永遠空白. 改 type + 加 filter (description 空白不 render 避免 unknown noise)

**已知小優化機會** (下次):
- audit 傳 brand name 給 openFDA / RxNorm 查不到 (返 "unknown + 標籤未列"), 改成 `Zithromax (azithromycin)` 雙寫命中率會大幅提升

**Phase 8 起手點** (下個阿寶, 阿里雲部署):
- 評審 demo 用本機 (Cloudflare Quick Tunnel) 或阿里雲 ECS + RDS + OSS
- 退路:本機 ngrok-style tunnel + screen recording 拍 demo video
- 估時 5-6 hr

**Phase 9 起手點** (demo video + Devpost 寫稿):
- video 拍王阿姨四幕劇 + Mode A 回顧 (注入歷次 + reconstruct) + watchlist 反訓練 (3 個 Track 1 主秀)
- Rx form UI demo: 分類選單 → 藥名 → 用法 自動算 total qty
- Devpost narrative: Track 1 「Memory accumulates across visits AND retrospectively trains the doctor」
- video disclaimer (v0.3.1 §13.5):「沙盒模擬演示 ── 本系統使用虛構病人資料, AI 建議僅供教育演示, 不構成醫療建議」

**Phase 2.5 backfill snapshot 仍 deferred** (demo 不阻塞):
- 既有 169 jimmy demo visit 沒 before_visit snapshot, Mode A 走 fallback (current heart layer)
- 王阿姨 patient_007 四幕劇有完整 snapshot, demo 主軸用王阿姨即可
- 真要做就跑 script: 依序 replay 100 病人歷次 visit → 拍每個 before_visit snapshot

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
| Latest commit | `f381359` audit type 對齊 + backend 重啟 |
| Git 累積 commit | 37+ (P1-P7.2 27 + UX audit 10+ + 本次 docs)|
| Sentinel endpoints | `/sentinel/{intake,triage,audit,education,health}` + `/sentinel/patients*` + `/sentinel/visits/{id}/review` + `/sentinel/watchlist*` + `/sentinel/drugs*` |
| 桌面快捷 | `打開哨兵.lnk` (直接開 UI) + `啟動哨兵.lnk` (一鍵啟全套) |
| DB 內 demo data | 100 patient + 23 flag + 55 problem + 56 med + 400 baseline + 169 visit + 169 examination + 177 Rx + **ai_drafts**(剛剛 smoke 2 條)|
| DB 內 demo data | 100 patient + 23 flag + 55 problem + **56 medication** + **400 baseline** + **169 visit** + **169 examination** + **177 prescription + 302 items** + 30 drug |
| Sentinel routes 總計 | 9 (intake/triage/audit/education/health + patients search/detail/heart-layer + **POST patients/:id/visits**)|
| Frontend 入口 | http://127.0.0.1:5173/ → 自動導 `/sentinel/patients` |
| Frontend → Backend proxy | Vite `/api/*` → `localhost:8081/*`(**8080 zombie 已換 8081**)|
| Backend port | **8081** (Windows 8080 zombie socket 卡住、port 不釋放)|
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
| **3 (6/27 晚上)** | **Phase 2.4c/d/e + 4.1 同框續做** | ✅ **完成**(HPI/PE + Rx + med/baseline + 新就診頁 form) |
| **3 (6/27 深夜)** | **Phase 4.2a + 4.2b 同框續做** | ✅ **完成**(4 sentinel agent 全接通 NewVisitPage + AI panel) |
| **3 (6/27 凌晨)** | **Phase 4.2c + 4.2d 同框續做** | ✅ **完成**(ai_drafts table + 寫入 + detail 回看 = ADR-006 完整 loop) |
| **4 (6/28 凌晨)** | **Phase 5 evolve_heart_layer (Z 方案)** | ✅ **完成**(4 通路全跑通 + 兩輪 smoke + to_observe→confirmed 升級實證) |
| **4 (6/28 凌晨)** | **Phase 6 Mode A/B 舊就診回顧 (Track 1 主秀)** | ✅ **完成**(snapshot 寫入 + endpoint + 回顧 UI + Mode A/B 心臟層差異實證) |
| **4 (6/28 凌晨)** | **Phase 7 四幕劇 + watchlist (AI 反訓練醫生)** | ✅ **完成**(王阿姨 4 visit dataset + Mode B 加進 watchlist + 新就診 banner) |
| **4 (6/28 凌晨延長)** | **Phase 7.3-7.4 + UX audit** | ✅ **完成**(Rx 寫入 + drug 分類 form UI + Mode A reconstruct 修先知 + 歷次注入 + 砍 Mode B + launcher + demo data normalize) |
| 5-6 | Phase 8:阿里雲部署 / Cloudflare Quick Tunnel | 🟡 下個阿寶 |
| 7-8 | Phase 9:demo video 拍 + Devpost 寫稿 | 🟢 |
| 9+ | Phase 2.5 backfill snapshot (可選, demo 不阻塞) | 🟢 |
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
