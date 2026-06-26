"""
============================================================
core/security.py
============================================================
Firebase Auth ID token 驗證。

用 firebase-admin SDK 驗證從前端送來的 Authorization: Bearer <id_token>。
驗證成功後，從 token 拿出 firebase_uid，再去資料庫查 users 表拿到內部 user。

為什麼不用 JWT 自己簽：
- Firebase Auth 已經是正式產品，安全性與 SSO 都比自己做好
- Pinky 用過，Chloe 熟悉
============================================================
"""

import logging
from typing import Optional

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Firebase Admin 初始化
# ============================================================
# 啟動時初始化一次。
# - 在 Cloud Run：自動用 service account（GOOGLE_APPLICATION_CREDENTIALS 由平台設）
# - 本地開發：要設 GOOGLE_APPLICATION_CREDENTIALS 指向 SA json
# ============================================================
def init_firebase_admin() -> None:
    """初始化 Firebase Admin SDK。在 main.py 啟動時呼叫一次。"""
    if firebase_admin._apps:                          # 已經初始化過就跳過
        return

    if not settings.FIREBASE_PROJECT_ID:
        logger.warning("FIREBASE_PROJECT_ID is not set. Firebase Auth disabled.")
        return

    try:
        # 用 default credential（Cloud Run 自動掛 SA；本地用 GOOGLE_APPLICATION_CREDENTIALS）
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            "projectId": settings.FIREBASE_PROJECT_ID,
        })
        logger.info(f"Firebase Admin initialized for project={settings.FIREBASE_PROJECT_ID}")
    except Exception as e:
        logger.error(f"Failed to init Firebase Admin: {e}")
        # 開發階段不要 raise，否則本地沒 SA 跑不起來
        if settings.is_production:
            raise


# ============================================================
# Token 驗證
# ============================================================
def verify_id_token(id_token: str) -> dict:
    """
    驗證 Firebase ID token。

    回傳 decoded token dict，包含：
        uid:           firebase_uid，跟 users.firebase_uid 對應
        email:         使用者 email
        email_verified: 是否驗證
        exp:           expiration timestamp
        ...

    驗證失敗會 raise firebase_auth.InvalidIdTokenError 等子類。

    Args:
        id_token: 從 Authorization: Bearer <token> 拿到的字串

    Returns:
        decoded claims dict

    Raises:
        firebase_auth.InvalidIdTokenError: token 無效
        firebase_auth.ExpiredIdTokenError: token 過期
        firebase_auth.RevokedIdTokenError: token 被撤銷
    """
    # check_revoked=True：每次都檢查 revocation（會多打一次 API，但更安全）
    # 高流量時可以改 False，靠 token 自己過期
    return firebase_auth.verify_id_token(id_token, check_revoked=False)


def extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """
    從 Authorization header 拿 token。

    格式：Authorization: Bearer <token>
    """
    if not authorization_header:
        return None
    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]
