"""
AuditLog — 所有重要操作的紀錄

規格 §14 商業底線第 14 條：「所有重要行為寫 audit_logs」

設計重點：
1. append-only：永遠只 INSERT，不 UPDATE 也不 DELETE
2. clinic_id 必填（多租戶隔離）；user_id 可空（系統觸發的也要記）
3. old_value_json / new_value_json 用 JSONB 存任意結構的 before/after 快照
4. 不靠 ORM cascade，而是由 service layer 主動寫 log
   （這樣才能保證每個關鍵動作都被記下，不會因為 ORM bug 漏掉）

⚠️ 注意：audit_logs 沒有 updated_at（append-only），所以不用 TimestampMixin
"""

import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    # 哪間診所的事件
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # 哪個 user 觸發。可空 → 系統觸發（cron job、agent task）
    # 用 SET NULL 而不是 CASCADE：使用者被刪除時 audit log 還是要留著
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 動作字串，例如 'patient.create', 'visit.complete', 'invoice.void'
    # 用 dot-separated 命名讓未來容易做 prefix 查詢與權限對照
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # 被影響的 entity 類型（'patient', 'visit', 'prescription'...）
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # 被影響的 entity 主鍵（用 String 而非 UUID，因為某些事件的 entity 可能不是 UUID）
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # 修改前 / 修改後的 JSON 快照
    old_value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 來源 IP（用 PG 原生 INET type 比 String 省空間且支援子網查詢）
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    # User-Agent，方便後續分析或抓異常
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 用 server_default + index：append-only 表通常按時間查
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action} "
            f"entity={self.entity_type}:{self.entity_id}>"
        )
