"""
============================================================
middleware/clinic_permission.py
============================================================
診所權限檢查 dependency（Sprint 1 完整版）。

這是整個系統最重要的安全層。每個碰 clinic 資料的 endpoint 都要過。

兩種 clinic_id 來源：
1. URL path param `{clinic_id}` — 大多數 endpoint 用這個
2. Header `X-Clinic-Id` — 給沒有 path param 的 endpoint 用（例如 /me/today）

依賴關係：
    get_current_user (Firebase token)
        ↓
    get_current_membership (查 clinic_memberships 並檢查 is_active)
      ├─ 走 X-Clinic-Id header（給沒有 path param 的 endpoint 用，例如 /me/today）
      └─ 走 URL path {clinic_id}（給 /clinics/{clinic_id}/... endpoints 用）
        ↓
    require_role / require_permission (角色 / 權限 helper)

⚠️ FastAPI 的 Path() 不允許 default value，所以我們把
   「來源是 Path」和「來源是 Header」拆成兩個 dependency，
   各 endpoint 用對應的那個。

⚠️ 規格 §11 商業底線第 4 條：所有 clinic-scoped 資料都必須過 membership 檢查。
   route handler 內也要主動把查詢加上 clinic_id 過濾，雙重保險。
============================================================
"""

import logging
from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.clinic_membership import ClinicMembership, ClinicRole
from app.models.user import User

logger = logging.getLogger(__name__)


# ============================================================
# 預設權限矩陣
# ============================================================
# 每個 role 的「預設能做什麼」。
# ClinicMembership.custom_permissions_json 可以個別覆蓋（true 或 false 都可以）。
#
# 設計重點：
# - owner 永遠是 True，custom_permissions 不能把 owner 的權限關掉
#   （避免唯一 owner 把自己鎖死）
# - 其他 role 用「最小權限原則」：預設不給，需要用 custom_permissions 開
# - 鍵名與規格 §3 對齊
# ============================================================
DEFAULT_PERMISSIONS: dict[str, dict[str, bool]] = {
    "owner": {
        # owner 預設全開，這個 dict 主要當 fallback；實際邏輯走 owner-bypass
        "can_manage_users": True,
        "can_manage_clinic_settings": True,
        "can_manage_inventory": True,
        "can_view_revenue_report": True,
        "can_void_invoice": True,
        "can_void_visit": True,
        "can_manage_drug_catalog": True,
        "can_manage_fee_catalog": True,
        "can_manage_templates": True,
        "can_manage_ai_prompts": True,
        "can_approve_agent_tasks": True,
    },
    "doctor": {
        "can_manage_users": False,
        "can_manage_clinic_settings": False,
        "can_manage_inventory": False,    # 看得到，但動庫存要另外授權
        "can_view_revenue_report": False,
        "can_void_invoice": False,
        "can_void_visit": False,           # 醫生自己看的診不能自己作廢
        "can_manage_drug_catalog": False,
        "can_manage_fee_catalog": False,
        "can_manage_templates": False,
        "can_manage_ai_prompts": False,
        "can_approve_agent_tasks": False,
    },
    "nurse": {
        "can_manage_users": False,
        "can_manage_clinic_settings": False,
        "can_manage_inventory": True,      # 護士通常負責盤點 / 入庫
        "can_view_revenue_report": False,
        "can_void_invoice": False,
        "can_void_visit": False,
        "can_manage_drug_catalog": False,
        "can_manage_fee_catalog": False,
        "can_manage_templates": False,
        "can_manage_ai_prompts": False,
        "can_approve_agent_tasks": False,
    },
    "reception": {
        "can_manage_users": False,
        "can_manage_clinic_settings": False,
        "can_manage_inventory": False,
        "can_view_revenue_report": False,
        "can_void_invoice": False,         # 預設不行；可由 owner 用 custom 開啟
        "can_void_visit": False,
        "can_manage_drug_catalog": False,
        "can_manage_fee_catalog": False,
        "can_manage_templates": False,
        "can_manage_ai_prompts": False,
        "can_approve_agent_tasks": False,
    },
}


def has_permission(membership: ClinicMembership, permission_key: str) -> bool:
    """
    檢查一個 membership 是否擁有某個權限。

    解析順序：
    1. owner-bypass：role='owner' 一律允許（不受 custom_permissions 影響）
    2. custom_permissions_json 明確設值（true/false 都覆蓋預設）
    3. 預設權限矩陣
    4. 找不到 key → False（最保守）

    這樣設計的原因：
    - owner 不可能被鎖死（即使誤把自己權限關了還是能登入修）
    - custom_permissions 可雙向覆蓋，例如把 reception 的 can_void_invoice 開成 true
    - 未知 permission key 一律拒絕，避免新增權限時舊資料漏掉預設值
    """
    # 1. owner 一律過
    if membership.role == ClinicRole.OWNER.value:
        return True

    # 2. custom 覆蓋
    custom = membership.custom_permissions_json or {}
    if permission_key in custom:
        return bool(custom[permission_key])

    # 3. 預設矩陣
    role_defaults = DEFAULT_PERMISSIONS.get(membership.role, {})
    return role_defaults.get(permission_key, False)


