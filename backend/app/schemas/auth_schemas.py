"""
============================================================
schemas/auth_schemas.py
============================================================
Auth 相關的 request / response schemas。

設計原則：
1. 不直接吐 ORM 物件，全部走 Pydantic 序列化
2. 不洩漏敏感欄位（例如 firebase_uid 不需要回 client）
3. 用 model_config = ConfigDict(from_attributes=True) 讓 Pydantic 能直接吃 ORM
============================================================
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


# ============================================================
# User
# ============================================================
class UserResponse(BaseModel):
    """回給前端的 user 資訊（不含 firebase_uid）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    phone: Optional[str] = None
    status: str
    created_at: datetime


# ============================================================
# Clinic
# ============================================================
class ClinicResponse(BaseModel):
    """診所基本資訊。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    receipt_header: Optional[str] = None
    logo_url: Optional[str] = None
    timezone: str
    currency: str


# ============================================================
# Membership
# ============================================================
class MembershipResponse(BaseModel):
    """
    使用者在某間診所的身份。

    /me/clinics 會回傳一個 MembershipResponse 列表，
    每筆內含 clinic 物件，前端不用額外打 API 拿診所資料。
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    role: str
    custom_permissions_json: dict
    is_active: bool
    clinic: ClinicResponse  # 透過 ORM relationship 自動帶出


# ============================================================
# /auth/session 回應
# ============================================================
class AuthSessionResponse(BaseModel):
    """
    POST /auth/session 的回應。

    用途：前端登入成功拿到 Firebase ID token 後立刻打這個 endpoint，
    讓後端建立 / 更新 user，並回傳「使用者所屬的所有 clinics」，
    前端據此決定要去 /select-clinic 還是直接進 /dashboard。
    """

    user: UserResponse
    memberships: list[MembershipResponse]
    is_first_login: bool  # 後端可選擇性告知前端「這是第一次見到這個使用者」
