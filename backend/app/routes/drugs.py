"""
============================================================
routes/drugs.py — 藥品主檔、批號、庫存異動
詳見 docs/API_SPEC.md §5 與 docs/WORKFLOWS.md W-10, W-11
============================================================
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.middleware.clinic_permission import (
    get_current_membership, require_role, require_permission,
)

router = APIRouter()


# === Drugs（主檔） ===
@router.get("/clinics/{clinic_id}/drugs")
async def list_drugs(
    clinic_id: UUID, q: str = "", active: bool = True,
    membership = Depends(get_current_membership),
):
    # TODO Sprint 3
    return {"items": [], "_stub": True}


@router.post("/clinics/{clinic_id}/drugs")
async def create_drug(
    clinic_id: UUID,
    membership = Depends(require_permission("can_manage_inventory")),
):
    # TODO Sprint 3
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/drugs/{drug_id}")
async def update_drug(
    clinic_id: UUID, drug_id: UUID,
    membership = Depends(require_permission("can_manage_inventory")),
):
    # TODO Sprint 3
    return {"_stub": True}


# === Drug Batches（批號庫存） ===
@router.get("/clinics/{clinic_id}/drug-batches")
async def list_batches(
    clinic_id: UUID,
    drug_id: UUID | None = None,
    expiring_within_days: int | None = None,
    membership = Depends(get_current_membership),
):
    # TODO Sprint 3
    return {"items": [], "_stub": True}


@router.post("/clinics/{clinic_id}/drug-batches")
async def create_batch(
    clinic_id: UUID,
    membership = Depends(require_permission("can_manage_inventory")),
):
    """進貨：建立批號，寫 stock_movements (purchase)。"""
    # TODO Sprint 3
    return {"_stub": True}


@router.patch("/clinics/{clinic_id}/drug-batches/{batch_id}")
async def update_batch(
    clinic_id: UUID, batch_id: UUID,
    membership = Depends(require_permission("can_manage_inventory")),
):
    """修改批號（限定欄位，不可改 quantity）。"""
    # TODO Sprint 3
    return {"_stub": True}


# === Stock movements（ledger） ===
@router.get("/clinics/{clinic_id}/stock-movements")
async def list_stock_movements(
    clinic_id: UUID,
    drug_id: UUID | None = None,
    membership = Depends(get_current_membership),
):
    # TODO Sprint 3
    return {"items": [], "_stub": True}


@router.post("/clinics/{clinic_id}/stock-adjustments")
async def adjust_stock(
    clinic_id: UUID,
    membership = Depends(require_role("owner")),
):
    """手動調整庫存（owner only）。"""
    # TODO Sprint 3
    return {"_stub": True}
