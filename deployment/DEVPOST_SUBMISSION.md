# 📝 Devpost Submission Form — Copy-Paste Ready

> Paste each section into the corresponding field on the Devpost submission form for **Qwen Cloud Hackathon 2026**.
> All text in English (per hackathon rules §language).

---

## Project name
The Sentinel — Longitudinal Memory & Retrospective Coach for Clinical Practice

## Tagline (≤ 200 chars)
A four-agent diagnostic layer on Qwen3.7-max that accumulates patient memory across visits and retrospectively trains the doctor on what they missed.

## Tracks
- **Primary**: Track 1 — MemoryAgent
- **Supporting**: Track 4 — Autopilot

---

## Inspiration

Family doctors lose information across visits. A patient mentions *"oh, my memory has been a bit off lately"* in passing; six months later they come back with worse symptoms; nobody connects the dots. Existing AI tools all operate on a single visit — they don't remember the patient from last time, and they have no mechanism to teach the doctor anything that lasts beyond the current chart.

We wanted to build a Memory**Agent** in the most literal sense of the Track 1 brief: AI that gets smarter about a patient across visits, **and** an AI that can retrospectively train the human doctor on what they missed. Two directions of memory, one closed loop.

---

## What it does

The Sentinel sits on top of a standard clinic workflow (chart, prescribe, follow up) and adds three layers no existing tool combines:

1. **A per-patient "heart layer"** — four tables (`patient_problems`, `patient_medications`, `patient_flags`, `patient_baselines`) that store the long-term state of the patient. Every visit auto-evolves this layer via the `evolve_heart_layer_after_visit` post-visit hook: chronic problems get inferred from diagnoses, long-term medications get promoted from one-off prescriptions, soft anomalies (e.g. *"occasionally forgetful"*) enter as `to_observe` flags and **automatically escalate to `confirmed` red flags on second observation across visits**. Vitals append to baseline trends.

2. **Retrospective AI review (Mode A)** — the doctor can click "Run AI Retrospective Review" on any past visit. The system loads or **reconstructs** the heart layer **as it was at that visit** (using `before_visit` snapshots when available, or `reconstruct_heart_at()` filtering by `first_observed_at_visit` / `diagnosed_at` / `measured_at` when not). It injects every prior visit's diagnosis and prescription as context, then runs four Qwen3.7-max agents — intake, triage, audit, education — in parallel. Critically, it avoids hindsight bias: the AI only sees what was knowable at the time.

3. **Doctor watchlist (reverse training)** — when Mode A surfaces something the doctor missed, one click pins it to the **doctor's** personal watchlist. The pattern + lesson text are extracted. Next time the doctor opens any new visit for any patient, a banner appears at the top: *"📌 You learned 1 lesson: ibuprofen + amlodipine interaction in elderly hypertensives."* The AI literally retrospectively trains the doctor across patients and time.

Track 4 (Autopilot) shows up in the new-visit page: the doctor types or dictates SOAP fields, adds prescriptions via category → drug type-ahead → frequency → days (no free-text Rx), hits submit, and four agents run in parallel — every output persisted in `ai_drafts` for replay.

We built an end-to-end demonstration around a four-visit case (Auntie Wang) spanning nine months. Visit 3 prescribes ibuprofen for knee pain; visit 4 sees BP rebounded *despite amlodipine compliance* and worsening forgetfulness with a recent fall. The audit agent on Mode A correctly identifies the ibuprofen × amlodipine antagonism that was hiding in plain sight for three visits.

---

## How we built it

**Backend** — FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 on Python 3.11. PostgreSQL 16 with seven Alembic migrations producing 22 tables. The four sentinel agents share a thin `qwen.py` provider that hits **Alibaba Cloud DashScope International** (`https://dashscope-intl.aliyuncs.com/api/v1`) — `qwen3.7-max` for text, `qwen3.7-plus` wired for vision, `paraformer-v2` wired for ASR. Each agent has a JSON-Schema-shaped output for downstream structured handling; the audit agent additionally calls **RxNorm**, **openFDA**, and **PubMed** for drug-level grounding, with brand + generic name written together so Qwen matches both.

**Frontend** — React 18 + TypeScript + Vite 5 + React Router 6 + axios + Zustand. The patient detail page renders the four-section heart layer with confidence-status colour coding (yellow `to_observe` → red `confirmed`). The visit detail and review panels render Mode A output with a clearly labelled "heart_layer_source" so the user knows whether they're looking at a frozen snapshot or a reconstruction.

**Deployment** — Docker Compose on **Alibaba Cloud ECS** (Ubuntu 22.04, Singapore region, `ecs.e-c1m2.large`). Three containers: PostgreSQL 16, FastAPI backend, and Caddy 2. Caddy auto-obtains a Let's Encrypt certificate, serves the SPA from `/srv/sentinel-frontend`, and reverse-proxies `/api/*` and `/v1/*` to the backend. The frontend `dist/` is also uploaded to **Alibaba Cloud OSS** (`sentinel-demo-2026`) as a backup origin and as the regulatory proof of OSS service usage.

