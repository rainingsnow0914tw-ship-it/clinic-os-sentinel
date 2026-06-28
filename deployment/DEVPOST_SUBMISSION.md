# 📝 Devpost Submission Form — Copy-Paste Ready

> Paste each section into the corresponding field on the Devpost submission form for **Qwen Cloud Hackathon 2026**.
> All text in English (per hackathon rules §language).

---

## Project name (50 / 60 chars — submitted 2026-06-29)
The Sentinel — A MemoryAgent for Clinical Practice

## Elevator pitch / Tagline (155 / 200 chars — submitted 2026-06-29)
A Qwen3.7-max diagnostic sentinel — memory accumulates across patient visits, AND retrospectively trains the doctor on what they missed. No hindsight bias.

## Tracks
- **Primary**: Track 1 — MemoryAgent
- **Supporting**: Track 4 — Autopilot

---

## Inspiration

Most clinical AI tools answer one question: **what should this doctor do in this single visit?**

It's the easiest framing to build for — and the most lossy one. 🩺

A patient mentions *"oh, my memory has been a bit off lately"* on visit 2. Visit 3 brings ibuprofen for knee pain. Visit 4 brings a fall, rebounded BP, and worsening forgetfulness. Three visits, three different chart pages — and nowhere does the system **connect the dots**.

The same waste pattern, three different costumes:

- 🗒️ a single-visit AI that re-reads the chart from scratch every time
- 🔁 a doctor who reads a soft observation and never writes it down as "track this"
- ♻️ a retrospective system that quietly hands the AI today's knowledge to "review" what happened nine months ago

> ❓ So we asked a different question: not *"what should the AI say in this visit"*, but **"how does memory of *this patient* grow across visits — and can the AI use that memory to retrospectively train the *doctor* on what they missed?"**

That second direction — backward into the doctor — is the one no chart system does. So we built it.

---

## What it does

**The Sentinel** is a four-agent diagnostic layer on **Qwen3.7-max** that closes the loop in *both* directions. It runs as one closed system:

🧠 **Heart layer — patient memory that grows itself**
Four per-patient tables (`problems` / `medications` / `flags` / `baselines`) updated automatically when any visit completes. No doctor labeling, no annotation UI. A diagnosis on visit 1 becomes a chronic problem; an anomaly mentioned in passing on visit 2 becomes a `to_observe` flag; the **same anomaly seen again on visit 4 auto-escalates to `confirmed` red flag** — yellow goes red without anyone clicking anything.

📸 **Heart-layer snapshots — frozen-in-time replay state**
Every visit takes a `before_visit` and `after_visit` snapshot. This is what makes the next part *honest*.

🔁 **Mode A retrospective review — without the hindsight bias**
The doctor clicks "Run AI Retrospective Review" on any past visit. The system loads the snapshot (or reconstructs it via `reconstruct_heart_at()` for legacy visits), injects every *prior* visit's diagnosis and prescription as context, and runs four Qwen agents. The AI sees **only what was knowable at the time** — never what we learned afterward. *Hindsight isn't a virtue. It's a bias we engineered out.*

🧾 **And we show our work.** Every heart-layer item displays the visit it was first observed at. Every Mode A review explicitly lists what was excluded — *"⊘ flag: 偶爾忘東西 (first observed 2026-02-15, after this visit); 9 baselines recorded after this visit"*. The no-hindsight guarantee lives in the UI, not just in a promise.

📌 **Doctor watchlist — the AI reverse-trains the human**
When Mode A surfaces something the doctor missed, one click pins the lesson to **the doctor's** watchlist — not the patient's. Next time the doctor opens a new visit for *any* patient, a banner surfaces the pattern. *Memory across visits. AND backward into the doctor.*

The full Track 1 demo runs on **Auntie Wang**, a deterministic four-visit case spanning nine months: hypertension diagnosed on visit 1, amlodipine prescribed; visit 3 adds ibuprofen for knee pain and a passing mention of forgetfulness; visit 4 brings rebounded BP, worsening forgetfulness, and a fall. The Audit agent on Mode A correctly identifies the **ibuprofen × amlodipine antagonism** that was hiding in plain sight for three visits.

