"""
============================================================
routes/invoices.py — 收據
詳見 docs/API_SPEC.md §7, docs/WORKFLOWS.md W-4, W-6
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.middleware.clinic_permission import (
    get_current_membership, require_permission,
)

router = APIRouter()


@router.post("/clinics/{clinic_id}/visits/{visit_id}/invoice-draft")
async def create_invoice_draft(clinic_id: UUID, visit_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 5
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/invoices/{invoice_id}")
async def update_invoice(clinic_id: UUID, invoice_id: UUID, membership = Depends(get_current_membership)):
    """限 status=draft 才能改。"""
    # TODO Sprint 5
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/invoices/{invoice_id}/issue")
async def issue_invoice(
    clinic_id: UUID, invoice_id: UUID,
    membership = Depends(get_current_membership),
):
    """
    確認收費並發藥（W-4）：
    - 產生 invoice_number
    - FEFO 扣庫存 + stock_movements
    - prescription.status = dispensed
    - visit.status = completed
    - 生成 receipt PDF → GCS
    - atomic transaction
    """
    # TODO Sprint 5
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/invoices/{invoice_id}/void")
async def void_invoice(
    clinic_id: UUID, invoice_id: UUID,
    membership = Depends(require_permission("can_void_invoice")),
):
    """作廢收據（W-6），自動回補庫存。"""
    # TODO Sprint 5
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(clinic_id: UUID, invoice_id: UUID, membership = Depends(get_current_membership)):
    """回 redirect 302 到 GCS signed URL。"""
    # TODO Sprint 5
    return {"_stub": True}
