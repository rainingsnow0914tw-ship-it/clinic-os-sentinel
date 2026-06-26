"""
============================================================
scripts/reset_dev_data.py
============================================================
清除 dev / sandbox 的示範資料，讓 seed 可以重來。

⚠️ 商業底線（讀三遍）：
1. 只允許在 ENVIRONMENT in {dev, sandbox, development} 跑
2. 只刪 is_demo_data=True AND source='mock' 的資料（雙重守門）
3. 永遠不碰 clinics / users / clinic_memberships / audit_logs
   （這些是『環境/身份』，不是 demo 資料）
4. 整體在一個 transaction，失敗 rollback

跑法：
    cd backend
    ENVIRONMENT=dev python -m scripts.reset_dev_data

預設會印確認訊息 + 倒數，要 --yes 才直接執行。
============================================================
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from sqlalchemy import and_, delete
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import (
    SOURCE_MOCK,
    Drug,
    DrugBatch,
    Invoice,
    InvoiceItem,
    Patient,
    Prescription,
    PrescriptionItem,
    StockMovement,
    Visit,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ALLOWED_ENVIRONMENTS = {"dev", "sandbox", "development"}


# ============================================================
# 環境守門
# ============================================================
def assert_dev_environment() -> str:
    env = os.environ.get("ENVIRONMENT", "").lower().strip()
    if env not in ALLOWED_ENVIRONMENTS:
        logger.error("─" * 60)
        logger.error("❌ 拒絕執行 reset_dev_data")
        logger.error("─" * 60)
        logger.error("ENVIRONMENT 變數 = %r", env or "（未設定）")
        logger.error(
            "reset_dev_data 只允許在以下環境跑：%s",
            sorted(ALLOWED_ENVIRONMENTS),
        )
        logger.error("─" * 60)
        sys.exit(1)
    return env


# ============================================================
# 主流程
# ============================================================
# 刪除順序（從 child 到 parent，避免 FK 違反）
# ⚠️ 順序不能換 — InvoiceItem 必須先刪，否則 Invoice 刪不了
DELETE_ORDER = [
    InvoiceItem,
    Invoice,
    StockMovement,
    PrescriptionItem,
    Prescription,
    Visit,
    DrugBatch,
    Drug,
    Patient,
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset Clinic OS dev mock data")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="跳過確認倒數，直接執行（CI / 自動化用）",
    )
    args = parser.parse_args()

    env = assert_dev_environment()
    logger.info("🟢 ENVIRONMENT=%s — reset 允許執行", env)

    # 確認倒數
    if not args.yes:
        logger.info("─" * 60)
        logger.info("⚠️  即將刪除所有符合下列條件的資料：")
        logger.info("    is_demo_data = TRUE")
        logger.info("    AND source   = 'mock'")
        logger.info("")
        logger.info("clinics / users / clinic_memberships / audit_logs 不會被動。")
        logger.info("")
        logger.info("3 秒後執行（Ctrl+C 取消）...")
        logger.info("─" * 60)
        try:
            for i in range(3, 0, -1):
                logger.info("  %d ...", i)
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️  已取消。")
            return 130

    db: Session = SessionLocal()
    try:
        stats = _reset(db)
        db.commit()

        logger.info("─" * 60)
        logger.info("🧹 Reset 完成")
        logger.info("─" * 60)
        for table_name, count in stats.items():
            logger.info("  %-22s - %d 筆", table_name, count)
        logger.info("─" * 60)
        return 0
    except Exception as exc:
        db.rollback()
        logger.error("❌ Reset 失敗，整體 rollback: %s", exc, exc_info=True)
        return 1
    finally:
        db.close()


def _reset(db: Session) -> dict[str, int]:
    """執行刪除。每張表都加 (is_demo_data=True AND source='mock') 雙重守門。"""
    stats: dict[str, int] = {}

    for model in DELETE_ORDER:
        # 雙重 WHERE 子句：is_demo_data=True AND source='mock'
        # 用 returning 拿到刪了多少筆
        # SQLAlchemy 2.x：用 delete().where(...) 然後 db.execute()
        stmt = delete(model).where(
            and_(
                model.is_demo_data.is_(True),
                model.source == SOURCE_MOCK,
            )
        )
        result = db.execute(stmt)
        stats[model.__tablename__] = result.rowcount or 0
        logger.info(
            "  刪除 %-22s %d 筆",
            model.__tablename__,
            stats[model.__tablename__],
        )

    return stats


if __name__ == "__main__":
    sys.exit(main())
