#!/bin/bash
# ============================================================
# Sentinel backend container entrypoint
# 啟動前先等 DB ready、跑 alembic upgrade head、再 exec CMD
# ============================================================
set -euo pipefail

echo "[entrypoint] 等 PostgreSQL ready..."
python - <<'PY'
import os, time, sys
import psycopg
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
for i in range(60):
    try:
        with psycopg.connect(url, connect_timeout=2) as c:
            c.execute("SELECT 1")
            print(f"[entrypoint] DB ready (attempt {i+1})")
            sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] DB not ready ({i+1}/60): {e}")
        time.sleep(2)
sys.exit(1)
PY

echo "[entrypoint] 跑 alembic upgrade head..."
alembic upgrade head

echo "[entrypoint] 啟動 backend: $@"
exec "$@"
