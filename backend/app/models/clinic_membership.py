"""
ClinicMembership — 使用者在某間診所的身份

這是整個權限系統的核心 join table。

設計重點（規格 §2、§3）：
1. 一個 user 可屬於多間 clinic（同一個 user_id 在 clinic_memberships 表可以有多筆）
2. role 是粗粒度（owner / doctor / nurse / reception）
3. custom_permissions 是細粒度，可以在預設角色上加開（或關閉）特定權限
   範例：一個 reception 被 owner 額外授權 can_manage_inventory=true
4. (clinic_id, user_id) 組合唯一（同一個人在同一間診所只能有一個 active membership）
5. is_active 用來停用，不真的刪除（保留 audit log 連結用）

⚠️ 權限檢查邏輯（會放在 middleware/clinic_permission.py）：
   - role='owner' → 所有權限預設允許（除非 custom_permissions 明確設 false）
   - 其他 role → 用預設權限矩陣 + custom_permissions 覆蓋
"""

import uuid
from enum import Enum
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ClinicRole(str, Enum):
    """
    診所內的角色枚舉

    用 str + Enum 讓 Pydantic / FastAPI 可以直接序列化成字串，
    存進 DB 時也是 'owner', 'doctor' 這種人類可讀的值
    """
    OWNER = "owner"          # 老闆 / 最大管理員
    DOCTOR = "doctor"        # 醫生
    NURSE = "nurse"          # 護士
    RECEPTION = "reception"  # 前台


class ClinicMembership(Base, TimestampMixin):
    __tablename__ = "clinic_memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    # 對應到哪間診所（多租戶隔離的根）
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 對應到哪個使用者
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 角色（用字串而不是 PG enum，方便之後增減值不需要 migration）
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # 細粒度權限覆蓋
    # 範例 JSON：
    # {
    #   "can_manage_inventory": true,
    #   "can_view_revenue_report": true,
    #   "can_manage_users": false,
    #   "can_void_invoice": true
    # }
    # 用 JSONB 而不是 JSON，PostgreSQL JSONB 支援索引和高效查詢
    custom_permissions_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    # 是否生效。停用員工時改成 False，不要 DELETE
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    # ORM 雙向關聯
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="memberships")

    __table_args__ = (
        # 同一個人在同一間診所只能有一個 membership
        # 即使 is_active=False 也算佔位（避免重複邀請造成多筆殘留）
        UniqueConstraint("clinic_id", "user_id", name="uq_clinic_membership"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClinicMembership clinic={self.clinic_id} "
            f"user={self.user_id} role={self.role} active={self.is_active}>"
        )
