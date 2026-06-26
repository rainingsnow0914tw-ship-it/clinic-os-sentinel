"""
User model — 系統使用者

設計重點：
1. user 本身不綁定 clinic（一個醫生可在多間診所工作 → ADR multi-tenant）
2. firebase_uid 是登入身份來源，唯一索引
3. 是否能進某間診所、能做什麼，由 ClinicMembership 決定，不是 User 本身
4. status 欄位用來停用使用者（軟刪除），不用 DELETE FROM users
"""

import uuid
from sqlalchemy import String, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # UUID v4 primary key（ADR-003）
    # server_default 使用 PostgreSQL 的 gen_random_uuid()，需要先安裝 pgcrypto extension
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    # Firebase Auth 的 UID，登入時用來查 user
    # unique=True 確保一個 Firebase 帳號對應一個 user
    firebase_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    # 顯示名稱，可被 user 自己更新
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # email 全系統唯一（用來邀請、找回帳號）
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        nullable=False,
        index=True,
    )

    # 電話可選；不設 unique（不同診所員工可能用同一支電話的情境少見但不限制）
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 帳號狀態：active / suspended / deleted
    # deleted 是軟刪除標記，不真的 DROP ROW
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
    )

    # 反向關聯：一個 user 可能屬於多間診所
    memberships: Mapped[list["ClinicMembership"]] = relationship(
        "ClinicMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # 限制 status 只能是這三種，DB 層擋住非法值
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'deleted')",
            name="ck_users_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} status={self.status}>"
