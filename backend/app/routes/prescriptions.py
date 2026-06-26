"""
============================================================
routes/prescriptions.py — 處方
詳見 docs/API_SPEC.md §6, docs/WORKFLOWS.md W-2, W-5
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.middleware.clinic_permission import get_current_membership, require_role

router = APIRouter()


@router.post("/clinics/{clinic_id}/visits/{visit_id}/prescriptions")
async def create_prescription(
    clinic_id: UUID, visit_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    # TODO Sprint 4
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/prescriptions/{prescription_id}/items")
async def add_prescription_item(
    clinic_id: UUID, prescription_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    """
    加開一個藥。
    伺服器即時計算 total_quantity / total_price / stock_status（W-2）。
    """
    # TODO Sprint 4
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/prescription-items/{item_id}")
async def update_prescription_item(
    clinic_id: UUID, item_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    # TODO Sprint 4
    return {"_stub": True}


@router.delete("/clinics/{clinic_id}/prescription-items/{item_id}")
async def delete_prescription_item(
    clinic_id: UUID, item_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    # TODO Sprint 4
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/prescriptions/{prescription_id}/confirm")
async def confirm_prescription(clinic_id: UUID, prescription_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 4
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/prescriptions/{prescription_id}/dispense")
async def dispense_prescription(
    clinic_id: UUID, prescription_id: UUID,
    membership = Depends(get_current_membership),
):
    """FEFO 扣庫存（W-5）。通常由 invoice issue 觸發，不應直接呼叫。"""
    # TODO Sprint 4
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/prescriptions/{prescription_id}/void")
async def void_prescription(
    clinic_id: UUID, prescription_id: UUID,
    membership = Depends(require_role("owner")),
):
    # TODO Sprint 5
    return {"_stub": True}
