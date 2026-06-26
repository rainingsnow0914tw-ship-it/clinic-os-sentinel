"""
============================================================
routes/reports.py — 基本報表
詳見 docs/API_SPEC.md §12
============================================================
"""
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query
from app.middleware.clinic_permission import get_current_membership, require_permission

router = APIRouter()


@router.get("/clinics/{clinic_id}/reports/daily-revenue")
async def daily_revenue(
    clinic_id: UUID,
    date: date = Query(...),
    membership = Depends(require_permission("can_view_revenue_report")),
):
    # TODO Sprint 5+
    return {"_stub": True}


@router.get("/clinics/{clinic_id}/reports/low-stock")
async def low_stock(clinic_id: UUID, membership = Depends(get_current_membership)):
    # TODO Sprint 3
    return {"items": [], "_stub": True}


@router.get("/clinics/{clinic_id}/reports/expiring-soon")
async def expiring_soon(
    clinic_id: UUID,
    within_days: int = 90,
    membership = Depends(get_current_membership),
):
    # TODO Sprint 3
    return {"items": [], "_stub": True}


@router.get("/clinics/{clinic_id}/reports/audit-logs")
async def audit_logs(clinic_id: UUID, membership = Depends(require_permission("can_view_audit_logs"))):
    # TODO Sprint 1
    return {"items": [], "_stub": True}
