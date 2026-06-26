"""
============================================================
models/heart_layer_snapshot.py -- 心臟層快照 (v0.3 新增,Mode A 依賴)
============================================================
對應 v0.3.1 設計 §8.4: Mode A「當時可獲得的資訊重審」需要
回放過去任意 visit 開始時的心臟層狀態。

心臟 4 表 (patient_problems / patient_medications / patient_flags
/ patient_baselines) 是 mutable,會隨 visit 演進。snapshot 表把
每次 visit 開始 + 完成各拍一張照,serialize 整個心臟層當下狀態。

觸發時機:
- visit 建立        -> snapshot_type='before_visit'
- visit 完成        -> snapshot_type='after_visit'
                       接著跑 evolve_heart_layer_after_visit() (§7.1)

demo seed 用法:
- seed_heart_layer.py 依序 replay 100 病人的歷次 visit,backfill
  每 visit 的 before_visit snapshot
============================================================
"""

import uuid
from typing import Literal

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.demo_mixin import DemoDataMixin


SnapshotType = Literal["before_visit", "after_visit"]


class HeartLayerSnapshot(Base, TimestampMixin, DemoDataMixin):
    __tablename__ = "heart_layer_snapshots"

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

    snapshot_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # 4 心臟表當下序列化
    problems_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    medications_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    flags_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    baselines_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # ContextPack 用的 plain text summary
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<HeartLayerSnapshot id={self.id} visit_id={self.visit_id} type={self.snapshot_type}>"