Track 4 (Autopilot) shows up in the new-visit page: SOAP-form intake, prescriptions via category → drug type-ahead → frequency → days, four agents fanned out in parallel on submit, every output persisted in `ai_drafts` for replay. *The doctor reviews. The AI never auto-writes.* (ADR-006.)

---

## How we built it

Three pillars, all wired to **live** data:

🤖 **Qwen3.7-max via DashScope International**
Every clinical reasoning call — intake, triage, audit, education — runs against `qwen3.7-max` through `dashscope-intl.aliyuncs.com`. The audit agent additionally grounds drugs against **RxNorm + openFDA + PubMed**, with brand and generic names written together (`"Zithromax (azithromycin)"`) so Qwen and the open APIs both find a match. Recall jumped from ~40% to ~90% on the synthetic test set.

🏗️ **FastAPI + SQLAlchemy + Alembic + PostgreSQL 16**
Seven Alembic migrations, 22 tables. The `evolve_heart_layer_after_visit` post-visit hook is a deterministic, idempotent service — not an LLM. *LLMs decide. State machines persist.* `reconstruct_heart_at()` filters every heart-layer row by `first_observed_at_visit` / `diagnosed_at` / `measured_at`, walking the `confidence_status` backwards so a confirmed-today flag becomes a to-observe-then flag if it confirmed after the target visit.

☁️ **Alibaba Cloud — ECS + OSS + DashScope, all in Singapore**
Three containers on one ECS box (`ecs.e-c1m2.large`, Ubuntu 22.04): PostgreSQL 16, FastAPI backend, **Caddy 2** with auto-Let's-Encrypt. Frontend `dist/` lives both on the ECS for the live demo (single origin, no CORS) and on **OSS bucket** `sentinel-demo-2026` (the asset-backup origin + the rule-compliance proof). Total spend at submission: **under $1 USD on the $40 voucher**. The infrastructure is intentionally boring so the *clinical reasoning* gets all the attention.

---

## Challenges we ran into

🪤 **The OSS HTML-download trap**
Alibaba Cloud OSS bucket-domain endpoints add `Content-Disposition: attachment` to HTML responses (anti-phishing). Browsers download `index.html` instead of rendering it. `curl` doesn't parse `Content-Disposition`, so this never showed in API tests. *Browsers and curl don't agree about what `text/html` means.* Fixed by serving the SPA from Caddy on ECS directly; OSS stays as backup origin and compliance proof.

⏪ **Hindsight bias was the entire risk of Mode A**
The first cut of retrospective review naively replayed today's heart layer into the past. That's not retrospection — it's telling the AI the answer and asking it to find the question. Caught in the daily UI audit pass. Fixed with two complementary mechanisms: `before_visit` snapshots taken at visit creation (golden path), and `reconstruct_heart_at()` filtering by observed/diagnosed/measured timestamps (fallback for legacy visits). *A retrospective tool that leaks the future is worse than no tool.*

🥶 **Windows line endings vs Linux containers**
Docker container refuses to run `docker-entrypoint.sh` if it carries CRLF — `/bin/bash^M: bad interpreter`. `.gitattributes` with `text eol=lf` for `*.sh`, Caddyfile, Dockerfile, and yml. *Tooling that crosses OS lines needs an explicit treaty about whitespace.*

🩺 **Demo data quality is a clinical signal**
The clinical researcher caught what no automated test would: a "Super Senior" patient with `age=36`; `Hypertension` and `原發性高血壓` as duplicate problems on the same patient; chronic patients with no long-term medication; visits without prescriptions. *Bad demo data isn't a cosmetic bug — it tells the wrong story about your system.* A series of normalize-and-cleanup scripts brought 169 mock visits + Auntie Wang's quartet to a coherent state.

---

## Accomplishments we're proud of

