"""
============================================================
routes/visits.py — 就診紀錄
詳見 docs/API_SPEC.md §4 與 docs/WORKFLOWS.md W-3
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends
from app.middleware.clinic_permission import get_current_membership, require_role

router = APIRouter()


@router.post("/clinics/{clinic_id}/visits")
async def create_visit(clinic_id: UUID, membership = Depends(get_current_membership)):
    """建立就診紀錄（status=draft）。"""
    # TODO Sprint 2
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/patients/{patient_id}/visits")
async def list_patient_visits(
    clinic_id: UUID, patient_id: UUID,
    membership = Depends(get_current_membership),
):
    """病人就診歷史。"""
    # TODO Sprint 2
    return {"items": [], "_stub": True}


@router.get("/clinics/{clinic_id}/visits/{visit_id}")
async def get_visit(clinic_id: UUID, visit_id: UUID, membership = Depends(get_current_membership)):
    """取得 visit 完整資料。"""
    # TODO Sprint 2
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/visits/{visit_id}")
async def update_visit(
    clinic_id: UUID, visit_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    """修改 visit（doctor only，限 status=draft）。"""
    # TODO Sprint 2
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/visits/{visit_id}/complete")
async def complete_visit(
    clinic_id: UUID, visit_id: UUID,
    membership = Depends(require_role("doctor", "owner")),
):
    """
    完成就診（W-3）：
    - prescription.status = confirmed
    - visit.status = ready_for_billing
    - 建立 invoice draft
    - 不扣庫存
    """
    # TODO Sprint 4
    return {"_stub": True}


@router.post("/clinics/{clinic_id}/visits/{visit_id}/void")
async def void_visit(
    clinic_id: UUID, visit_id: UUID,
    membership = Depends(require_role("owner")),
):
    """作廢 visit（owner only，要 reason）。"""
    # TODO Sprint 5
    return {"_stub": True}
