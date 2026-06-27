"""
============================================================
routes/sentinel_drugs.py -- Phase 7.4 Drug list/search (處方選單)
============================================================
司機 6/28 反饋: 新就診頁 Rx 寫入要支援分類選單 (退燒/止痛/抗生素/...) +
type-ahead 搜尋 (brand name 或學名).

Endpoint:
- GET /v1/sentinel/drugs/categories            列出 14 分類 + 每類 count
- GET /v1/sentinel/drugs?category=&q=&limit=   list drugs by category /
                                               type-ahead search by name/code

dev-bypass-safe, 不依賴 firebase auth.
============================================================
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Drug

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Schemas
# ============================================================
class DrugItem(BaseModel):
    id: str
    code: str
    name: str
    unit: str
    category: str | None = None
    unit_price: float = 0


class DrugListResponse(BaseModel):
    items: list[DrugItem]
    total: int
    category_filter: str | None = None
    q_filter: str | None = None


class CategoryItem(BaseModel):
    category: str
    count: int


class CategoryListResponse(BaseModel):
    items: list[CategoryItem]
    total_drugs: int


# ============================================================
# Endpoints
# ============================================================
@router.get("/sentinel/drugs/categories", response_model=CategoryListResponse)
def list_drug_categories(db: Session = Depends(get_db)):
    """所有分類 + 該類 drug count, 給 NewVisitPage 分類 dropdown 用."""
    rows = db.execute(
        select(Drug.category, func.count(Drug.id))
        .where(Drug.status == "active")
        .where(Drug.category.is_not(None))
        .group_by(Drug.category)
        .order_by(func.count(Drug.id).desc(), Drug.category)
    ).all()
    items = [CategoryItem(category=r[0], count=r[1]) for r in rows]
    total = sum(r[1] for r in rows)
    return CategoryListResponse(items=items, total_drugs=total)


@router.get("/sentinel/drugs", response_model=DrugListResponse)
def list_drugs(
    category: Optional[str] = Query(default=None, description="分類過濾"),
    q: str = Query(default="", description="type-ahead 搜尋 name/code"),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    """List drugs by category + type-ahead search.

    Examples:
      /sentinel/drugs?category=抗生素              該類所有 drug
      /sentinel/drugs?q=azithro                    搜學名
      /sentinel/drugs?q=Norvasc                    搜 brand name
      /sentinel/drugs?category=胃藥&q=ome          類 + 搜尋
    """
    stmt = select(Drug).where(Drug.status == "active")
    if category:
        stmt = stmt.where(Drug.category == category)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            Drug.name.ilike(like),
            Drug.code.ilike(like),
        ))
    stmt = stmt.order_by(Drug.category, Drug.name).limit(limit)
    drugs = db.scalars(stmt).all()

    return DrugListResponse(
        items=[
            DrugItem(
                id=str(d.id),
                code=d.code,
                name=d.name,
                unit=d.unit,
                category=d.category,
                unit_price=float(d.unit_price or 0),
            )
            for d in drugs
        ],
        total=len(drugs),
        category_filter=category,
        q_filter=q.strip() or None,
    )
