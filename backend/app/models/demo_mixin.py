"""
============================================================
models/demo_mixin.py
============================================================
給業務表加上 demo data tracking 欄位的 mixin。

每個繼承 DemoDataMixin 的 table 都會有：
- source: 資料來源（'manual' / 'mock' / 'import' / 'agent'）
- is_demo_data: 是否是示範資料（True 才能被 reset_dev_data.py 清掉）

設計重點：
1. clinics / users / clinic_memberships / audit_logs 不用這個 mixin
   （這些是『環境/身份』資料，不是『業務』資料）
2. 第一次 seed 進來的資料：source='mock', is_demo_data=True
3. 之後使用者輸入的資料：source='manual', is_demo_data=False
4. 之後 import 進來的資料：source='import', is_demo_data=False
5. AI Agent 寫的資料：source='agent', is_demo_data=False
6. (clinic_id, is_demo_data) 加 composite index 方便 reset 快速找
   ⚠️ 這個 index 在子類別的 __table_args__ 裡加，因為要用到 clinic_id

⚠️ 商業底線第 11 條的延伸：reset_dev_data.py 永遠只刪
   `is_demo_data=True AND source='mock'` 的資料，雙重保險。
============================================================
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


# 合法的 source 值（程式內常數，避免 typo）
SOURCE_MANUAL = "manual"
SOURCE_MOCK = "mock"
SOURCE_IMPORT = "import"
SOURCE_AGENT = "agent"
VALID_SOURCES = {SOURCE_MANUAL, SOURCE_MOCK, SOURCE_IMPORT, SOURCE_AGENT}


class DemoDataMixin:
    """
    給業務 entity 加上『可被 reset 安全清除』的能力。

    用法：
        class Patient(Base, TimestampMixin, DemoDataMixin):
            __tablename__ = "patients"
            ...
    """

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=SOURCE_MANUAL,
    )

    is_demo_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        index=True,
    )
