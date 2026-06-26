"""
============================================================
core/config.py
============================================================
集中管理所有環境變數設定。
用 pydantic-settings 自動從 .env 讀取與驗證型別。

為什麼這樣做：
- 所有 config 都從這裡拿，不要直接讀 os.environ
- 型別錯誤在啟動時就 raise，不會跑到一半才炸
- 測試時可以 mock Settings 物件
============================================================
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """應用程式全域設定。"""

    # -------------------- 應用程式 --------------------
    APP_ENV: str = "development"          # development / staging / production
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/v1"
    API_TITLE: str = "Clinic OS API"

    # -------------------- 資料庫 --------------------
    DATABASE_URL: str                     # 必填，沒填會 startup 時炸
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # -------------------- Firebase Auth --------------------
    FIREBASE_PROJECT_ID: str = ""
    # GOOGLE_APPLICATION_CREDENTIALS 由 google-auth library 自動讀，
    # 不需要在這宣告，Cloud Run 會自動掛載 service account

    # -------------------- GCS --------------------
    GCS_BUCKET_NAME: str = ""
    GCS_PDF_URL_EXPIRY_SECONDS: int = 3600

    # -------------------- AI Providers --------------------
    # 三家都允許空值，表示「這個 provider 沒設定，呼叫時會 raise」
    GEMINI_API_KEY: str = ""
    GEMINI_DEFAULT_MODEL: str = "gemini-2.5-flash"   # TODO: 用前 web_search 最新版本

    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"        # TODO: 用前 web_search

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_DEFAULT_MODEL: str = "claude-haiku-4-5-20251001"  # TODO: 用前 web_search

    # -------------------- Qwen / DashScope (Sentinel 比賽期 LLM) --------------------
    # 司機在 PowerShell 試打 qwen-max 已驗證可用(2026-06-26 03:00)
    # 走 REST API + httpx，不裝 dashscope SDK 避免相依
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    QWEN_TEXT_MODEL: str = "qwen-max"
    QWEN_VISION_MODEL: str = "qwen-vl-max"
    QWEN_ASR_MODEL: str = "paraformer-v2"
    QWEN_REQUEST_TIMEOUT: int = 120
    QWEN_MAX_RETRIES: int = 2

    # -------------------- Sentinel 哨兵層 --------------------
    SENTINEL_ENABLED: bool = True
    SENTINEL_DEV_BYPASS_AUTH: bool = False

    # -------------------- CORS --------------------
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """把逗號分隔的 CORS_ORIGINS 字串轉成 list。"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    # pydantic-settings：從 .env 讀取
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",                   # .env 多寫了不認識的 key 不要炸
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    回傳全域 Settings 單例。
    用 lru_cache 確保只實體化一次。
    測試時可以 get_settings.cache_clear() 重新讀取。
    """
    return Settings()


# 方便其他模組直接 import settings
settings = get_settings()
