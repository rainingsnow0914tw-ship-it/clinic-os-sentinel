# 🛡️ Sentinel — Alibaba Cloud Deployment

> Qwen Cloud Hackathon 2026 投稿用「Proof of Alibaba Cloud Deployment」入口文件。
> Submission deadline: **2026-07-09 14:00 PT**

## 🟢 Live deployment

- **Frontend (OSS)**: https://sentinel-demo-2026.oss-ap-southeast-1.aliyuncs.com/
- **Backend API base**: https://47.84.230.19.nip.io/api/
- **Health check**: https://47.84.230.19.nip.io/v1/sentinel/health
- **Region**: Singapore (ap-southeast-1)
- **Stack**: ECS (Ubuntu 22.04, ecs.e-c1m2.large) + OSS Standard + Caddy 2 + Let's Encrypt
- **Deployment proof commit**: see git log for `feat(phase8): 阿里雲 ECS+OSS 部署起手`

---

## Alibaba Cloud services used

| Service | Region | Purpose | Code reference |
|---|---|---|---|
| **ECS** (Elastic Compute Service) | `ap-southeast-1` (Singapore) | Hosts backend FastAPI + PostgreSQL 16 + Caddy reverse proxy via docker-compose | [`deployment/docker-compose.yml`](docker-compose.yml) |
| **OSS** (Object Storage Service) | `ap-southeast-1` (Singapore) | Static hosting for React + Vite frontend build | [`deployment/ALIYUN.md#frontend--oss`](#frontend--oss) (this file, frontend section) |
| **DashScope (Qwen) International** | `ap-southeast-1` backbone | 4 sentinel agents (intake / triage / audit / education) on `qwen3.7-max`; vision on `qwen3.7-plus`; ASR on `paraformer-v2` | [`backend/app/providers/qwen.py`](../backend/app/providers/qwen.py), [`backend/app/agents/`](../backend/app/agents/), endpoint `https://dashscope-intl.aliyuncs.com/api/v1` configured in [`backend/.env.example`](../backend/.env.example) |

---

## Architecture

```
                       Judge browser
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
   OSS static bucket            ECS (ap-southeast-1)
   sentinel-demo.oss-           ┌─────────────────────────────┐
   ap-southeast-1.aliyuncs.com  │ Caddy :80/:443 (Let's       │
   (React + Vite build)         │   Encrypt auto-renew)       │
                │               │   ↓ reverse_proxy /api/*    │
                │               │ backend :8080 (FastAPI)     │
                │  /api/* via   │   ↓ asyncpg                 │
                └──────────────►│ db :5432 (PostgreSQL 16)    │
                                └──────────────┬──────────────┘
                                               │
                                               ▼
                                  DashScope intl REST API
                                  (Qwen3.7-max 4-agent
                                   diagnostic loop)
```

All three components are inside Alibaba Cloud:
- **ECS** runs compute + DB.
- **OSS** serves the SPA.
- **DashScope intl** powers every LLM call.

---

## Deployment SOP (driver-runnable)

### Prereq: ECS provisioning (driver does in Alibaba Cloud console)
1. Region: **Singapore (ap-southeast-1)**
2. Spec: **ecs.e-c1m2.large** (2 vCPU / 4 GB) or higher, **40 GB ESSD**
3. OS: **Ubuntu 22.04 LTS x64**
4. Public IPv4: assigned, **1 Mbps pay-by-traffic** (enough for demo)
5. Security group inbound: **22 / 80 / 443**. **Do NOT open 5432** (DB is internal).
6. Key pair: download `.pem` (no password login).

### Step 1 — bootstrap ECS
SSH in, then:
```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER  # log out & back in
```

### Step 2 — clone repo
```bash
git clone <repo-url> ~/sentinel
cd ~/sentinel/deployment
```

### Step 3 — fill env
```bash
cp .env.example .env
cp backend.env.example backend.env
nano .env          # fill DOMAIN, CADDY_EMAIL, PG_PASSWORD
nano backend.env   # paste DASHSCOPE_API_KEY, set CORS_ORIGINS to OSS URL
```

### Step 4 — DNS
- Point `<DOMAIN>` A record → ECS public IP (TTL 60s).
- Verify: `dig +short <DOMAIN>` returns ECS IP from a 3rd-party DNS.

### Step 5 — bring up the stack
```bash
docker compose --env-file .env up -d --build
docker compose logs -f backend   # 等到看到 Uvicorn running on 0.0.0.0:8080
```

Caddy will auto-request Let's Encrypt cert on first request.

### Step 6 — seed demo data
```bash
docker compose exec backend python scripts/seed.py \
  --clinic-name "千問哨兵示範診所" \
  --owner-email chloe@sentinel.demo \
  --owner-name "Dr. Chloe" \
  --firebase-uid demo-uid
docker compose exec backend python scripts/seed_dev_data.py
docker compose exec backend python scripts/extend_mock_patients.py
docker compose exec backend python scripts/seed_heart_layer.py
docker compose exec backend python scripts/seed_wang_aunt_quartet.py
```

### Step 7 — smoke
```bash
curl -sS https://<DOMAIN>/v1/sentinel/health
curl -sS https://<DOMAIN>/v1/sentinel/patients | jq '.[0]'
```

### Frontend → OSS
On dev machine:
```bash
cd frontend
# 設 VITE_API_BASE 指向雲端 backend
echo "VITE_API_BASE=https://<DOMAIN>" > .env.production
npm run build
# 把 dist/ 整個 sync 上 OSS
ossutil sync ./dist oss://sentinel-demo-2026/ --delete
```

OSS bucket settings:
- Static website hosting: index `index.html`, error `index.html` (SPA)
- Read permission: **public read**
- CORS: enable, allow origin `*` (or specifically `https://<DOMAIN>`)

Update backend `CORS_ORIGINS` to include the OSS URL, then `docker compose restart backend`.

---

## Cost guard ($40 hackathon voucher)

| Item | Approx monthly | 2-week demo cost |
|---|---|---|
| ECS ecs.e-c1m2.large pay-as-you-go | ~$20 | ~$10 |
| 1 Mbps pay-by-traffic | ~$1-3 | <$2 |
| OSS storage + traffic | <$1 | <$1 |
| DashScope intl Qwen3.7-max | covered by separate API quota | $0 |
| **Total** | | **~$13** |

Well under the $40 voucher.

---

## Compliance reference

This deployment satisfies the **Qwen Cloud Hackathon Rules — "Proof of Alibaba Cloud Deployment"**:

> "You must demonstrate that the backend is running on Alibaba Cloud. Proof: a link to a code file in the code repo that demonstrates use of Alibaba Cloud services and APIs."

This file (`deployment/ALIYUN.md`) plus the linked configuration files (`docker-compose.yml`, `Caddyfile`, `backend/app/providers/qwen.py`) form that proof.
