# 🛡️ Sentinel — Live Demo Walkthrough

> For Qwen Cloud Hackathon 2026 judges. No login required (dev-bypass mode).

## Try it

**👉 https://47.84.230.19.nip.io/**

Should auto-redirect to `/sentinel/patients` (patient search page).

---

## Track 1 (MemoryAgent) demo flow — 90 seconds

### Scene 1: longitudinal memory across visits

1. On the patient search page, type **`王`** → click the patient **王慧明 (王阿姨)** (`TEST-W007`).
2. You see her heart layer accumulated across 4 visits over 9 months:
   - 1 **confirmed red flag**: "偶爾忘東西" (occasional forgetfulness, escalated from `to_observe` → `confirmed` by Phase 5 auto-evolution)
   - 1 chronic problem: hypertension
   - 1 long-term med: amlodipine
   - BP/HR baseline trend chart

### Scene 2: retrospective AI review (Mode A reconstruct)

3. Scroll to visit timeline → click any visit row → click **「🔁 跑 AI 回顧」**.
4. The system:
   - Reconstructs the heart layer **as it was at that visit** (using `reconstruct_heart_at` + before-visit snapshot)
   - Injects all *prior* visits' diagnosis + Rx (`_build_past_visits_summary`)
   - Runs 4 Qwen3.7-max agents (intake / triage / audit / education)
5. For **visit 4 (2026-06-26)** the audit agent flags **ibuprofen ↔ amlodipine BP antagonism** — a finding the doctor missed at the time.

### Scene 3: reverse-training the doctor (watchlist)

6. In the review panel, click **「📌 加進 watchlist」**.
7. The system extracts the pattern + lesson into `doctor_watchlists`.
8. Click **「新就診」** to start a new visit (any patient).
9. At the top of the new-visit page, a **banner** shows: *"📌 你過去學到的 1 條: ibuprofen + amlodipine interaction"*.

This is the closed loop: **AI memory grows across visits AND retrospectively trains the doctor**.

---

## Track 4 (Autopilot) supporting flow

- New visit page → fill SOAP form (chief complaint / HPI / PE / diagnosis) → add Rx via **category dropdown → drug type-ahead → frequency → days** (no typing, auto-computes total qty).
- 4 agents run in parallel on submit (~30-50s via Qwen3.7-max).
- ai_drafts persisted; visit detail page can replay every agent's reasoning.

---

## Endpoints (curl-able by judges)

```bash
# Health
curl https://47.84.230.19.nip.io/v1/sentinel/health

# Patient list
curl https://47.84.230.19.nip.io/v1/sentinel/patients?q=王

# 王阿姨 heart layer
PID=$(curl -s "https://47.84.230.19.nip.io/v1/sentinel/patients?q=王" | python -c "import json,sys;print(json.load(sys.stdin)['items'][0]['id'])")
curl https://47.84.230.19.nip.io/v1/sentinel/patients/$PID/heart-layer | jq

# Drug categories
curl https://47.84.230.19.nip.io/v1/sentinel/drugs/categories | jq

# Doctor watchlist
curl https://47.84.230.19.nip.io/v1/sentinel/watchlist | jq
```

---

## Data scope

- 101 patients (100 mock + 王阿姨 quartet)
- 182 visits, 26 patient_flags (1 confirmed), 58 problems, 77 long-term meds, 400+ baselines
- 10 heart_layer_snapshots (before/after each 王阿姨 visit)
- 20 ai_drafts (Phase 6 Mode A/B + Phase 7 smoke)

All names / addresses are synthetic Macau-style placeholders. No real PHI.

---

## Disclaimer (per v0.3.1 §13.5)

This is a **sandbox demonstration**. The system uses fictional patient data; AI suggestions are for educational illustration only and do not constitute medical advice.
