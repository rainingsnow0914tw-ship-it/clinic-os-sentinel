"""
============================================================
agents/education.py — Sentinel Agent 4：衛教出口官
============================================================
身份：決策節點 2 後生成「個人化生活醫囑」。
對抗病人回家後的盲點(醫生沒空講的生活習慣)。
只增療效不取代醫囑。

範圍(保守不擴張)：
- 只做文字、個人化、簡單
- 吃同一顆心臟(針對此病人愛吃煎炸/熬夜等)，不是罐頭衛教單

安全紅線(絕不可越)：
- 可「解釋為什麼」，不可「示範怎麼做」
- 衛教概念圖安全但比賽版先文字
- 動作示範圖(復健/伸展/按摩)絕對不生成
============================================================
"""

from __future__ import annotations

import json
import logging

from app.agents._base import ANTI_HALLUCINATION_RULES
from app.providers import get_default_provider
from app.providers.base import ChatMessage
from app.schemas.sentinel import EducationRequest, EducationResponse

logger = logging.getLogger(__name__)


# ============================================================
# System Prompt
# ============================================================
_SYSTEM_PROMPT = f"""
你是「哨兵」系統的 Agent 4：衛教出口官。

【你的身份】
決策節點 2 後生成「個人化生活醫囑」。
對抗病人回家後的盲點(醫生沒空講的生活習慣)。
只增療效不取代醫囑。

【範圍(保守不擴張)】
- 只做文字、個人化、簡單
- 吃同一顆心臟(針對此病人習慣)，不是罐頭衛教單

【安全紅線(絕不可越)】
- 可「解釋為什麼」，不可「示範怎麼做」
- 動作示範(復健/伸展/按摩) → 絕對不生成

【比賽版範圍】
- 只做：針對此診斷 + 此病人習慣的文字醫囑
- 使用型態：口頭版優先(醫生看著口頭講)
- 先不做：藥物副作用預告、複雜衛教、動作指導

【絕不能做】
- 不取代或改動正式醫囑
- 不下診斷、不改處方
- 不超出本次診斷的過度衛教

【輸出語氣】
溫暖、具體、就事論事。針對「這個病人」「這個習慣」「這個診斷」說話，
不要「一般而言」「大家都」這種泛化表達。

{ANTI_HALLUCINATION_RULES}

【輸出格式】
請以下列 JSON 結構回應(可選擇用 ```json 包裹)：
{{
  "advice": "完整給病人聽的個人化生活醫囑(2-4 句話，溫暖具體)",
  "reasoning": "為什麼這樣建議(簡短原理，不示範動作)"
}}
"""


# ============================================================
# 主入口
# ============================================================
async def run_education_agent(req: EducationRequest) -> EducationResponse:
    """跑衛教出口官。"""

    provider = get_default_provider()
    user_content = _build_user_message(req)

    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_content),
    ]

    resp = await provider.chat(messages=messages, temperature=0.4, max_tokens=1500)

    # 解析 JSON
    from app.agents._base import extract_json
    parsed = extract_json(resp.text)
    if isinstance(parsed, dict):
        advice = str(parsed.get("advice", "")).strip()
        reasoning = str(parsed.get("reasoning", "")).strip()
    else:
        # 解析失敗 — 把原文當 advice
        logger.warning(f"education JSON parse failed; using raw text")
        advice = resp.text.strip()
        reasoning = ""

    return EducationResponse(
        advice=advice or "(本次無特別生活建議)",
        reasoning=reasoning,
        model_used=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
    )


# ============================================================
# 構造 user message
# ============================================================
def _build_user_message(req: EducationRequest) -> str:
    parts: list[str] = [f"【本次診斷】\n{req.diagnosis}"]

    if req.patient_name_hint:
        parts.append(f"【病人稱呼】\n{req.patient_name_hint}")

    if req.patient_habits:
        habits_text = json.dumps(req.patient_habits, ensure_ascii=False, indent=2)
        parts.append(f"【病人習慣(從心臟資料)】\n{habits_text}")
    else:
        parts.append("【病人習慣】未提供，請給通用但保守的建議")

    return "\n\n".join(parts)
