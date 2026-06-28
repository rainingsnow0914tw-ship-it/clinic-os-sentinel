# 🛡️ Sentinel — System Architecture

> Companion to [`README.md`](../README.md) and [`ALIYUN.md`](ALIYUN.md). All diagrams use Mermaid (GitHub renders inline).

---

## 1. Deployment topology

```mermaid
flowchart TB
    Judge["Judge browser"]

    subgraph ECS["Alibaba Cloud ECS (Singapore, ap-southeast-1)<br/>Ubuntu 22.04, ecs.e-c1m2.large"]
        Caddy["Caddy 2<br/>:80, :443<br/>Auto Let's Encrypt<br/>HTTP/3 enabled"]
        Frontend[("/srv/sentinel-frontend<br/>React SPA dist")]
        Backend["FastAPI + uvicorn<br/>2 workers, :8080"]
        DB[("PostgreSQL 16<br/>22 tables, alembic 0007")]
    end

    subgraph DashScope["Alibaba Cloud DashScope International<br/>dashscope-intl.aliyuncs.com"]
        QwenMax["qwen3.7-max<br/>4 agents (text)"]
        QwenPlus["qwen3.7-plus<br/>vision"]
        Paraformer["paraformer-v2<br/>ASR"]
    end

    OSS["Alibaba Cloud OSS bucket<br/>sentinel-demo-2026<br/>(frontend dist backup, public-read)"]

    Judge -- HTTPS --> Caddy
    Caddy -- "SPA fallback<br/>try_files / index.html" --> Frontend
    Caddy -- "/api/* (strip prefix)<br/>/v1/*" --> Backend
    Backend -- "asyncpg<br/>postgresql+psycopg" --> DB
    Backend -- "REST + Bearer key" --> QwenMax
    Backend -. vision (future) .-> QwenPlus
    Backend -. ASR (future) .-> Paraformer
    Frontend -. "dist also stored<br/>as proof of OSS usage" .-> OSS
```

---

## 2. The four sentinel agents

```mermaid
flowchart LR
    Visit["New visit form<br/>(SOAP + Rx)"]

    subgraph Agents["4 agents run in parallel"]
        Intake["intake_agent<br/>Structured chart<br/>+ anomaly flags"]
        Triage["triage_agent<br/>Differential ranking<br/>+ working hypothesis<br/>+ red-flag rule-out"]
        Audit["audit_agent<br/>Drug-vs-heart-layer<br/>+ RxNorm + openFDA<br/>+ rule engine"]
        Education["education_agent<br/>Patient-friendly<br/>summary"]
    end

    Heart[("Heart layer<br/>problems, meds,<br/>flags, baselines")]
    Drafts[("ai_drafts<br/>(replayable)")]

    Visit --> Intake
    Visit --> Triage
    Visit --> Audit
    Visit --> Education

    Heart -- context --> Triage
    Heart -- context --> Audit

    Intake --> Drafts
    Triage --> Drafts
    Audit --> Drafts
    Education --> Drafts
```

---

## 3. Phase 5 — heart layer auto-evolution (post-visit hook)

```mermaid
flowchart TB
    Submit["Doctor submits visit"]
    Flush["db.flush()<br/>(persist visit + ai_drafts)"]
    Evolve["evolve_heart_layer_after_visit"]
    Commit["db.commit()"]

    Submit --> Flush --> Evolve --> Commit

    subgraph Channels["4 evolution channels"]
        Problems["problems<br/>visit.diagnosis →<br/>chronic-keyword match →<br/>patient_problems<br/>(INFERRED_FROM_VISIT)"]
        Meds["medications<br/>audit findings →<br/>long-term-keyword filter →<br/>patient_medications<br/>(category=long_term)"]
        Flags["flags (the key one)<br/>intake.findings.anomaly →<br/>1st obs: to_observe<br/>2nd obs: confirmed<br/>(yellow → red)"]
        Baselines["baselines<br/>visit_examination vitals →<br/>BP, HR, T, SpO2, RR →<br/>patient_baselines trend"]
    end

    Evolve --> Problems
    Evolve --> Meds
    Evolve --> Flags
    Evolve --> Baselines
```

Idempotency: re-running the same visit through evolution does not duplicate problems / meds / flags (dedup + first-observed-at-visit guard). Baselines append.

---

## 4. Phase 6 — Mode A retrospective review

The bug we found mid-build: a naive replay shows the AI today's heart layer, not the heart layer as it was at the target visit. That leaks future knowledge into "what the AI would have known" and is hindsight bias.

The fix:

```mermaid
sequenceDiagram
    participant Doctor
    participant Backend
    participant Snapshots as heart_layer_snapshots
    participant Reconstruct as reconstruct_heart_at()
    participant PastVisits as prior visits
    participant Qwen as qwen3.7-max

    Doctor->>Backend: POST /v1/sentinel/visits/{vid}/review<br/>mode=at_the_time
    alt before_visit snapshot exists
        Backend->>Snapshots: load before_visit snapshot
        Snapshots-->>Backend: frozen heart layer
    else fallback (older visits without snapshot)
        Backend->>Reconstruct: filter by first_observed_at_visit,<br/>diagnosed_at, measured_at
        Reconstruct-->>Backend: heart layer as-of target visit
    end
    Backend->>PastVisits: gather intake.raw_dictation + triage.working_hypothesis<br/>from every prior visit
    PastVisits-->>Backend: past_visits_summary
    Backend->>Qwen: 4 agents in parallel<br/>(heart_layer + past_visits_summary)
    Qwen-->>Backend: 4 ai_drafts
    Backend-->>Doctor: ReviewResponse<br/>+ mode_disclaimer<br/>(no claim that doctor was wrong)
```

