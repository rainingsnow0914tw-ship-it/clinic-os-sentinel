"""
============================================================
routes/agent_tasks.py — A2A-ready Agent Tasks
詳見 docs/API_SPEC.md §10, docs/A2A_READY_ARCHITECTURE.md
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.middleware.clinic_permission import get_current_membership, require_role

router = APIRouter()


@router.post("/clinics/{clinic_id}/agent-tasks")
async def create_agent_task(clinic_id: UUID, membership = Depends(get_current_membership)):
    """建立 agent task（queued）。"""
    # TODO Sprint 8
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/agent-tasks")
async def list_agent_tasks(
    clinic_id: UUID,
    status: str | None = None,
    agent_type: str | None = None,
    membership = Depends(get_current_membership),
):
    # TODO Sprint 8
    return {"items": [], "_stub": True}


@router.get("/clinics/{clinic_id}/agent-tasks/{task_id}")
async def get_agent_task(clinic_id: UUID, task_id: UUID, membership = Depends(get_current_membership)):
    """含 events 列表。"""
    # TODO Sprint 8
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/agent-tasks/{task_id}/approve")
async def approve_agent_task(
    clinic_id: UUID, task_id: UUID,
    membership = Depends(require_role("owner", "doctor")),
):
    """核准 agent 提案，套用到實際表。"""
    # TODO Sprint 8
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/agent-tasks/{task_id}/reject")
async def reject_agent_task(clinic_id: UUID, task_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 8
    return {"_stub": True}
