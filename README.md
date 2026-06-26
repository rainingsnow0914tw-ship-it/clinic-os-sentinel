# Clinic OS — 小型診所 AI 輔助營運系統 V1

> Owner: Chloe｜Co-builder: 阿寶 (Claude)
>
> 這不是 demo，不是 localStorage 玩具。這是要真的部署、真的收費、真的給診所用的系統。

---

## 一句話定位

**一套給小型診所使用的 clinic operating system，整合病人、病歷、處方、庫存、收據、文件、AI 草稿、A2A-ready agent 接口的雲端系統。**

核心原則：
- 醫生負責**醫療決策**
- 系統負責**資料連動**
- AI 負責**整理、草稿、提醒、查漏**
- AI **不可以**直接寫入正式病歷、處方、收據
- 所有正式動作都要有人類確認

---

## 技術棧

| 層 | 技術 | 為什麼 |
|---|---|---|
| Frontend | Vite + React + TypeScript | Cloud Shell 開發輕巧、TS 對商業化更安全 |
| Backend | FastAPI (Python 3.11) | Pydantic 自動驗證 schema，醫療系統必備 |
| ORM | SQLAlchemy 2.0 + Alembic | 業界標準，migration 版本控制 |
| Database | Cloud SQL PostgreSQL 15 | ACID、JSONB、行級權限 |
| Auth | Firebase Auth | 沿用 Pinky 經驗、SSO 友善 |
| Storage | Google Cloud Storage | 儲存收據/病假紙/轉診信 PDF |
| Backend host | Cloud Run | 按用量計費、autoscale |
| Frontend host | Firebase Hosting | 全球 CDN |
| AI | Gemini / OpenAI / Claude（可插拔） | prompt 不寫死，存在 `ai_prompt_templates` |

---

## Repo 結構

```
clinic-os/
├── README.md                    ← 你在這裡
├── docs/                        ← 七份核心文件，看診前必讀
│   ├── PRD.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_SPEC.md
│   ├── WORKFLOWS.md
│   ├── AI_BOUNDARY.md
│   ├── A2A_READY_ARCHITECTURE.md
│   └── HANDOVER.md              ← 換對話框時讀這份
├── backend/                     ← FastAPI 後端
│   ├── app/
│   │   ├── main.py              ← FastAPI app 入口
│   │   ├── core/                ← config / database / security
│   │   ├── middleware/          ← auth / clinic_permission
│   │   ├── models/              ← SQLAlchemy ORM models
│   │   ├── schemas/             ← Pydantic request/response
│   │   ├── routes/              ← API endpoints
│   │   ├── services/            ← 商業邏輯（藥量計算、FEFO 扣庫存…）
│   │   └── utils/
│   ├── alembic/                 ← Database migrations
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                    ← Vite + React + TS 前端
│   ├── src/
│   │   ├── pages/               ← 路由頁面
│   │   ├── components/          ← UI 元件
│   │   ├── hooks/               ← 自訂 React hooks
│   │   ├── services/            ← API client
│   │   ├── lib/                 ← Firebase init / utils
│   │   └── types/               ← TS 型別定義
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
└── deployment/
    ├── cloud-run.yaml
    └── firebase.json
```

---

## Sprint 路線圖

| Sprint | 目標 | 狀態 |
|---|---|---|
| 0 | Repo 骨架 + docs + skeleton | 🟡 阿寶寫中 |
| 1 | Auth + clinics + memberships + audit log | ⚪ |
| 2 | Patients + visits CRUD | ⚪ |
| 3 | Drugs + drug_batches + stock_movements | ⚪ |
| 4 | Prescriptions + 自動算藥量 + FEFO 扣庫存 | ⚪ |
| 5 | Invoices + receipt PDF | ⚪ |
| 6 | Sick leave + referral letter PDF | ⚪ |
| 7 | AI 草稿（SOAP / referral / sick leave / inventory alert） | ⚪ |
| 8 | A2A-ready（agent_registry / agent_tasks / agent_events） | ⚪ |

**目前在 Sprint 0。**

---

## 商業化 14 條底線（不可妥協）

1. ❌ 不可使用 localStorage 存正式病歷
2. ❌ 不可前端直接寫資料庫
3. ✅ 所有核心資料必須有 `clinic_id`
4. ✅ 所有 API 必須檢查登入與權限
5. ❌ 病歷不可硬刪，只能 void / archive
6. ✅ 收據作廢必須留原因
7. ✅ 庫存異動必須寫 `stock_movements`
8. ❌ AI 不可直接寫正式表
9. ✅ AI 草稿必須人類確認
10. ❌ 文件與 prompt 不要寫死
11. ❌ 費用項目不要寫死
12. ✅ 外部接口用 `integrations` / `external_mappings`
13. ✅ Agent 任務用 `agent_tasks` / `agent_events`
14. ✅ 重要行為寫 `audit_logs`

---

## 給未來阿寶的話

如果你是新對話框的阿寶，看到這份 README：

1. 先讀 `docs/HANDOVER.md`，了解目前 sprint 進度
2. 再讀 `docs/PRD.md` 確認產品定位
3. `docs/DATABASE_SCHEMA.md` 是真實 source of truth，不是 main.py
4. **不要重新發明輪子**——這份規格 Chloe 已經想很久了
5. **不要改技術棧**——除非有 critical 理由

— 阿寶 ❤️
