"""
============================================================
main.py — FastAPI Application Entry Point
============================================================
啟動順序：
1. 設定 logging
2. 初始化 Firebase Admin
3. 建 FastAPI app
4. 加 CORS middleware
5. 註冊所有 routers
6. 設 healthcheck endpoint
============================================================
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from app.core.config import settings
from app.core.security import init_firebase_admin

# 各 router（Sprint 0 都是 stub，Sprint 1+ 才實作）
from app.routes import (
    auth_router,
    patients_router,
    visits_router,
    drugs_router,
    prescriptions_router,
    invoices_router,
    documents_router,
    ai_router,
    agent_tasks_router,
    reports_router,
    sentinel_router,
    sentinel_patients_router,
    sentinel_review_router,
    sentinel_watchlist_router,
    sentinel_drugs_router,
)

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ============================================================
# Lifespan: 啟動 / 關閉時的初始化
# ============================================================
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理。"""
    # === 啟動 ===
    logger.info(f"Starting Clinic OS API in {settings.APP_ENV} mode")
    init_firebase_admin()
    logger.info("Firebase Admin initialized")
    yield
    # === 關閉 ===
    logger.info("Shutting down Clinic OS API")


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title=settings.API_TITLE,
    version="0.1.0",
    lifespan=lifespan,
    # 生產環境關掉 docs，避免暴露 schema
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)


# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 全域 exception handler（讓錯誤格式統一）
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """攔截所有未處理的 exception，回統一格式。"""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred",
            }
        },
    )


# ============================================================
# Healthcheck
# ============================================================
@app.get("/", tags=["health"])
async def root():
    return {"name": settings.API_TITLE, "version": "0.1.0", "env": settings.APP_ENV}


@app.get("/healthz", tags=["health"])
async def healthz():
    """K8s / Cloud Run 的 healthcheck。"""
    return {"status": "ok"}


# ============================================================
# Routers
# ============================================================
prefix = settings.API_PREFIX

app.include_router(auth_router,         prefix=prefix, tags=["auth"])
app.include_router(patients_router,     prefix=prefix, tags=["patients"])
app.include_router(visits_router,       prefix=prefix, tags=["visits"])
app.include_router(drugs_router,        prefix=prefix, tags=["drugs"])
app.include_router(prescriptions_router, prefix=prefix, tags=["prescriptions"])
app.include_router(invoices_router,     prefix=prefix, tags=["invoices"])
app.include_router(documents_router,    prefix=prefix, tags=["documents"])
app.include_router(ai_router,           prefix=prefix, tags=["ai"])
app.include_router(agent_tasks_router,  prefix=prefix, tags=["agent_tasks"])
app.include_router(reports_router,      prefix=prefix, tags=["reports"])
app.include_router(sentinel_router,     prefix=prefix, tags=["sentinel"])
app.include_router(sentinel_patients_router, prefix=prefix, tags=["sentinel-patients"])
app.include_router(sentinel_review_router, prefix=prefix, tags=["sentinel-review"])
app.include_router(sentinel_watchlist_router, prefix=prefix, tags=["sentinel-watchlist"])
app.include_router(sentinel_drugs_router, prefix=prefix, tags=["sentinel-drugs"])
