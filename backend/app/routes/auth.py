"""
============================================================
routes/auth.py
============================================================
身份驗證與 user / clinic membership 管理（Sprint 1 完整版）。

對應 docs/API_SPEC.md §1：
- POST /auth/session   ← 登入後第一個呼叫，建立/更新 user
- GET  /me             ← 拿當前 user 資訊
- GET  /me/clinics     ← 拿當前 user 屬於的所有診所
============================================================
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.clinic_membership import ClinicMembership
from app.models.user import User
from app.schemas.auth_schemas import (
    AuthSessionResponse,
    ClinicResponse,
    MembershipResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# POST /auth/session
# ============================================================
@router.post("/auth/session", response_model=AuthSessionResponse)
def create_session(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthSessionResponse:
    """
    登入後第一個呼叫的 endpoint。

    流程：
    1. get_current_user 已經完成 token 驗證 + auto-create user
    2. 這裡只負責查 user 屬於的所有 active clinics 並回傳

    is_first_login 的判斷：
    - User created_at 與當前時間差 < 5 秒 → 視為第一次登入
    - 主要給前端做引導用（顯示歡迎畫面、引導建立第一間診所）
    """
    # 查 active memberships，joinedload 一起把 clinic 撈進來避免 N+1
    memberships = (
        db.query(ClinicMembership)
        .options(joinedload(ClinicMembership.clinic))
        .filter(
            ClinicMembership.user_id == user.id,
            ClinicMembership.is_active.is_(True),
        )
        .all()
    )

    # 判斷是否是第一次登入（簡單用時間差判斷）
    now = datetime.now(timezone.utc)
    is_first_login = (now - user.created_at).total_seconds() < 5

    logger.info(
        "Session created: user=%s clinics=%d first_login=%s",
        user.id, len(memberships), is_first_login,
    )

    return AuthSessionResponse(
        user=UserResponse.model_validate(user),
        memberships=[
            MembershipResponse(
                id=m.id,
                clinic_id=m.clinic_id,
                role=m.role,
                custom_permissions_json=m.custom_permissions_json,
                is_active=m.is_active,
                clinic=ClinicResponse.model_validate(m.clinic),
            )
            for m in memberships
        ],
        is_first_login=is_first_login,
    )


# ============================================================
# GET /me
# ============================================================
@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """
    拿當前 user 資訊。

    用途：前端定期 refresh user 狀態（例如顯示在右上角頭像區）
    """
    return UserResponse.model_validate(user)


# ============================================================
# GET /me/clinics
# ============================================================
@router.get("/me/clinics", response_model=list[MembershipResponse])
def list_my_clinics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MembershipResponse]:
    """
    拿當前 user 屬於的所有 active clinics（含 membership 資訊）。

    用途：
    - 前端 /select-clinic 頁面顯示診所列表給 user 選擇
    - 切換診所時重新拉取
    """
    memberships = (
        db.query(ClinicMembership)
        .options(joinedload(ClinicMembership.clinic))
        .filter(
            ClinicMembership.user_id == user.id,
            ClinicMembership.is_active.is_(True),
        )
        .order_by(ClinicMembership.created_at.asc())
        .all()
    )

    return [
        MembershipResponse(
            id=m.id,
            clinic_id=m.clinic_id,
            role=m.role,
            custom_permissions_json=m.custom_permissions_json,
            is_active=m.is_active,
            clinic=ClinicResponse.model_validate(m.clinic),
        )
        for m in memberships
    ]
