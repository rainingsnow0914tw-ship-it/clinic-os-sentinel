"""
LLM Provider 抽換層 — Sentinel 哨兵專案

設計目的：
- 4 個 agent 透過 LLMProvider 介面呼叫 LLM，不直接 import vendor SDK
- 比賽期(Qwen Cloud Hackathon)只實做 QwenProvider
- 賽後 Chloe 自用診所版可加 AnthropicProvider / OpenAIProvider，agent code 完全不改

⚠️ 比賽期紀律：
- demo / video / README 不強調「可換模型」這件事
- 但介面化本身是技術深度加分(評審看到 abstraction 漂亮)
"""

from app.providers.base import LLMProvider, ChatMessage, ChatResponse
from app.providers.qwen import QwenProvider

__all__ = [
    "LLMProvider",
    "ChatMessage",
    "ChatResponse",
    "QwenProvider",
    "get_default_provider",
]


def get_default_provider() -> LLMProvider:
    """
    取得當前預設 LLM provider。

    比賽期固定回 QwenProvider。賽後 Chloe 自用版可改讀 settings.DEFAULT_LLM_PROVIDER
    決定回哪一家。
    """
    return QwenProvider()
