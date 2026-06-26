"""
============================================================
agents/intake.py — Sentinel Agent 1：入口偵查官
============================================================
身份：辦案的偵查官，不是聽寫員。

職責：
1. 原話全留：結構化但不丟資訊
2. 分類不過濾：主訴 / 額外提及 兩區都可見
3. 標連結不標輕重：只說「跟什麼勾連」(例:3B丸便祕→疑似 nocebo)
4. 標反常：跟平常不一致的主動標
5. 補漏(提示式)：標該問未問的，醫生可採納可忽略

絕不能做：
- 不替醫生隱藏資訊
- 不用輕中重分級
- 不下診斷
============================================================
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents._base import (
    ANTI_HALLUCINATION_RULES,
    extract_json,
    json_output_instruction,
)
from app.providers import get_default_provider
from app.providers.base import ChatMessage
from app.schemas.sentinel import IntakeRequest, IntakeResponse, IntakeFinding

logger = logging.getLogger(__name__)


# ============================================================
# System Prompt
# ============================================================
_SYSTEM_PROMPT = f"""
你是「哨兵」系統的 Agent 1：入口偵查官。

【你的身份】
你不是聽寫員，是辦案的偵查官。把醫生口述理清、讓重點浮出、標出該問沒問的。
絕不替醫生丟掉任何資訊。

【你要做的(依序)】
1. 原話全留：結構化(對齊病歷欄位)但每句保留，不刪不藏
2. 分類不過濾：分「主訴相關」+「額外提及」兩區都可見，離題的放額外區不丟
3. 標連結不標輕重：只說「跟什麼勾連」(例：3B丸便祕→疑似 nocebo 傾向)，
   不說重不重要
4. 標反常：跟平常不一致的主動標
5. 補漏(提示式)：標該問未問的(例：發燒→接觸史? 燒幾天?)，醫生可採納可忽略

【對抗警示疲勞 — 醫生 30 秒看不完就會 ignore】
- **suggested_question 最多 3 條**，只列「會死人」或「會誤診」的問題。
  問了不影響決策的問題不要列。寧可 1 條好的，也別 4 條湊數。
  按優先級排序：第 1 條最關鍵，第 3 條才邊緣。
- **anomaly 跟 main_complaint 同條時只列 anomaly**：
  例如「左手最近沒力」既是主訴也是反常，
  只放在 anomaly section(更值得醫生注意)，
  main_complaint 不重複列。避免同一資訊出現兩次。

【絕不能做】
- 不替醫生隱藏資訊
- 不用輕中重分級
- 不錄病人不存音檔
- 不下診斷
- 不為了「全留」湊 suggested_question(寧少勿濫)

{ANTI_HALLUCINATION_RULES}
"""


# ============================================================
# 輸出 schema hint(給 LLM 參考)
# ============================================================
_OUTPUT_SCHEMA_HINT = """
{
  "summary": "對本次口述的一句話摘要",
  "findings": [
    {
      "section": "main_complaint",
      "text": "病人主訴的具體內容",
      "linkage": null
    },
    {
      "section": "extra",
      "text": "離題但被提到的內容(例：順口提到的家裡事)",
      "linkage": "可能跟某某勾連，例：壓力大→可能影響血壓"
    },
    {
      "section": "anomaly",
      "text": "跟平常不一致的地方(例：左手最近沒力，跟過去病史不一致)",
      "linkage": "與既有中風史相關"
    },
    {
      "section": "suggested_question",
      "text": "建議追問的問題(例：發燒幾天了? 接觸史?)",
      "linkage": null
    }
  ]
}

注意：
- findings 為空陣列([]) 也合法，沒任何發現就回空
- section 必須是這四個值之一
- linkage 沒有就填 null，不要省略欄位
- **suggested_question 最多 3 條**，按優先級排序(最關鍵的放第一條)
- 同一資訊既是主訴又是反常 → 只放 anomaly 不重複放 main_complaint
"""


# ============================================================
# 主入口
# ============================================================
async def run_intake_agent(req: IntakeRequest) -> IntakeResponse:
    """
    跑入口偵查官 agent。

    Args:
        req: IntakeRequest(含 raw_dictation 等)

    Returns:
        IntakeResponse
    """
    provider = get_default_provider()

    user_content = _build_user_message(req)
    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT + json_output_instruction(_OUTPUT_SCHEMA_HINT)),
        ChatMessage(role="user", content=user_content),
    ]

    resp = await provider.chat(messages=messages, temperature=0.2, max_tokens=2000)

    parsed = extract_json(resp.text)
    if not isinstance(parsed, dict):
        # 解析失敗 — 把原文塞進 main_complaint section 當 fallback
        logger.warning(f"intake JSON parse failed; raw={resp.text[:200]}")
        return IntakeResponse(
            findings=[
                IntakeFinding(
                    section="main_complaint",
                    text=resp.text.strip()[:500],
                    linkage=None,
                )
            ],
            summary="(LLM 回應 JSON 解析失敗，已回原文)",
            model_used=resp.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

    findings = _normalize_findings(parsed.get("findings", []))
    summary = str(parsed.get("summary", ""))

    return IntakeResponse(
        findings=findings,
        summary=summary,
        model_used=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
    )


# ============================================================
# 構造 user message
# ============================================================
def _build_user_message(req: IntakeRequest) -> str:
    parts: list[str] = []
    if req.chief_complaint_hint:
        parts.append(f"【主訴提示】\n{req.chief_complaint_hint}")
    parts.append(f"【醫生口述原話】\n{req.raw_dictation}")
    return "\n\n".join(parts)


# ============================================================
# 把 LLM 回的 findings list 正規化成 IntakeFinding 物件
# ============================================================
def _normalize_findings(raw_findings: Any) -> list[IntakeFinding]:
    if not isinstance(raw_findings, list):
        return []

    valid_sections = {"main_complaint", "extra", "anomaly", "suggested_question"}
    out: list[IntakeFinding] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        section = item.get("section")
        text = item.get("text")
        if section not in valid_sections or not text:
            continue
        out.append(
            IntakeFinding(
                section=section,
                text=str(text).strip(),
                linkage=(str(item["linkage"]).strip() if item.get("linkage") else None),
            )
        )
    return out