- 🔄 **A closed loop in both directions.** Forward (memory across visits) **and** backward (retrospective coaching). One demo, both directions, ~3 minutes end-to-end.
- 🛡️ **Mode A is honest — and the UI proves it.** The AI sees only what was knowable then. Every heart-layer row shows its visit-of-origin timestamp; every Mode A run explicitly lists what was excluded by reconstruction. The judges can read the no-hindsight guarantee straight off the screen.
- 📌 **The watchlist belongs to the doctor, not the patient.** A lesson learned on Auntie Wang surfaces the next time the doctor sees *anyone* with the same pattern. *AI as coach, not chart.*
- 💸 **Live on Alibaba Cloud for under $1.** ECS + OSS + DashScope + Caddy auto-TLS + HTTP/3 enabled. Cost-engineering is a feature.
- 🩺 **Built with a clinical researcher in the loop.** Every UX bug — including the Mode A hindsight leak — was caught by the daily clinical audit pass, not by automated tests. Three days, 38+ commits, every one of them feedback-driven.

---

## What we learned

A *single-visit* answer is the wrong answer to most family-medicine questions. The real signal lives in the **shape of the patient's history** — the to_observe flag that fires twice, the drug prescribed at visit 3 that interacts with the one prescribed at visit 1, the BP trend across nine months. That signal is invisible to chart-page-shaped AI.

And: **hindsight is a bias, not a virtue.** A retrospective coaching tool that doesn't engineer hindsight *out* is just a hindsight-bias generator with a nicer UI. The snapshot + `reconstruct_heart_at()` plumbing is what makes the doctor trust the lesson — and what makes the system safe to actually train them with.

One symptom is never a diagnosis. *The same holds for one visit.* 🩺

---

## What's next

- 📸 **Backfill snapshots for the 169 legacy visits** so Mode A runs on snapshots end-to-end (Auntie Wang's quartet already has full snapshots; the rest fall back to reconstruct).
- 👁️ **Wire `qwen3.7-plus` for visual intake** — paper lab reports and X-ray photos. Provider plumbed, UI not yet.
- 🎙️ **Wire `paraformer-v2` for ambient dictation** during the visit. SOAP form is keyboard input right now.
- 🏥 **Multi-tenant clinic deployment.** Firebase Auth is wired but bypassed for judge access; production path is per-clinic tenancy on `X-Clinic-Id` (already in middleware).
- 🩺 **Specialties beyond family medicine.** Heart layer + Mode A is general; cardiology and endocrinology are the natural next targets.

---

## Built with (Devpost tag input — 一個一個輸入按 Enter，不要包反引號、不要用 · 分隔)

```
alibaba-cloud-ecs
alibaba-cloud-oss
dashscope-international
qwen3.7-max
qwen3.7-plus
paraformer-v2
fastapi
sqlalchemy
alembic
pydantic
postgresql
react
typescript
vite
axios
zustand
docker
docker-compose
caddy
lets-encrypt
rxnorm
openfda
```

(22 tags. `pubmed` 拿掉了——audit agent 規劃連 PubMed 但 hackathon 階段沒實接，誠實一點。)

---

## Try it out (Devpost "Try it" link section)

- 🟢 **Live demo (no login)**: https://47.84.230.19.nip.io/
- 📦 **Source repo (MIT)**: https://github.com/rainingsnow0914tw-ship-it/clinic-os-sentinel
- 🎬 **Demo video (≤3 min)**: <YouTube URL — driver to fill after upload>
- ☁️ **Proof of Alibaba Cloud deployment**: https://github.com/rainingsnow0914tw-ship-it/clinic-os-sentinel/blob/master/deployment/ALIYUN.md
- 🩺 **90-second judge walkthrough**: https://github.com/rainingsnow0914tw-ship-it/clinic-os-sentinel/blob/master/deployment/LIVE_DEMO.md
- 🏗️ **Architecture diagrams (Mermaid)**: https://github.com/rainingsnow0914tw-ship-it/clinic-os-sentinel/blob/master/deployment/architecture.md

---

## Disclaimer (paste this at the bottom of "What it does")

⚠️ **Sandbox demonstration.** Built for the Qwen Cloud Hackathon 2026. Uses fictional synthetic patient data only (101 patients, all deterministic-seeded). AI suggestions are for educational illustration only and **do not constitute medical advice**.
