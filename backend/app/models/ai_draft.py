"""
============================================================
models/ai_draft.py -- AI draft (Phase 4.2c, ADR-006)
============================================================
AI 寫 ai_drafts → 醫師 review 後接受才入正表。

minimal 用法 (這版): 醫師按「完成就診」時, 把當下 AI panel 4 agent
response 全部 dump 進 ai_drafts (status='accepted_with_visit'),
Mode A/B 回顧時可看醫師當時看過什麼 AI 建議。

完整版 (Phase 5+): per-draft accept/dismiss + accept 時把 payload
拆解寫入對應 ORM (intake findings → patient_flags, audit risk
→ block prescription, ...)。
============================================================
"""

import uuid
from datetime import datetime
import enum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


class AgentType(str, enum.Enum):
    INTAKE = "intake"
    TRIAGE = "triage"
    AUDIT = "audit"
    EDUCATION = "education"


class AiDraftStatus(str, enum.Enum):
    PENDING = "pending"                          # 未 review
    ACCEPTED_WITH_VISIT = "accepted_with_visit"  # 醫師看過 panel 後完成就診 (minimal demo)
    ACCEPTED_TO_RECORD = "accepted_to_record"    # 醫師明確按「接受寫入正表」(Phase 5)
    DISMISSED = "dismissed"                      # 醫師看過不採納


class AiDraft(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "ai_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
    )

    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AiDraftStatus.ACCEPTED_WITH_VISIT.value,
        server_default=AiDraftStatus.ACCEPTED_WITH_VISIT.value,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AiDraft id={self.id} type={self.agent_type} status={self.status}>"
