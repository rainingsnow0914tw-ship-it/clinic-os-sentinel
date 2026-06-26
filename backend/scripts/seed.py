"""
============================================================
scripts/seed.py
============================================================
建立第一間診所與第一個 owner。

何時跑：
- 第一次部署完，alembic upgrade head 之後
- 跑一次就夠了；如果跑第二次會偵測到已存在的 user，更新 membership 而不重建

跑法：
    cd backend
    source .venv/bin/activate
    python -m scripts.seed \
      --clinic-name "心晴診所" \
      --owner-email "chloe@example.com" \
      --owner-name "Chloe" \
      --firebase-uid "<可選，省略則之後 first-login 時自動填>"

設計重點：
1. 不從 .env 讀 owner email（一定要 CLI 帶，避免敏感資訊 leak）
2. 如果 firebase_uid 不提供，建立一個 placeholder user
   等該 owner 第一次用 Google 登入時，middleware 會走「email 已存在但 uid 不同」
   分支 → 改用「拿 email 找到 placeholder user，更新 firebase_uid」邏輯
   ⚠️ 這個 reclaim 邏輯目前 auth middleware 還沒做（會回 409）
   → V1 建議直接帶上 firebase_uid，避免邊緣情境
3. 一定建立成 owner role（role=owner）
============================================================
"""

import argparse
import logging
import sys
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.clinic import Clinic
from app.models.clinic_membership import ClinicMembership, ClinicRole
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def seed_first_clinic(
    db: Session,
    *,
    clinic_name: str,
    owner_email: str,
    owner_name: str,
    firebase_uid: Optional[str] = None,
    timezone_str: str = "Asia/Macau",
    currency: str = "MOP",
) -> tuple[Clinic, User, ClinicMembership]:
    """
    建立第一間診所與第一個 owner。

    回傳 (Clinic, User, ClinicMembership)
    """
    # ─── Step 1: 找 / 建 user ───────────────────────────
    user = db.query(User).filter(User.email == owner_email).first()

    if user is None:
        # 沒給 firebase_uid 時用 placeholder；之後 reclaim 時會更新
        # placeholder 用 'pending:' 前綴避免跟真實 uid 撞
        if not firebase_uid:
            firebase_uid = f"pending:{owner_email}"
            logger.warning(
                "未提供 firebase_uid，使用 placeholder=%s。"
                "owner 第一次登入時可能需要手動關聯。",
                firebase_uid,
            )

        user = User(
            firebase_uid=firebase_uid,
            email=owner_email,
            name=owner_name,
            status="active",
        )
        db.add(user)
        db.flush()
        logger.info("✓ 建立 user: id=%s email=%s", user.id, user.email)
    else:
        logger.info("✓ user 已存在: id=%s email=%s（沿用）", user.id, user.email)
        # 如果現有 user 是 placeholder 且這次有給 firebase_uid，更新它
        if firebase_uid and user.firebase_uid.startswith("pending:"):
            old_uid = user.firebase_uid
            user.firebase_uid = firebase_uid
            db.flush()
            logger.info("  ↳ 更新 firebase_uid: %s → %s", old_uid, firebase_uid)

    # ─── Step 2: 建 clinic ──────────────────────────────
    # 不檢查 clinic name 重複（不同診所同名是正常情境）
    clinic = Clinic(
        name=clinic_name,
        timezone=timezone_str,
        currency=currency,
    )
    db.add(clinic)
    db.flush()
    logger.info("✓ 建立 clinic: id=%s name=%s", clinic.id, clinic.name)

    # ─── Step 3: 建 owner membership ────────────────────
    # 用 (clinic_id, user_id) unique constraint 防呆
    existing = (
        db.query(ClinicMembership)
        .filter(
            ClinicMembership.clinic_id == clinic.id,
            ClinicMembership.user_id == user.id,
        )
        .first()
    )
    if existing is not None:
        # 不應該發生（clinic 是新建的），但保險起見
        logger.warning("Membership 已存在，沿用: id=%s", existing.id)
        membership = existing
    else:
        membership = ClinicMembership(
            clinic_id=clinic.id,
            user_id=user.id,
            role=ClinicRole.OWNER.value,
            custom_permissions_json={},
            is_active=True,
        )
        db.add(membership)
        db.flush()
        logger.info(
            "✓ 建立 owner membership: id=%s role=%s",
            membership.id, membership.role,
        )

    return clinic, user, membership


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clinic OS — 建立第一間診所與第一個 owner",
    )
    parser.add_argument("--clinic-name", required=True, help="診所名稱")
    parser.add_argument("--owner-email", required=True, help="owner 的 email")
    parser.add_argument("--owner-name", required=True, help="owner 的顯示名")
    parser.add_argument(
        "--firebase-uid",
        default=None,
        help="owner 的 Firebase UID（建議帶上）",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Macau",
        help="診所時區（IANA 格式，預設 Asia/Macau）",
    )
    parser.add_argument(
        "--currency",
        default="MOP",
        help="診所貨幣（ISO 4217，預設 MOP）",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        clinic, user, membership = seed_first_clinic(
            db,
            clinic_name=args.clinic_name,
            owner_email=args.owner_email,
            owner_name=args.owner_name,
            firebase_uid=args.firebase_uid,
            timezone_str=args.timezone,
            currency=args.currency,
        )
        db.commit()
        logger.info("─" * 60)
        logger.info("🎉 完成！")
        logger.info("Clinic ID: %s", clinic.id)
        logger.info("User ID:   %s", user.id)
        logger.info("Membership ID: %s", membership.id)
        logger.info("─" * 60)
        logger.info(
            "下一步：用 owner email (%s) 透過 Firebase Google Sign-In 登入，"
            "auth middleware 會 link 起來。",
            args.owner_email,
        )
        return 0
    except Exception as exc:
        db.rollback()
        logger.error("❌ Seed 失敗，已 rollback: %s", exc, exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
