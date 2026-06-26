"""
Alembic 環境設定

關鍵設計：
1. 從 app.core.config.settings 讀取 DATABASE_URL，不在 alembic.ini 寫死
2. import app.models 讓 Alembic 看到所有 ORM model 的 metadata
   → 之後跑 alembic revision --autogenerate 才能正確比對 schema
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 匯入專案的設定與所有 ORM models（讓 Alembic autogenerate 看得到 metadata）
from app.core.config import settings
from app.models import Base  # noqa: F401 — 讓 Base.metadata 包含所有 model

# Alembic Config 物件
config = context.config

# 把 DATABASE_URL 動態塞進 config（覆蓋 alembic.ini 的空白值）
# 注意：sync URL（不含 +asyncpg），Alembic 用同步 driver 跑 migration 比較穩
# config.py 用 UPPER_CASE 命名（pydantic-settings + case_sensitive=True 風格）
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
config.set_main_option("sqlalchemy.url", sync_url)

# 設定 logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 提供給 autogenerate 做 schema diff 的 metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """離線模式：只生成 SQL 不真的連 DB（少用）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """連線模式：實際連 DB 跑 migration（常用）"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,    # 偵測欄位 type 變更
            compare_server_default=True,  # 偵測 default 變更
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
