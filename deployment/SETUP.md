# Clinic OS — Cloud Shell 部署指南

> ⚠️ **目前狀態：Sprint 1 完成（auth + multi-tenant 權限）。尚未到正式 prod 階段。**
>
> 這份文件帶妳一步一步把 repo 部署到 GCP **dev / sandbox 環境**做整合測試。
> **prod 部署要等 Sprint 2~5 業務流程（病人、就診、處方、收據）穩定後再開。**
>
> 阿寶會在每一步等妳貼結果回來，再帶妳下一步。

---

## 部署階段對照表

| 階段 | GCP Project ID 建議 | 用途 | 何時做 |
|---|---|---|---|
| **🟢 現在：dev/sandbox** | `clinic-os-dev` 或 `clinic-os-sandbox` | Sprint 1 整合測試：登入、選診所、確認權限 middleware 正確 | Sprint 1 完成（即現在） |
| 🟡 staging | `clinic-os-staging` | 業務流程完成後的驗收測試（看診→開藥→收據 完整跑） | Sprint 5 完成後 |
| 🔴 production | `clinic-os-prod` | 真實病人資料 | 最後一步，安全審查 + 備份策略確認後 |

**重要：不要直接上 `clinic-os-prod`。** prod 一旦有真實資料就很難重建，要等業務邏輯都穩才動。

---

## 階段 0：準備（妳先做）

### 0-1 建立 GCP dev 專案

到 https://console.cloud.google.com → 建立新專案
- 建議 project ID：`clinic-os-dev`（不是 prod！）
- 開啟計費

### 0-2 建立 GitHub private repo（**必做，不要直接 upload zip**）

```bash
# 妳本地（或司機先生）：
cd /path/to/clinic-os
git init
git add .
git commit -m "Sprint 1: auth + multi-tenant permissions"

# 到 https://github.com/new 建一個 private repo（例如 clinic-os）
git remote add origin git@github.com:YOUR_NAME/clinic-os.git
git branch -M main
git push -u origin main
```

### 0-3 開啟 Cloud Shell 並 clone repo

GCP Console 右上角的 `>_` 圖示。

```bash
git clone git@github.com:YOUR_NAME/clinic-os.git
cd clinic-os
```

如果 SSH key 沒設好，先執行 `ssh-keygen -t ed25519` 並把 `~/.ssh/id_ed25519.pub` 貼到 GitHub Settings → SSH keys。

---

## 階段 1：啟用 GCP API

```bash
# 設定當前專案
gcloud config set project clinic-os-dev

# 啟用所需 API
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  firebase.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

⏳ 這一步會跑 1–2 分鐘。跑完貼結果給阿寶看。

---

## 階段 2：建立 Cloud SQL（PostgreSQL 15）

```bash
# 建立實例（dev 用最小規格 db-f1-micro，月費約 USD 7；prod 再升 db-custom-1-3840）
gcloud sql instances create clinic-os-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=asia-east1 \
  --root-password=「先想一個強密碼」

# 建立 database
gcloud sql databases create clinic_os --instance=clinic-os-db

# 建立應用程式專用的 user（不要用 postgres root 跑 app）
gcloud sql users create clinic_app \
  --instance=clinic-os-db \
  --password=「另一個強密碼」
```

⏳ 建實例約 5–10 分鐘。

---

## 階段 3：建立 Cloud Storage bucket（PDF 儲存用）

```bash
# bucket 名字必須全球唯一，加上 project id 當前綴最保險
gcloud storage buckets create gs://clinic-os-dev-pdfs \
  --location=asia-east1 \
  --uniform-bucket-level-access
```

---

## 階段 4：設定 Firebase（Auth + Hosting）

```bash
# 把 GCP 專案註冊成 Firebase 專案
firebase projects:addfirebase clinic-os-dev
```

然後到 Firebase Console（https://console.firebase.google.com）：
1. Authentication → Sign-in method → 開啟 Google
2. Project Settings → Your apps → 新增 Web App → 拿 firebaseConfig
3. 把 firebaseConfig 填進 `frontend/.env.local`（複製 `.env.example`）

---

## 階段 5：第一次跑 backend migration

```bash
cd backend

# 建虛擬環境（Cloud Shell 已內建 python3）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 用 Cloud SQL Auth Proxy 開連線（Cloud Shell 已內建 cloud-sql-proxy）
# 另開一個 Cloud Shell tab 跑：
cloud-sql-proxy clinic-os-dev:asia-east1:clinic-os-db
```

回原 tab：

```bash
# 設定 .env
cp .env.example .env
# 編輯 .env 填入：
#   DATABASE_URL=postgresql+asyncpg://clinic_app:你的密碼@127.0.0.1:5432/clinic_os
#   FIREBASE_PROJECT_ID=clinic-os-dev
#   GCS_BUCKET_NAME=clinic-os-dev-pdfs