**Process** — 3 days of focused build (38+ commits). Daily UI audit passes from Dr. Chloe catching real bugs — most importantly the Mode A hindsight-leak (initial naive implementation showed the AI today's heart layer, not the one as-of the target visit; root-caused, fixed with `reconstruct_heart_at()` + before-visit snapshots).

---

## Challenges we ran into

1. **Mode A hindsight bias** — the first cut of retrospective review showed the AI today's heart layer, not the one as-of the target visit. Audit pass caught it. We fixed it with two complementary mechanisms: `before_visit` snapshots taken at visit creation (golden path), plus `reconstruct_heart_at()` filtering by `first_observed_at_visit`, `diagnosed_at`, and `measured_at` (fallback for legacy visits with no snapshot). The `confidence_status` of flags is correctly walked backwards too.

2. **The OSS HTML-download trap** — Alibaba Cloud OSS bucket-domain endpoints add `Content-Disposition: attachment` to HTML responses as an anti-phishing measure. Browser downloads `index.html` instead of rendering it. (`curl` doesn't parse `Content-Disposition`, so this was not caught in API tests.) Solution: let Caddy on ECS serve the SPA directly via `try_files {path} /index.html`; OSS remains the backup origin and the proof of usage.

3. **Drug audit recall** — the audit agent's grounding via openFDA / RxNorm initially missed lookups when only the brand name was provided. We solved it by writing brand + generic together (`"Zithromax (azithromycin)"`) before sending to Qwen and to the external APIs, with an `OVERRIDE` dict for tricky generics (IBU → ibuprofen, PARA → paracetamol). Recall jumped from ~40% to ~90% on the synthetic test set.

4. **Demo data quality** — multiple audit passes caught patient_problem English/Chinese duplicates (`Hypertension` vs `原發性高血壓`), name × age mismatches (a "Super Senior" patient with `age=36`), prescription items missing on chronic patients, and orphan flags from earlier smoke tests. A series of `fix_incomplete_visits.py` / `cleanup_smoke_leftover.py` / `normalize_chinese_only_problems.py` scripts brought the demo data set to a coherent state.

5. **Windows ↔ Linux line endings** — Docker container won't run `docker-entrypoint.sh` if it has CRLF (`/bin/bash^M: bad interpreter`). Solved with a `.gitattributes` forcing `text eol=lf` for `*.sh`, Caddyfile, Dockerfile, and yml files.

---

## Accomplishments that we're proud of

- **Closing the Track 1 loop end-to-end in 4 days, 38+ commits**, with a real working demo of memory accumulating across visits and retrospectively training the doctor.
- **The Mode A hindsight-bias bug was caught and fixed** with a principled mechanism (frozen snapshots + reconstruct), not a hack.
- **No fake clinical demos** — the Auntie Wang quartet is a genuine four-visit narrative with deterministic seed (the audit catch on visit 4 reproduces every time), not a hand-crafted UI mockup.
- **38+ commits in 3 days** is itself the iteration log — every UI audit feedback from the clinical researcher was acted on in the same session.
- **Under $1 USD of Alibaba Cloud spend** on the entire live demo deployment (well within the $40 voucher), with auto-Let's-Encrypt HTTPS, HTTP/3 enabled, and a single-URL same-origin architecture (no CORS overhead).

---

## What we learned

- **`curl` is not a substitute for a real browser when testing static hosting** — `Content-Disposition` and other browser-only behaviours can break a deployment that looks fine from a terminal.
- **Hindsight bias is the silent killer of retrospective AI tools** — without a principled snapshot or reconstruction mechanism, a "what would the AI have done" demo is actively misleading.
- **Soft observations need first-class state** — modelling `to_observe` as a real `confidence_status` (rather than a free-text comment) is what made the `auto-escalate on second observation` mechanic actually work, and what makes the demo emotionally land.
- **The audit pass from a clinical user is irreplaceable** — every meaningful bug in this build was found by Dr. Chloe poking at the UI, not by automated tests.

---

## What's next

- **Phase 2.5 — backfill `before_visit` snapshots** for the 169 mock visits without one (currently they Mode A via `reconstruct_heart_at` fallback, which is correct but slower).
- **Wire qwen3.7-plus** for visual intake of paper lab reports and X-ray photos (provider is already plumbed; UI not yet).
- **Wire paraformer-v2** for ambient dictation during the visit; currently the SOAP form is keyboard input.
- **Multi-tenant clinic deployment** — Firebase Auth is wired but currently bypassed for judge access; the production path is a per-clinic tenancy boundary on the `current_clinic_id` X-header (already in middleware).
- **Real-world regulatory pathway** — the heart layer + Mode A architecture is general enough to be of interest beyond family medicine; chronic disease specialties (cardiology, endocrinology) are the next natural targets.

---

## Built with

`alibaba-cloud-ecs` · `alibaba-cloud-oss` · `dashscope-international` · `qwen3.7-max` · `qwen3.7-plus` · `paraformer-v2` · `fastapi` · `sqlalchemy` · `alembic` · `pydantic` · `postgresql` · `react` · `typescript` · `vite` · `axios` · `zustand` · `docker` · `docker-compose` · `caddy` · `lets-encrypt` · `rxnorm` · `openfda` · `pubmed`

---

## Try it out (Devpost "Try it" link section)

- **Live demo (no login)**: https://47.84.230.19.nip.io/
- **Source repo**: <GitHub URL — driver to fill once repo is public>
- **Demo video**: <YouTube URL — driver to fill after upload>
- **Proof of Alibaba Cloud deployment**: <repo URL>/blob/master/deployment/ALIYUN.md
- **90-second testing walkthrough**: <repo URL>/blob/master/deployment/LIVE_DEMO.md
- **Architecture diagrams**: <repo URL>/blob/master/deployment/architecture.md

---

## Disclaimer (paste this at the bottom of "What it does")

This is a **sandbox demonstration** built for the Qwen Cloud Hackathon 2026. It uses fictional synthetic patient data only (101 patients, all deterministic-seeded). AI suggestions produced by this system are for educational illustration only and **do not constitute medical advice**.
