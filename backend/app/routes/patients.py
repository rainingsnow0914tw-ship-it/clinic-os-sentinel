"""
============================================================
routes/patients.py — 病人 CRUD
詳見 docs/API_SPEC.md §3
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.middleware.clinic_permission import get_current_membership

router = APIRouter()


@router.get("/clinics/{clinic_id}/patients")
async def list_patients(
    clinic_id: UUID,
    q: str = Query(default="", description="模糊搜尋姓名/電話/身分證"),
    page: int = 1,
    page_size: int = 20,
    membership = Depends(get_current_membership),
):
    """搜尋病人列表。"""
    # TODO Sprint 2
    return {"items": [], "meta": {"page": page, "page_size": page_size, "total": 0}, "_stub": True}


@router.post("/clinics/{clinic_id}/patients")
async def create_patient(clinic_id: UUID, membership = Depends(get_current_membership)):
    """建立病人。"""
    # TODO Sprint 2
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/patients/{patient_id}")
async def get_patient(clinic_id: UUID, patient_id: UUID, membership = Depends(get_current_membership)):
    """取得單一病人。"""
    # TODO Sprint 2
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/patients/{patient_id}")
async def update_patient(clinic_id: UUID, patient_id: UUID, membership = Depends(get_current_membership)):
    """修改病人。"""
    # TODO Sprint 2
    return {"_stub": True}
