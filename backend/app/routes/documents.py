"""
============================================================
routes/documents.py — 病假紙、轉診信、診斷書
詳見 docs/API_SPEC.md §8, docs/WORKFLOWS.md W-7, W-8
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.middleware.clinic_permission import get_current_membership, require_role

router = APIRouter()


@router.post("/clinics/{clinic_id}/visits/{visit_id}/documents/sick-leave")
async def create_sick_leave(
    clinic_id: UUID, visit_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    """建立病假紙草稿（可選 use_ai_draft）。"""
    # TODO Sprint 6
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/visits/{visit_id}/documents/referral")
async def create_referral(
    clinic_id: UUID, visit_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    """建立轉診信草稿。"""
    # TODO Sprint 6
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/documents/{document_id}")
async def update_document(clinic_id: UUID, document_id: UUID, membership = Depends(get_current_membership)):
    """修改文件 content_json（限 status=draft）。"""
    # TODO Sprint 6
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/documents/{document_id}/confirm")
async def confirm_document(
    clinic_id: UUID, document_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    """確認文件並生成 PDF。"""
    # TODO Sprint 6
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/documents/{document_id}/pdf")
async def get_document_pdf(clinic_id: UUID, document_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 6
    return {"_stub": True}
