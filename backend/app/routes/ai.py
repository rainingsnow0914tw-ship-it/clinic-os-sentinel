"""
============================================================
routes/ai.py — AI 草稿生成與 review flow
詳見 docs/API_SPEC.md §9, docs/AI_BOUNDARY.md, docs/WORKFLOWS.md W-9
============================================================

關鍵原則：AI 永遠寫進 ai_drafts，不直接寫正式表。
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.middleware.clinic_permission import get_current_membership

router = APIRouter()


@router.post("/clinics/{clinic_id}/ai/visit-summary")
async def ai_visit_summary(clinic_id: UUID, membership = Depends(get_current_membership)):
    """病人就診摘要。"""
    # TODO Sprint 7
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/ai/soap-draft")
async def ai_soap_draft(clinic_id: UUID, membership = Depends(get_current_membership)):
    """SOAP 病歷草稿（從口述/亂寫整理）。"""
    # TODO Sprint 7
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/ai/referral-draft")
async def ai_referral_draft(clinic_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 7
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/ai/sick-leave-draft")
async def ai_sick_leave_draft(clinic_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 7
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/ai/inventory-alerts")
async def ai_inventory_alerts(clinic_id: UUID, membership = Depends(get_current_membership)):
    """觸發 inventory agent task。"""
    # TODO Sprint 7
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/ai-drafts")
async def list_ai_drafts(
    clinic_id: UUID,
    visit_id: UUID | None = None,
    status: str | None = None,
    membership = Depends(get_current_membership),
):
    # TODO Sprint 7
    return {"items": [], "_stub": True}


@router.post("/clinics/{clinic_id}/ai-drafts/{draft_id}/accept")
async def accept_ai_draft(clinic_id: UUID, draft_id: UUID, membership = Depends(get_current_membership)):
    """
    人類接受草稿，將內容寫入正式表（target 由 draft_type 決定）。
    詳見 WORKFLOWS.md W-9 對應表。
    """
    # TODO Sprint 7
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/ai-drafts/{draft_id}/reject")
async def reject_ai_draft(clinic_id: UUID, draft_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 7
    return {"_stub": True}