---

## 5. Phase 7 — doctor watchlist (retrospective coaching)

```mermaid
flowchart LR
    Review["Mode A review<br/>(visit 4)"]
    AuditFinding["Audit finds:<br/>ibuprofen ↔ amlodipine<br/>antagonism"]
    Pin["📌 Save to watchlist"]
    Store[("doctor_watchlists<br/>pattern + lesson_text<br/>+ triggered_count")]

    Banner["New-visit page banner:<br/>📌 You learned 1 lesson:<br/>ibuprofen + amlodipine<br/>in elderly hypertensives"]
    NewVisit["Doctor opens<br/>ANY new visit"]

    Review --> AuditFinding --> Pin --> Store
    NewVisit -- GET /watchlist --> Store
    Store --> Banner

    Pin -.-> |dedup by pattern<br/>+ triggered++| Store
```

The key design point: the watchlist is the doctor's, not the patient's. A lesson learned on Auntie Wang surfaces the next time the doctor sees anyone with a similar pattern.

---

## 6. Database schema highlights

```mermaid
erDiagram
    PATIENTS ||--o{ VISITS : has
    VISITS ||--|| VISIT_EXAMINATIONS : has
    VISITS ||--o{ PRESCRIPTIONS : has
    PRESCRIPTIONS ||--o{ PRESCRIPTION_ITEMS : contains
    VISITS ||--o{ AI_DRAFTS : runs
    VISITS ||--o{ HEART_LAYER_SNAPSHOTS : "before / after"

    PATIENTS ||--o{ PATIENT_PROBLEMS : "heart layer"
    PATIENTS ||--o{ PATIENT_MEDICATIONS : "heart layer"
    PATIENTS ||--o{ PATIENT_FLAGS : "heart layer"
    PATIENTS ||--o{ PATIENT_BASELINES : "heart layer"

    CLINICS ||--o{ DOCTOR_WATCHLISTS : "doctor's notes"

    PATIENT_FLAGS {
        uuid id
        string type
        string severity "yellow / red"
        string confidence_status "to_observe / confirmed"
        uuid first_observed_at_visit
        uuid confirmed_at_visit
        string source "auto_evolve / manual / ai_review"
    }

    HEART_LAYER_SNAPSHOTS {
        uuid id
        uuid visit_id
        string snapshot_type "before_visit / after_visit"
        jsonb payload
        text summary_text
    }
```

Full schema: 7 alembic migrations in [`backend/alembic/versions/`](../backend/alembic/versions/).

---

## 7. Request flow — happy path

```mermaid
sequenceDiagram
    participant Browser
    participant Caddy
    participant FastAPI
    participant Postgres
    participant Qwen as DashScope intl

    Browser->>Caddy: GET /sentinel/patients
    Caddy->>Caddy: try_files → /index.html
    Caddy-->>Browser: SPA index.html

    Browser->>Caddy: GET /api/v1/sentinel/patients?q=王
    Caddy->>FastAPI: GET /v1/sentinel/patients?q=王 (prefix stripped)
    FastAPI->>Postgres: SELECT ... WHERE name LIKE %王%
    Postgres-->>FastAPI: rows
    FastAPI-->>Caddy: JSON
    Caddy-->>Browser: JSON

    Browser->>Caddy: POST /api/v1/sentinel/visits/{vid}/review?mode=at_the_time
    Caddy->>FastAPI: POST /v1/sentinel/visits/{vid}/review
    FastAPI->>Postgres: load snapshot + past visits
    FastAPI->>Qwen: 4 parallel agent calls (qwen3.7-max)
    Qwen-->>FastAPI: 4 structured responses
    FastAPI->>Postgres: persist ai_drafts
    FastAPI-->>Caddy: ReviewResponse
    Caddy-->>Browser: render review panel
```

---

## 8. Why Caddy serves the SPA (not OSS)

We initially planned **OSS Standard bucket as the public frontend host**, with Caddy as backend-only reverse proxy. We hit a known limitation: Alibaba Cloud OSS bucket-domain endpoints add `Content-Disposition: attachment` to HTML responses as an **anti-phishing measure** — the browser downloads `index.html` instead of rendering it. (curl does not parse `Content-Disposition`, so this was not caught in API tests.)

Two workarounds exist:
1. **Custom domain with CNAME + own SSL certificate** — feasible but requires extra DNS work and an SSL cert per domain.
2. **OSS website-hosting endpoint** (`<bucket>.oss-website-<region>.aliyuncs.com`) — HTTP only, would force mixed-content issues with HTTPS backend calls.

We chose a third path: **let Caddy on ECS serve the SPA directly** (`try_files {path} /index.html`). Single origin, single TLS cert, no CORS overhead. The OSS bucket still holds the same `dist/` (uploaded with the `oss2` SDK — see [`ALIYUN.md`](ALIYUN.md)) as proof of OSS usage per the hackathon rules, and remains available as a backup CDN-style origin.

---

## 9. What's outside the diagram (deferred / future)

- **Phase 2.5 — backfill heart-layer snapshots** for the 169 mock visits (currently Mode A falls back to `reconstruct_heart_at` for those; Auntie Wang has real snapshots).
- **Vision / ASR** (qwen3.7-plus / paraformer-v2 wired but UI integration parked post-hackathon).
- **Multi-tenant auth** (currently `SENTINEL_DEV_BYPASS_AUTH=true` for judge access; Firebase wiring exists but is dormant).
- **CI/CD** (38 commits in 3 days are the iteration log; future migration to GitHub Actions).
