"""
Clinic model — 診所主檔（multi-tenant 的 root）

設計重點：
1. 系統第一天就是 multi-tenant 架構，所有業務資料都會 reference 這個 id
2. receipt_header / logo_url / timezone / currency 是「診所層級」的設定
   讓不同診所可以有自己的收據抬頭、貨幣、時區
3. 不放 owner_user_id 在這裡（owner 用 ClinicMembership.role='owner' 表示，
   而且可能有多個 owner，避免 single-owner 假設）
"""

import uuid
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Clinic(Base, TimestampMixin):
    __tablename__ = "clinics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    # 診所名字（中英都可，用 String 200 應該夠）
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 地址、電話、email：診所基本資料，會印在收據抬頭
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # 收據抬頭文字（可獨立於 name，例如有些診所收據要印不同名字）
    receipt_header: Mapped[str | None] = mapped_column(Text, nullable=True)

    # logo URL：通常是 GCS 公開讀的 signed URL 或公開連結
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 時區，用 IANA 字串（例如 'Asia/Macau', 'Asia/Taipei'）
    # 預設給澳門，因為 Chloe 在澳門；其他診所建立時可以改
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="Asia/Macau",
    )

    # 貨幣代碼，ISO 4217（MOP=澳門幣, HKD=港幣, TWD=新台幣...）
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        server_default="MOP",
    )

    # 反向關聯：一間診所有多個 membership（員工）
    memberships: Mapped[list["ClinicMembership"]] = relationship(
        "ClinicMembership",
        back_populates="clinic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Clinic id={self.id} name={self.name}>"