# ============================================================
# 主 dependency：拿到當前 clinic membership
# ============================================================
def _check_membership(
    clinic_id: UUID, user: User, db: Session
) -> ClinicMembership:
    """
    共用邏輯：給定 clinic_id 與 user，檢查是否存在 active membership。

    錯誤情境：
    - 找不到 / is_active=False → 403 not_a_member（不洩漏 clinic 是否存在）
    """
    membership: Optional[ClinicMembership] = (
        db.query(ClinicMembership)
        .filter(
            ClinicMembership.clinic_id == clinic_id,
            ClinicMembership.user_id == user.id,
            ClinicMembership.is_active.is_(True),
        )
        .first()
    )

    if membership is None:
        # 不暴露「這個 clinic 是否存在」的差異（避免被掃 clinic_id）
        # 不論 clinic 不存在還是 user 不在裡面，一律回同樣的錯
        logger.warning(
            "Membership check failed: user=%s clinic=%s",
            user.id, clinic_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "not_a_member",
                    "message": "You are not a member of this clinic",
                }
            },
        )

    return membership


def get_current_membership(
    x_clinic_id: Optional[str] = Header(default=None, alias="X-Clinic-Id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClinicMembership:
    """
    從 X-Clinic-Id header 拿 clinic_id 並檢查 membership。

    用於沒有 {clinic_id} path param 的 endpoint，例如：
    - GET /v1/dashboard
    - GET /v1/me/today

    Header 沒帶 → 400 clinic_id_required
    Header 不是合法 UUID → 400 invalid_clinic_id
    """
    if not x_clinic_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "clinic_id_required",
                    "message": (
                        "This endpoint requires X-Clinic-Id header"
                    ),
                }
            },
        )

    try:
        clinic_uuid = UUID(x_clinic_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "invalid_clinic_id",
                    "message": "X-Clinic-Id header is not a valid UUID",
                }
            },
        ) from exc

    return _check_membership(clinic_uuid, user, db)


def get_current_membership_for_clinic(
    clinic_id: UUID = Path(..., description="當前操作的 clinic UUID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClinicMembership:
    """
    從 URL path 的 {clinic_id} 拿並檢查 membership。

    用於有 {clinic_id} path param 的 endpoint，例如：
    - GET /v1/clinics/{clinic_id}/patients
    - POST /v1/clinics/{clinic_id}/visits

    ⚠️ 後續 sprint 在寫 routes 時，這個 dependency 才是主力。
       Sprint 1 的 routes（/me, /me/clinics）不需要 clinic_id，所以還沒用到。
    """
    return _check_membership(clinic_id, user, db)


# ============================================================
# Helper：要求特定 role
# ============================================================
def require_role(*allowed_roles: "ClinicRole | str") -> Callable:
    """
    產生一個 dependency，限定只有指定 role 才能通過。

    用法（兩種寫法都支援）：
        Depends(require_role(ClinicRole.DOCTOR, ClinicRole.OWNER))
        Depends(require_role("doctor", "owner"))

    注意：owner 永遠在 allowed list 裡（即使 caller 沒寫進去）
    這是規格 §3：owner 是最高權限，任何受限 endpoint owner 都能進
    """
    # 同時接受字串和 enum，統一轉成字串值
    allowed_values: set[str] = set()
    for role in allowed_roles:
        if isinstance(role, ClinicRole):
            allowed_values.add(role.value)
        else:
            allowed_values.add(str(role))
    allowed_values.add(ClinicRole.OWNER.value)  # owner 永遠允許

    def _checker(
        membership: ClinicMembership = Depends(get_current_membership),
    ) -> ClinicMembership:
        if membership.role not in allowed_values:
            logger.info(
                "Role check failed: user=%s clinic=%s role=%s required=%s",
                membership.user_id, membership.clinic_id,
                membership.role, allowed_values,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "insufficient_role",
                        "message": (
                            f"Role '{membership.role}' is not allowed. "
                            f"Required: {sorted(allowed_values)}"
                        ),
                    }
                },
            )
        return membership

    return _checker


# ============================================================
# Helper：要求特定權限
# ============================================================
def require_permission(permission_key: str) -> Callable:
    """
    產生一個 dependency，要求 membership 有特定權限。

    用法：
        @router.post(
            "/clinics/{clinic_id}/invoices/{invoice_id}/void",
            dependencies=[Depends(require_permission("can_void_invoice"))],
        )

    解析邏輯參見 has_permission()：owner-bypass → custom → default。
    """

    def _checker(
        membership: ClinicMembership = Depends(get_current_membership),
    ) -> ClinicMembership:
        if not has_permission(membership, permission_key):
            logger.info(
                "Permission check failed: user=%s clinic=%s "
                "role=%s permission=%s",
                membership.user_id, membership.clinic_id,
                membership.role, permission_key,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "insufficient_permission",
                        "message": (
                            f"Permission '{permission_key}' is required"
                        ),
                    }
                },
            )
        return membership

    return _checker
