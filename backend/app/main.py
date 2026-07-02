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

    # Phase 8 warmup: 預熱 Qwen shared client (TLS + DNS + auth handshake)
    # 之後第一次 review 不會因 4 個 agent parallel cold-start 而 timeout.
    import asyncio as _asyncio
    try:
        from app.providers.qwen import QwenProvider, _get_shared_client
        from app.providers.base import ChatMessage
        await _get_shared_client()  # 建 client (內部延遲到首次 request)
        provider = QwenProvider()
        try:
            await _asyncio.wait_for(
                provider.chat(
                    messages=[ChatMessage(role="user", content="ok")],
                    max_tokens=1,
                    temperature=0.0,
                ),
                timeout=30.0,
            )
            logger.info("Qwen provider warmed up (TLS+auth handshake done)")
        except _asyncio.TimeoutError:
            logger.warning("Qwen warmup call did not complete in 30s (OK — real requests will still work)")
        except Exception as e:
            logger.warning(f"Qwen warmup call failed (OK, real requests will still work): {e}")
    except Exception as e:
        logger.warning(f"Qwen warmup skipped: {e}")

    yield
    # === 關閉 ===
    logger.info("Shutting down Clinic OS API")
    try:
        from app.providers.qwen import close_shared_qwen_client
        await close_shared_qwen_client()
    except Exception as e:
        logger.warning(f"Qwen client shutdown failed: {e}")


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
# Phase 8 安全: In-memory per-IP rate limiter
# ============================================================
# 目的: 防止機器人 / scanner 找到 POST endpoint 大量濫用消耗 Qwen quota
# 或污染 demo data. Simple in-memory sliding window, 對 hackathon demo 夠用.
# 生產環境要換 Redis + slowapi.
# ------------------------------------------------------------
from collections import defaultdict
from time import monotonic

_IP_TOTAL_HITS: dict[str, list[float]] = defaultdict(list)
_IP_WRITE_HITS: dict[str, list[float]] = defaultdict(list)
_TOTAL_PER_MIN = 120        # 讀+寫 all methods per IP per minute
_WRITE_PER_MIN = 15         # POST/PUT/DELETE/PATCH per IP per minute
_HEAVY_PATH_LIMIT = 6       # /review 跟 create-visit 這種會打 Qwen 的 per minute
_WINDOW = 60.0

# 個別限更嚴的重路徑 (每次會呼叫 Qwen 4 agent, 貴)
_HEAVY_PREFIXES = (
    "/v1/sentinel/visits/",         # POST /visits/{id}/review
    "/v1/sentinel/patients/",       # POST /patients/{id}/visits (create visit)
)

_IP_HEAVY_HITS: dict[str, list[float]] = defaultdict(list)


def _prune(bucket: list[float], now: float) -> list[float]:
    cutoff = now - _WINDOW
    return [t for t in bucket if t > cutoff]


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 從 forwarded header 拿真 client IP (Caddy 有加 X-Forwarded-For)
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")
    now = monotonic()
    method = request.method
    path = request.url.path

    # health / OPTIONS preflight 不算
    if path.endswith("/health") or method == "OPTIONS":
        return await call_next(request)

    # 總量檢查
    total = _prune(_IP_TOTAL_HITS[ip], now)
    if len(total) >= _TOTAL_PER_MIN:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit: too many requests from your IP. Try again in a minute."},
        )

    # write 檢查
    is_write = method in {"POST", "PUT", "DELETE", "PATCH"}
    if is_write:
        write_bucket = _prune(_IP_WRITE_HITS[ip], now)
        if len(write_bucket) >= _WRITE_PER_MIN:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit: too many write requests. Try again in a minute."},
            )

        # 重路徑檢查 (Qwen billing 保護)
        if any(path.startswith(p) for p in _HEAVY_PREFIXES) and "/visits" in path:
            heavy_bucket = _prune(_IP_HEAVY_HITS[ip], now)
            if len(heavy_bucket) >= _HEAVY_PATH_LIMIT:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit: this endpoint triggers Qwen agents and is limited to "
                                  f"{_HEAVY_PATH_LIMIT} calls per minute per IP to protect the demo budget."
                    },
                )
            heavy_bucket.append(now)
            _IP_HEAVY_HITS[ip] = heavy_bucket

        write_bucket.append(now)
        _IP_WRITE_HITS[ip] = write_bucket

    total.append(now)
    _IP_TOTAL_HITS[ip] = total

    return await call_next(request)


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
