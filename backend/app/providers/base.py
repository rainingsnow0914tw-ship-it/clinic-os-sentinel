"""
============================================================
providers/base.py — LLM Provider 抽象介面
============================================================
所有 LLM Provider(Qwen / Claude / GPT / Gemini)必須遵守的契約。

設計重點：
1. 介面層只認 messages / model / temperature 等通用參數
   廠商特定的東西(top_p / repetition_penalty 等)放 extras dict
2. 回應統一成 ChatResponse，agent code 不必知道是哪家
3. async 介面：FastAPI 全程非同步，避免 block event loop

⚠️ Chloe 沒工程背景，注釋要詳細。
============================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal
from pydantic import BaseModel, Field


# ============================================================
# 統一的訊息格式
# ============================================================
class ChatMessage(BaseModel):
    """
    一條對話訊息(對應 OpenAI / Anthropic / Qwen 都通用的 schema)。

    role:    system / user / assistant
    content: 訊息文字本身
    """

    role: Literal["system", "user", "assistant"]
    content: str


class ChatResponse(BaseModel):
    """
    LLM 回應(統一格式，所有 provider 都要回這個)。

    text:           生成的文字(主要結果)
    model:          實際使用的模型名稱(廠商可能會 fallback)
    finish_reason:  stop / length / content_filter / tool_calls / error
    input_tokens:   輸入消耗 token 數
    output_tokens:  輸出消耗 token 數
    raw:            原廠商回應 dict(debug 用，agent 不必看)
    """

    text: str
    model: str
    finish_reason: str = "stop"
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Provider 抽象介面
# ============================================================
class LLMProvider(ABC):
    """
    所有 LLM Provider 的基底類別。

    任何 agent 想呼叫 LLM，都透過這個介面。
    廠商特定 SDK / HTTP 細節都封裝在子類裡。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名稱，例如 'qwen' / 'anthropic' / 'openai'。"""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **extras: Any,
    ) -> ChatResponse:
        """
        純文字對話。

        Args:
            messages:       對話歷史(含 system prompt 開頭)
            model:          指定模型，None = 用 provider 預設
            temperature:    0.0~2.0，越低越保守(醫療場景預設 0.3)
            max_tokens:     回應 token 上限
            extras:         廠商特定參數(top_p / repetition_penalty 等)

        Returns:
            ChatResponse 物件
        """
        ...

    async def vision(
        self,
        messages: list[ChatMessage],
        image_urls: list[str],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        **extras: Any,
    ) -> ChatResponse:
        """
        多模態(看圖)對話。預設不支援，子類覆寫才有。

        哨兵用途：Qwen-VL 讀 X 光、皮膚照片、檢驗單。
        """
        raise NotImplementedError(
            f"{self.name} provider does not support vision. "
            "Use a vision-capable model like qwen-vl-max."
        )
