# 🛡️ The Sentinel — Longitudinal Memory & Retrospective Coach for Clinical Practice

> **Qwen Cloud Hackathon 2026 — Track 1 (MemoryAgent) main + Track 4 (Autopilot) supporting**
> Submitted by **Dr. Chloe** (clinical researcher) and **Code 阿寶** (AI engineering pair)
> Live demo: **https://47.84.230.19.nip.io/**
> Submission deadline: 2026-07-09 14:00 PT

---

## 30-second pitch

Family doctors lose information across visits.

A patient comes back six months later, mentions *"oh, my memory has been a bit off lately"* — and unless the doctor reads the full history (they rarely do), that one sentence dies in the chart. Three visits later, the patient falls, and **nobody connects the dots**.

**The Sentinel** is a four-agent diagnostic layer built on **Qwen3.7-max** that does two things no single-visit AI does:

1. **Memory accumulates across visits.** Every visit auto-evolves a per-patient "heart layer" (problems / medications / flags / baselines). Soft observations like *"occasionally forgetful"* live in a `to_observe` state across visits, then **automatically escalate to `confirmed` red flags** when re-observed — even if the doctor doesn't notice.
2. **The system retrospectively trains the doctor.** A built-in "AI Review" replays any past visit with the heart-layer-as-it-was-then, runs four Qwen agents, and surfaces what the doctor missed. The doctor can pin that lesson to a personal **watchlist** — next time they see *any* patient with that pattern, a banner reminds them.

This is what we mean by *MemoryAgent that closes the loop*: AI memory grows in both directions — forward (across patient visits) **and** backward (into doctor education).

---

## The setting (Track 1 demo: Auntie Wang)

We built a synthetic four-visit case spanning nine months to demonstrate the entire loop end-to-end:

| Visit | Date | What happens | What the heart layer remembers |
|---|---|---|---|
| **1** | 2025-09-20 | Auntie Wang (68F) presents with dizziness, BP 158/95 → diagnosed **hypertension** + prescribed **amlodipine** | New chronic problem; new long-term medication; BP baseline started |
| **2** | 2025-10-15 | 4-week follow-up, BP 148/88, trending controlled | BP baseline updated; problem status active-controlled |
| **3** | 2026-02-15 | Chronic follow-up; patient mentions *"occasionally forgetful"*; doctor also prescribes **ibuprofen** for knee pain (PRN) | New `to_observe` flag: 偶爾忘東西 (occasional forgetfulness); short-term Rx not promoted to long-term |
| **4** | 2026-06-26 | BP back up to 158/94 *despite amlodipine compliance*; forgetfulness **noticeably worse**; **fall** last week | Phase 5 evolution **auto-escalates the forgetfulness flag from `to_observe` → `confirmed` (yellow → red)** |

