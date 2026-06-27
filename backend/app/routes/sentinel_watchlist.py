"""
============================================================
routes/sentinel_watchlist.py -- Phase 7.2 AI 反訓練醫生 watchlist
============================================================
Track 1 MemoryAgent narrative 強化: 醫師 Mode B 回顧時把學到的盲點
「加進我的 watchlist」, 下次新就診時 banner 提醒。

Endpoint:
- POST   /v1/sentinel/watchlist             add lesson
- GET    /v1/sentinel/watchlist             list (filter doctor_user_id, is_dismissed=false)
- DELETE /v1/sentinel/watchlist/{id}        dismiss
- POST   /v1/sentinel/watchlist/{id}/trigger  triggered_count + 1 (新就診撞到該 lesson 時)
============================================================
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    Clinic,
    DoctorWatchlist,
    User,
    Visit,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _default_doctor(db: Session) -> User:
    """demo 模式: 沒帶 doctor_user_id 就取第一個 user."""
    u = db.scalars(select(User).order_by(User.created_at).limit(1)).first()
    if not u:
        raise HTTPException(status_code=500, detail="No user in DB")
    return u


def _default_clinic(db: Session) -> Clinic:
    c = db.scalars(select(Clinic).order_by(Clinic.created_at).limit(1)).first()
    if not c:
        raise HTTPException(status_code=500, detail="No clinic in DB")
    return c


# ============================================================
# Schemas
# ============================================================
class WatchlistAddRequest(BaseModel):
    pattern: str = Field(..., min_length=2, max_length=200)
    lesson_text: str = Field(..., min_length=2)
    source_visit_id: UUID | None = None
    source_mode: str = Field(default="hindsight", pattern="^(hindsight|at_the_time)$")
    doctor_user_id: UUID | None = None   # demo 不帶就 default first user


class WatchlistItem(BaseModel):
    id: UUID
    doctor_user_id: UUID
    source_visit_id: UUID | None = None
    source_mode: str
    pattern: str
    lesson_text: str
    triggered_count: int
    created_at: str


class WatchlistListResponse(BaseModel):
    items: list[WatchlistItem]
    total: int
    doctor_user_id: UUID


# ============================================================
# Endpoints
# ============================================================
@router.post(
    "/sentinel/watchlist",
    response_model=WatchlistItem,
    status_code=status.HTTP_201_CREATED,
)
def add_watchlist(payload: WatchlistAddRequest, db: Session = Depends(get_db)):
    """醫師加進個人 watchlist (Mode B review 完按按鈕觸發)."""
    doctor = (
        db.get(User, payload.doctor_user_id) if payload.doctor_user_id else _default_doctor(db)
    )
    if not doctor:
        raise HTTPException(404, "doctor_user_id not found")

    clinic = _default_clinic(db)

    # 防重複: 同 doctor + 同 pattern + active -> skip add, 回既有
    existing = db.scalars(
        select(DoctorWatchlist).where(
            DoctorWatchlist.doctor_user_id == doctor.id,
            DoctorWatchlist.pattern == payload.pattern,
            DoctorWatchlist.is_dismissed.is_(False),
        )
    ).first()
    if existing:
        # 不重複加, 但更新 lesson_text (可能 AI 改了) + 視為一次 trigger
        existing.lesson_text = payload.lesson_text
        existing.triggered_count = (existing.triggered_count or 0) + 1
        db.commit()
        return WatchlistItem(
            id=existing.id,
            doctor_user_id=existing.doctor_user_id,
            source_visit_id=existing.source_visit_id,
            source_mode=existing.source_mode,
            pattern=existing.pattern,
            lesson_text=existing.lesson_text,
            triggered_count=existing.triggered_count,
            created_at=existing.created_at.isoformat() if existing.created_at else "",
        )

    item = DoctorWatchlist(
        id=uuid4(),
        clinic_id=clinic.id,
        doctor_user_id=doctor.id,
        source_visit_id=payload.source_visit_id,
        source_mode=payload.source_mode,
        pattern=payload.pattern,
        lesson_text=payload.lesson_text,
        triggered_count=0,
        is_dismissed=False,
        source="manual",
        is_demo_data=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return WatchlistItem(
        id=item.id,
        doctor_user_id=item.doctor_user_id,
        source_visit_id=item.source_visit_id,
        source_mode=item.source_mode,
        pattern=item.pattern,
        lesson_text=item.lesson_text,
        triggered_count=item.triggered_count,
        created_at=item.created_at.isoformat() if item.created_at else "",
    )


@router.get("/sentinel/watchlist", response_model=WatchlistListResponse)
def list_watchlist(
    doctor_user_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    """列出該醫師的 active watchlist (新就診頁 banner 用)."""
    doctor = db.get(User, doctor_user_id) if doctor_user_id else _default_doctor(db)
    if not doctor:
        raise HTTPException(404, "doctor not found")

    items = db.scalars(
        select(DoctorWatchlist)
        .where(
            DoctorWatchlist.doctor_user_id == doctor.id,
            DoctorWatchlist.is_dismissed.is_(False),
        )
        .order_by(DoctorWatchlist.created_at.desc())
    ).all()

    return WatchlistListResponse(
        items=[
            WatchlistItem(
                id=w.id,
                doctor_user_id=w.doctor_user_id,
                source_visit_id=w.source_visit_id,
                source_mode=w.source_mode,
                pattern=w.pattern,
                lesson_text=w.lesson_text,
                triggered_count=w.triggered_count,
                created_at=w.created_at.isoformat() if w.created_at else "",
            )
            for w in items
        ],
        total=len(items),
        doctor_user_id=doctor.id,
    )


@router.delete("/sentinel/watchlist/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_watchlist(watchlist_id: UUID, db: Session = Depends(get_db)):
    """醫師關掉 watchlist 條目 (soft delete via is_dismissed=true)."""
    item = db.get(DoctorWatchlist, watchlist_id)
    if not item:
        raise HTTPException(404, f"Watchlist {watchlist_id} not found")
    item.is_dismissed = True
    db.commit()


@router.post("/sentinel/watchlist/{watchlist_id}/trigger", response_model=WatchlistItem)
def trigger_watchlist(watchlist_id: UUID, db: Session = Depends(get_db)):
    """新就診撞到該 lesson 時, triggered_count + 1 (demo「越用越聰明」加分)."""
    item = db.get(DoctorWatchlist, watchlist_id)
    if not item:
        raise HTTPException(404, f"Watchlist {watchlist_id} not found")
    item.triggered_count = (item.triggered_count or 0) + 1
    db.commit()
    db.refresh(item)
    return WatchlistItem(
        id=item.id,
        doctor_user_id=item.doctor_user_id,
        source_visit_id=item.source_visit_id,
        source_mode=item.source_mode,
        pattern=item.pattern,
        lesson_text=item.lesson_text,
        triggered_count=item.triggered_count,
        created_at=item.created_at.isoformat() if item.created_at else "",
    )
