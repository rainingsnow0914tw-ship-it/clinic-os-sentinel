# ============================================================
# Clinic OS Backend Dockerfile
# 部署到 Google Cloud Run 用
# ============================================================

FROM python:3.11-slim

# 系統相依（WeasyPrint 需要 Pango / Cairo）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先裝相依（讓 docker layer cache 生效）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 再 copy 程式碼
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./

# Cloud Run 會用 PORT 環境變數
ENV PORT=8080
EXPOSE 8080

# Cloud Run 建議 1 worker per instance（autoscale 由 Cloud Run 處理）
CMD exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