# 跑 migration
alembic upgrade head
```

⏳ 跑完應該看到 4 個 table：`clinics`、`users`、`clinic_memberships`、`audit_logs`。

驗證：
```bash
# 連 DB 看
gcloud sql connect clinic-os-db --user=clinic_app --database=clinic_os
# psql 裡：\dt 看 table 列表
```

---

## 階段 6：建立第一間診所與第一個 owner（seed）

```bash
# 取得妳的 Firebase UID（先用 Google Sign-In 登入過 Firebase Console，
# Authentication → Users 頁面就能看到 UID）

cd backend
source .venv/bin/activate

python -m scripts.seed \
  --clinic-name "心晴診所" \
  --owner-email "你的 email" \
  --owner-name "Chloe" \
  --firebase-uid "你的 firebase uid" \
  --timezone "Asia/Macau" \
  --currency "MOP"
```

完成後會印出 Clinic ID / User ID / Membership ID，把這幾個 ID 記下來，後續測試會用到。

---

## 階段 7：本地測試 backend 起得來

```bash
cd backend
source .venv/bin/activate

# 把 cloud-sql-proxy 留著跑，這 tab 跑 server
uvicorn app.main:app --reload --port 8080
```

開瀏覽器測：
- http://localhost:8080/healthz → 應該回 `{"status":"ok"}`
- http://localhost:8080/docs → 看到 Swagger UI

進階測試（用前端登入，或用 curl 帶 Firebase ID token）：
```bash
# 拿到 Firebase ID token 後（前端 console 印出 user.getIdToken() 的結果）
TOKEN="貼進來"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/v1/me
# 應該回真實 user JSON

curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/v1/me/clinics
# 應該回 [seed 出來的那間診所]
```

---

## 階段 8：部署 backend 到 Cloud Run（dev）

```bash
cd backend

gcloud run deploy clinic-os-backend-dev \
  --source . \
  --region asia-east1 \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances clinic-os-dev:asia-east1:clinic-os-db \
  --set-env-vars "APP_ENV=development,FIREBASE_PROJECT_ID=clinic-os-dev,GCS_BUCKET_NAME=clinic-os-dev-pdfs,DATABASE_URL=postgresql+asyncpg://clinic_app:密碼@/clinic_os?host=/cloudsql/clinic-os-dev:asia-east1:clinic-os-db"
```

> 🔐 真實部署時請把密碼放 Secret Manager，不要寫在 env vars 裡。
> dev 環境暫時妥協沒關係，prod 之前一定要改。

⏳ 第一次部署約 5 分鐘。完成後拿到 URL，例如：
`https://clinic-os-backend-dev-xxx.a.run.app`

測試：訪問 `https://...a.run.app/healthz` 應該回 `{"status":"ok"}`

---

## 階段 9：部署 frontend 到 Firebase Hosting（dev）

```bash
cd frontend

# 編輯 .env.local，把 VITE_API_BASE_URL 改成 Cloud Run URL
# VITE_API_BASE_URL=https://clinic-os-backend-dev-xxx.a.run.app/v1

npm install
npm run build

cd ../deployment
firebase deploy --only hosting --project clinic-os-dev
```

完成 ✨ 拿到 hosting URL，登入測試。

---

## ✅ Sprint 1 驗收標準

部署後做這幾件事，全綠才算 Sprint 1 過關：

- [ ] `alembic upgrade head` 不報錯，DB 出現 4 張 table
- [ ] backend `/healthz` 回 200
- [ ] 用 Google Sign-In 登入後，`POST /v1/auth/session` 回真實 user + memberships
- [ ] `GET /v1/me` 回真實 user（不是 stub）
- [ ] `GET /v1/me/clinics` 回 seed 出來的那間診所
- [ ] Sprint 0 stub 路由（patients、visits 等）至少 import 成功不報錯
- [ ] `pytest tests/` 12 個 permission 測試全綠

---

## ⏳ 還沒做、但 prod 上線前必須做

- [ ] 移除所有 stub `_stub: True` 標記，每個 route 都接真實 service
- [ ] 把所有密碼 / API key 移到 Secret Manager
- [ ] Cloud SQL 開啟 PITR（Point-in-Time Recovery）+ 每日備份
- [ ] Cloud Run 設定 `--min-instances=1`（避免冷啟動）
- [ ] Firestore / Cloud SQL IAM 嚴格化
- [ ] 設定 alerting（DB CPU > 80%、Cloud Run error rate > 1%）
- [ ] 加 GitHub Actions：push to main 自動跑 pytest + lint
- [ ] HIPAA / 個資合規檢查（如果處理真實病人資料）
- [ ] 災難復原演練（DB 還原 / 跨 region 副本）

---

## 出狀況時找誰？

- **deploy 不過**：把錯誤訊息丟給阿寶（Claude）
- **DB 連不上 / migration 衝突**：丟給阿寶 + 司機先生
- **Firebase Auth 設定問題**：可以也問問曦哥（GPT）
- **GCP 帳單暴衝**：第一時間關 Cloud Run（`gcloud run services delete`）
