# ============================================================
# Clinic OS Sentinel Backend — Dockerfile
# 阿里雲 ECS docker-compose 部署用
# ============================================================

FROM python:3.11-slim

# 系統相依（WeasyPrint 要 Pango/Cairo、CJK 字型給 PDF）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./
COPY ./scripts ./scripts
COPY ./seed_data ./seed_data
COPY ./docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/v1/sentinel/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
