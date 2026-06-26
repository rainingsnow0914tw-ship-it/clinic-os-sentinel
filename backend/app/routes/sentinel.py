"""
============================================================
routes/sentinel.py — Sentinel REST endpoints
============================================================
4 個 agent 的對外 endpoint。給：
- demo 腳本 / pytest smoke test
- 阿里雲評審 test access(Devpost 必填欄位)
- frontend 將來接

⚠️ 比賽期 demo 紀律：
- 這裡 endpoint 預設不接 Firebase Auth(SENTINEL_DEV_BYPASS_AUTH=true)
- 評審要能 curl 直接打就跑(不必登入)
- production(Chloe 自用版)要把 Depends(get_current_membership) 加回來

路徑：
- POST /v1/sentinel/intake     入口偵查官
- POST /v1/sentinel/triage     前閘門鑑別診斷
- POST /v1/sentinel/audit      後閘門處方審計
- POST /v1/sentinel/education  衛教出口
- GET  /v1/sentinel/health     簡單 healthcheck(快速驗證 Qwen 可達)
============================================================
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.agents import (
    run_intake_agent,
    run_triage_agent,
    run_audit_agent,
    run_education_agent,
)
from app.core.config import settings
from app.providers import get_default_provider
from app.providers.base import ChatMessage
from app.schemas.sentinel import (
    IntakeRequest,
    IntakeResponse,
    TriageRequest,
    TriageResponse,
    AuditRequest,
    AuditResponse,
    EducationRequest,
    EducationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# 健康檢查 — 確認 Qwen 可達
# ============================================================
@router.get("/sentinel/health")
async def sentinel_health(probe: bool = False) -> dict:
    """
    Sentinel 健康檢查。預設快速(只看 config),不打 Qwen。

    用 `?probe=true` 才真實打 Qwen 驗 endpoint(慢,30-60秒)。

    Frontend SentinelPage 進來時呼叫預設版本 → 立刻 OK,UI 不卡。
    """
    if not settings.SENTINEL_ENABLED:
        return {"status": "disabled", "reason": "SENTINEL_ENABLED=false"}

    if not settings.DASHSCOPE_API_KEY:
        return {
            "status": "misconfigured",
            "reason": "DASHSCOPE_API_KEY not set in .env",
        }

    # 預設只回 config check(< 1ms,frontend 友善)
    if not probe:
        return {
            "status": "ok",
            "provider": "qwen",
            "model": settings.QWEN_TEXT_MODEL,
            "dev_bypass_auth": settings.SENTINEL_DEV_BYPASS_AUTH,
        }

    # probe=true 才真打 Qwen
    provider = get_default_provider()
    try:
        resp = await provider.chat(
            messages=[ChatMessage(role="user", content="用一句話介紹自己")],
            temperature=0.1,
            max_tokens=80,
        )
        return {
            "status": "ok",
            "provider": provider.name,
            "model": resp.model,
            "echo": resp.text,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "dev_bypass_auth": settings.SENTINEL_DEV_BYPASS_AUTH,
        }
    except Exception as e:
        logger.exception("Sentinel health probe: Qwen call failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "qwen_call_failed", "message": str(e)},
        )


# ============================================================
# Agent 1：入口偵查官
# ============================================================
@router.post("/sentinel/intake", response_model=IntakeResponse)
async def sentinel_intake(req: IntakeRequest) -> IntakeResponse:
    """把醫生口述變結構化偵查結果。"""
    return await run_intake_agent(req)


# ============================================================
# Agent 2：前閘門鑑別診斷
# ============================================================
@router.post("/sentinel/triage", response_model=TriageResponse)
async def sentinel_triage(req: TriageRequest) -> TriageResponse:
    """撞病史紅旗找盲點，最多 3 個鑑別。沒矛盾就回空。"""
    return await run_triage_agent(req)


# ============================================================
# Agent 3：後閘門處方審計
# ============================================================
@router.post("/sentinel/audit", response_model=AuditResponse)
async def sentinel_audit(req: AuditRequest) -> AuditResponse:
    """規則引擎 + AI 第三層情境推理。事實查表非編造。"""
    return await run_audit_agent(req)


# ============================================================
# Agent 4：衛教出口
# ============================================================
@router.post("/sentinel/education", response_model=EducationResponse)
async def sentinel_education(req: EducationRequest) -> EducationResponse:
    """個人化生活醫囑(只解釋為什麼，不示範動作)。"""
    return await run_education_agent(req)
