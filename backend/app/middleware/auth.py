"""
============================================================
middleware/auth.py
============================================================
身份驗證 dependency（Sprint 1 完整版）。

任何需要登入的 endpoint 加 Depends(get_current_user) 即可。

流程：
1. 從 Authorization header 拿 ID token
2. 用 firebase-admin 驗證
3. 從 firebase_uid 查 users 表
4. 如果使用者不存在 → first-login 自動建立（用 Firebase token 的 email/name）
5. 已存在但 status != 'active' → 403
6. 回傳 User ORM 物件

⚠️ 規格 §11 商業底線：所有需要身份的 endpoint 都必須過這個 dependency。
   絕對不能有「沒帶 token 也能呼叫」的 protected endpoint。
============================================================
"""

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import extract_bearer_token, verify_id_token
from app.models.user import User

logger = logging.getLogger(__name__)


# ============================================================
# 主 dependency：拿到當前 user（已登入、且 status=active）
# ============================================================
def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    驗證 Firebase ID token，回傳 User ORM 物件。

    錯誤情境：
    - 沒帶 token / token 格式錯  → 401 auth_required
    - Firebase 驗證失敗（過期/無效/撤銷）→ 401 auth_required
    - User 在 DB 不存在 → 自動建立（first-time login，規格 W-0）
    - User 存在但 status != 'active' → 403 user_disabled

    用法：
        @router.get("/me")
        def me(user: User = Depends(get_current_user)):
            return user
    """
    # ─── 1. 從 header 拿 token ───────────────────────────
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "auth_required",
                    "message": "Missing bearer token",
                }
            },
        )

    # ─── 2. 驗 Firebase token ────────────────────────────
    try:
        decoded = verify_id_token(token)
    except Exception as exc:
        # 不暴露具體錯誤給 client（避免 token 內部資訊洩漏）
        # 但內部 log 寫清楚方便 debug
        logger.warning("Firebase token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "auth_required",
                    "message": "Invalid or expired token",
                }
            },
        ) from exc

    firebase_uid: str = decoded["uid"]
    # email / name 不一定都有（看 provider），盡量取
    email: str = decoded.get("email", "") or ""
    name: str = (
        decoded.get("name")
        or decoded.get("display_name")
        or (email.split("@")[0] if email else firebase_uid)
    )

    # ─── 3. 查 users 表 ─────────────────────────────────
    user: Optional[User] = (
        db.query(User).filter(User.firebase_uid == firebase_uid).first()
    )

    # ─── 4. 不存在 → first-time login 自動建立 ────────────
    if user is None:
        # 確認 email 不是空（Google login 一定會有 email；
        # 萬一沒有就拒絕，避免後續流程處理空字串）
        if not email:
            logger.error(
                "First-login but Firebase token has no email "
                "(firebase_uid=%s)", firebase_uid
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "missing_email",
                        "message": "Login provider did not return an email address",
                    }
                },
            )

        # email 唯一性衝突：
        # 例如同一個人先用 Google 註冊，後來又改用其他 provider 登入
        # → 直接報錯，由人工處理（V1 不做帳號合併）
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email is not None:
            logger.error(
                "Email already exists with different firebase_uid "
                "(email=%s, existing_uid=%s, new_uid=%s)",
                email, existing_email.firebase_uid, firebase_uid,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "email_already_exists",
                        "message": (
                            "This email is already registered with another "
                            "login method. Please contact admin."
                        ),
                    }
                },
            )

        # 建立 user（status 預設 active）
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(
            "Auto-created user on first login: id=%s email=%s",
            user.id, user.email,
        )
        # ⚠️ 注意：first-login 的 user 還沒有任何 ClinicMembership
        #    所以接下來如果 endpoint 需要 clinic 權限會被擋
        #    UI 端要在這時導去 /select-clinic 或顯示「等待邀請」

    # ─── 5. 檢查狀態 ─────────────────────────────────────
    if user.status != "active":
        logger.warning(
            "Disabled user attempted login: id=%s status=%s",
            user.id, user.status,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "user_disabled",
                    "message": f"User account is {user.status}",
                }
            },
        )

    return user
