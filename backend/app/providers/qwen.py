"""
============================================================
providers/qwen.py — Qwen via DashScope REST
============================================================
比賽期(Qwen Cloud Hackathon)主秀 LLM。

為什麼用 REST 不用 dashscope SDK：
- 少一個相依套件，Docker image 小
- REST 跨語言可複用(賽後 Chloe 自用版前端直接打也行)
- 司機 5/21 立過「家族後端接 LLM 走 REST + ADC」鐵律(對應 Vertex AI 經驗)

司機 PowerShell 試打驗證(2026-06-26 03:00)：
    qwen-max → HTTP 200 → 中文正常 → 39 token

⚠️ 模型名稱不寫死，全部走 config.py。司機禁止區鐵律「不要憑記憶寫模型名稱」。
============================================================
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings
from app.providers.base import LLMProvider, ChatMessage, ChatResponse

logger = logging.getLogger(__name__)


# ============================================================
# DashScope REST API endpoints
# ============================================================
# 文字模型(qwen-max / qwen-plus / qwen-turbo)：
_TEXT_GENERATION_PATH = "/services/aigc/text-generation/generation"

# 多模態模型(qwen-vl-max / qwen-vl-plus)：
_VL_GENERATION_PATH = "/services/aigc/multimodal-generation/generation"


# ============================================================
# Provider 實作
# ============================================================
class QwenProvider(LLMProvider):
    """
    Qwen via DashScope International (dashscope-intl.aliyuncs.com)。

    用法：
        provider = QwenProvider()
        resp = await provider.chat(
            messages=[ChatMessage(role="user", content="你好")],
            temperature=0.3,
        )
        print(resp.text)
    """

    @property
    def name(self) -> str:
        return "qwen"

    # --------------------------------------------------------
    # 純文字
    # --------------------------------------------------------
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
        呼叫 Qwen 文字生成 API。

        DashScope text-generation 的 body 格式：
            {
              "model": "qwen-max",
              "input":      {"messages": [...]},
              "parameters": {"temperature": 0.3, "max_tokens": 2048, ...}
            }
        """
        if not settings.DASHSCOPE_API_KEY:
            raise RuntimeError(
                "DASHSCOPE_API_KEY is not set. "
                "請在 .env 填入司機從阿里雲拿到的 key。"
            )

        body = {
            "model": model or settings.QWEN_TEXT_MODEL,
            "input": {
                "messages": [m.model_dump() for m in messages],
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                # qwen3.7-max / qwen3-max 之後 result_format=text 被廢棄,
                # 必須用 "message"(回 choices[0].message.content 標準 chat schema)
                "result_format": extras.pop("result_format", "message"),
                **extras,
            },
        }

        return await self._post(_TEXT_GENERATION_PATH, body)

    # --------------------------------------------------------
    # 多模態(看圖)
    # --------------------------------------------------------
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
        Qwen-VL 多模態對話：圖片 + 文字。

        DashScope VL 的 message content 格式：
            {"role": "user", "content": [
                {"image": "https://...jpg"},
                {"text":  "這張 X 光看到什麼？"}
            ]}

        我們把 messages 最後一條 user 訊息塞 image，前面對話保持純文字。
        """
        if not settings.DASHSCOPE_API_KEY:
            raise RuntimeError("DASHSCOPE_API_KEY is not set.")

        # 把 messages 改寫成 VL 格式
        vl_messages: list[dict[str, Any]] = []
        for i, msg in enumerate(messages):
            is_last_user = (i == len(messages) - 1) and msg.role == "user"
            if is_last_user and image_urls:
                content_blocks: list[dict[str, Any]] = [
                    {"image": url} for url in image_urls
                ]
                content_blocks.append({"text": msg.content})
                vl_messages.append({"role": msg.role, "content": content_blocks})
            else:
                vl_messages.append({"role": msg.role, "content": [{"text": msg.content}]})

        body = {
            "model": model or settings.QWEN_VISION_MODEL,
            "input": {"messages": vl_messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                **extras,
            },
        }
        return await self._post(_VL_GENERATION_PATH, body)

    # --------------------------------------------------------
    # 底層：POST + 重試 + 錯誤處理
    # --------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        # TransportError 涵蓋 TimeoutException / NetworkError / ProtocolError /
        # RemoteProtocolError 全譜系 — qwen3.7-max thinking mode 偶發中途斷線
        # (2026-06-26 audit agent UI 跑炸的 root cause,凌晨 smoke 剛好命運好沒抓到)
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _post(self, path: str, body: dict[str, Any]) -> ChatResponse:
        """實際打 HTTP，加 retry。"""
        url = f"{settings.DASHSCOPE_BASE_URL.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.QWEN_REQUEST_TIMEOUT) as client:
            logger.debug(f"POST {url} model={body.get('model')}")
            resp = await client.post(url, json=body, headers=headers)

        if resp.status_code != 200:
            logger.error(
                f"DashScope error: status={resp.status_code} body={resp.text[:500]}"
            )
            resp.raise_for_status()

        data = resp.json()
        return self._parse_response(data, model=body.get("model", "qwen-max"))

    # --------------------------------------------------------
    # 解析 DashScope 回應(text 與 message 兩種 format)
    # --------------------------------------------------------
    @staticmethod
    def _parse_response(data: dict[str, Any], model: str) -> ChatResponse:
        """
        DashScope 兩種回應格式都吃：

        1. result_format=text(預設)：
           {"output": {"text": "...", "finish_reason": "stop"},
            "usage":  {"input_tokens": ..., "output_tokens": ...}}

        2. result_format=message：
           {"output": {"choices": [{"message": {"content": "..."}, "finish_reason": "stop"}]},
            "usage":  {...}}
        """
        output = data.get("output", {})
        usage = data.get("usage", {})

        # 格式 1：text
        if "text" in output:
            text = output.get("text", "")
            finish_reason = output.get("finish_reason", "stop")
        # 格式 2：message (text 或 multimodal)
        elif "choices" in output and output["choices"]:
            choice = output["choices"][0]
            content = choice.get("message", {}).get("content", "")
            # 純文字 model: content 是 str
            # 多模態 model (qwen-vl): content 是 list[{"text": "..."}] / {"image": "..."}
            if isinstance(content, list):
                text = "".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and "text" in item
                )
            else:
                text = str(content) if content else ""
            finish_reason = choice.get("finish_reason", "stop")
        else:
            text = ""
            finish_reason = "error"

        return ChatResponse(
            text=text,
            model=model,
            finish_reason=finish_reason,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            raw=data,
        )