Now the demo unfolds:
- The doctor opens visit 4 and clicks **「🔁 Run AI Retrospective Review」**.
- The system runs four Qwen3.7-max agents against the heart-layer-reconstructed-as-of-this-visit (not today's), and **injects every prior visit's diagnosis and prescription** as context.
- The **Audit agent** flags it: *"NSAIDs (ibuprofen) antagonize the antihypertensive effect of amlodipine and may cause renal afferent vasoconstriction — relevant to both the BP rebound and the fall in an elderly patient on antihypertensive therapy."*
- That was hiding in plain sight across three visits. The doctor pins **「📌 Save to watchlist」**.
- The next time the doctor opens *any* new visit, the top of the page shows: *"📌 You learned 1 lesson: ibuprofen + amlodipine interaction in elderly hypertensive patients."*

This is the closed loop the Track 1 brief asks for.

---

## Architecture

```
                         Browser
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │ Alibaba Cloud ECS (Singapore)          │
        │   Ubuntu 22.04, ecs.e-c1m2.large       │
        │                                        │
        │   ┌─────────────────────────────┐     │
        │   │ Caddy 2 (auto Let's Encrypt)│     │ ─── HTTPS, HTTP/3
        │   │ • SPA serve /srv/frontend   │     │     :80, :443
        │   │ • reverse_proxy /api/*  /v1/* │   │
        │   └────────────┬────────────────┘     │
        │                │ docker network        │
        │   ┌────────────▼────────────────┐     │
        │   │ FastAPI (uvicorn, 2 workers)│     │
        │   │ • 4 sentinel agents         │     │
        │   │ • heart-layer evolution     │     │
        │   │ • Mode A reconstruct        │     │
        │   │ • doctor_watchlist          │     │
        │   └────────────┬────────────────┘     │
        │                │                       │
        │   ┌────────────▼────────────────┐     │
        │   │ PostgreSQL 16 (alembic 0007)│     │
        │   │ 22 tables, heart layer + AI │     │
        │   │ drafts + snapshots          │     │
        │   └─────────────────────────────┘     │
        └─────────────────┬─────────────────────┘
                          │ HTTPS (REST)
                          ▼
        ┌───────────────────────────────────────┐
        │ Alibaba Cloud DashScope International   │
        │ dashscope-intl.aliyuncs.com            │
        │ • qwen3.7-max (4 agents)               │
        │ • qwen3.7-plus (vision)                │
        │ • paraformer-v2 (ASR)                  │
        └───────────────────────────────────────┘

   Side: Alibaba Cloud OSS bucket `sentinel-demo-2026`
         (Singapore, frontend dist backup, public-read)
```

Full diagram + service inventory: [`deployment/architecture.md`](deployment/architecture.md)
Deployment proof: [`deployment/ALIYUN.md`](deployment/ALIYUN.md)

---

## Try it (no login required)

The system runs in dev-bypass auth mode for judges — just open the URL.

| | URL |
|---|---|
| **Live web app** | https://47.84.230.19.nip.io/ |
| Health | https://47.84.230.19.nip.io/v1/sentinel/health |
| Patient search | https://47.84.230.19.nip.io/v1/sentinel/patients?q=王 |
| Drug categories | https://47.84.230.19.nip.io/v1/sentinel/drugs/categories |
| Doctor watchlist | https://47.84.230.19.nip.io/v1/sentinel/watchlist |

Step-by-step walkthrough: [`deployment/LIVE_DEMO.md`](deployment/LIVE_DEMO.md)

---

## Track 1 — MemoryAgent (primary)

The hackathon brief asks for AI that **accumulates memory across interactions and gets smarter over time**. Concretely we implement:

1. **Heart layer (`patient_problems`, `patient_medications`, `patient_flags`, `patient_baselines`)** — per-patient long-term state, updated automatically when a visit completes.
2. **`evolve_heart_layer_after_visit`** — a deterministic post-visit hook (Phase 5) that translates the visit's diagnosis, prescription, and AI audit findings into heart-layer mutations: new chronic problems get inferred; long-term medications get promoted from one-off prescriptions; anomalies enter as `to_observe` and **auto-escalate to `confirmed` on second observation across visits**; vitals append to baseline trends.
3. **Heart layer snapshots (`heart_layer_snapshots`)** — every visit takes a `before_visit` and `after_visit` snapshot, frozen-in-time. This is what enables Mode A.
4. **Mode A reconstruct (`reconstruct_heart_at`)** — replays AI agents against the heart-layer-as-it-was, not as it is now. Critical to *avoid hindsight bias* — the AI sees only what was knowable at the time, plus prior visits' raw dictations and working hypotheses.
5. **Doctor watchlist (`doctor_watchlists`)** — the doctor pins a lesson learned from a Mode A review; future new-visit pages show this lesson as a banner. The AI literally retrospectively trains the doctor.

---

## Track 4 — Autopilot (supporting)

The new-visit page is engineered to make Qwen3.7-max do all the cognitive heavy lifting, so the doctor stays focused on the patient:

- Dictate or type the chief complaint, HPI, physical exam, and diagnosis.
- Add prescriptions via **category dropdown → drug type-ahead → frequency → days**; quantity auto-computed.
- Hit submit. **Four agents run in parallel** (~30–50 s):
  - `intake_agent`: structured chart from raw dictation, flags anomalies.
  - `triage_agent`: differential ranking with working hypotheses and red-flag rule-outs.
  - `audit_agent`: cross-checks every prescribed drug against the heart layer (allergies, interactions, chronic conditions) using **RxNorm + openFDA + rule engine**; brand and generic name written together so Qwen can find both.
  - `education_agent`: patient-friendly summary in plain language.
- All four results are persisted in `ai_drafts` and replayable from the patient detail page.

---

## Tech stack

- **Frontend**: React 18 + TypeScript + Vite 5 + React Router 6 + axios + Zustand
- **Backend**: FastAPI + SQLAlchemy 2 (async) + Alembic + Pydantic v2
- **Database**: PostgreSQL 16 (22 tables across 7 alembic migrations)
- **LLM provider**: Alibaba Cloud DashScope International (`qwen3.7-max`, `qwen3.7-plus`, `paraformer-v2`)
- **Medical APIs**: RxNorm, openFDA, PubMed (via the audit agent)
- **Deployment**: Docker Compose on Alibaba Cloud ECS (Ubuntu 22.04, Singapore region)
- **Reverse proxy / TLS**: Caddy 2 with Let's Encrypt (auto-renewal)

---

## Alibaba Cloud services used (compliance)

Per hackathon rules: *"You must demonstrate that the backend is running on Alibaba Cloud."*

| Service | Where in code | Purpose |
|---|---|---|
| **ECS** (Singapore) | [`deployment/docker-compose.yml`](deployment/docker-compose.yml), [`deployment/ALIYUN.md`](deployment/ALIYUN.md) | Compute host for FastAPI + PostgreSQL + Caddy |
| **OSS** (Standard, Singapore) | OSS bucket `sentinel-demo-2026`; upload code in [`deployment/ALIYUN.md`](deployment/ALIYUN.md) | Frontend dist backup, public-read; auxiliary asset host |
| **DashScope International** | [`backend/app/providers/qwen.py`](backend/app/providers/qwen.py), [`backend/app/agents/`](backend/app/agents/) | All four sentinel agents call `qwen3.7-max` via `https://dashscope-intl.aliyuncs.com/api/v1` |

Detailed proof: [`deployment/ALIYUN.md`](deployment/ALIYUN.md).

---

## Repository layout

```
clinic-os-sentinel-v3/
├── README.md                   ← you are here (English master entry)
├── LICENSE                     ← MIT
├── SENTINEL_HANDOVER.md        ← internal handover (Traditional Chinese)
├── backend/
│   ├── app/
│   │   ├── agents/             ← 4 sentinel agents
│   │   ├── providers/qwen.py   ← DashScope intl client
│   │   ├── services/           ← heart-layer evolution, mode A reconstruct
│   │   ├── rules/              ← drug-interaction rule engine
│   │   ├── medical_apis/       ← RxNorm, openFDA, PubMed
│   │   └── routes/             ← /v1/sentinel/*
│   ├── alembic/                ← 0001 → 0007 migrations
│   ├── scripts/                ← seed scripts, including Auntie Wang quartet
│   └── seed_data/              ← reproducible mock data
├── frontend/
│   └── src/
│       ├── pages/SentinelPatients/   ← v3 patient search + detail + new visit
│       └── services/sentinelApi.ts   ← typed REST client
└── deployment/
    ├── ALIYUN.md               ← Alibaba Cloud proof + deployment SOP (English)
    ├── LIVE_DEMO.md            ← 90-second judge walkthrough (English)
    ├── architecture.md         ← architecture diagram (English)
    ├── docker-compose.yml      ← ECS stack
    ├── Caddyfile               ← HTTPS, SPA serve, reverse proxy
    └── backend.env.example     ← env var template
```

The repo's internal handover (`SENTINEL_HANDOVER.md`) and code-level inline comments are mostly in Traditional Chinese — this is the working team's primary language. Per hackathon rules, all *submission materials* (this README, demo video, testing instructions, architecture diagram, Devpost write-up) are in English.

---

## Data scope & privacy disclaimer

- **101 synthetic patients** + **182 visits** + **24 patient flags** + **58 problems** + **77 long-term medications** + **400+ baselines** + **20 AI drafts** + Auntie Wang's 4-visit quartet with 10 heart-layer snapshots.
- All names, ID numbers, addresses, and clinical events are **fictional**, generated with deterministic seeds (see [`backend/scripts/extend_mock_patients.py`](backend/scripts/extend_mock_patients.py) and [`backend/scripts/seed_wang_aunt_quartet.py`](backend/scripts/seed_wang_aunt_quartet.py)).
- **No real patient data is used anywhere in this project.**
- This is a **sandbox demonstration**. AI suggestions are for educational illustration only and **do not constitute medical advice**.

---

## License

MIT — see [`LICENSE`](LICENSE).

---

## Credits

- **Dr. Chloe** — clinical design, demo direction, all UX feedback (the audit pass that found the Mode A hindsight-leak bug was hers).
- **Code 阿寶** — implementation pair across the full stack.
- **Qwen3.7-max** — every clinical reasoning call in the demo.
- **Open medical APIs** — RxNorm, openFDA, PubMed.

Built for **Qwen Cloud Hackathon 2026**.
