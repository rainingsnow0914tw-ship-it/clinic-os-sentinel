"""
============================================================
agents/_base.py — Sentinel agent 共用 helper
============================================================
集中：
- 反幻覺五型紅線(每個 agent system prompt 都要嵌)
- JSON 解析(從 Qwen 回應裡撈 JSON，容錯 markdown ```json 包裹)
- 標準錯誤處理

⚠️ 不放 agent 商業邏輯，那部分各 agent 各管各的。
============================================================
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 反幻覺五型紅線(來自「千問模型性能测试」對話框，Chat 寶內化進設計)
# ============================================================
# 嵌進每個 agent system prompt 開頭，框住 Qwen 容易犯的五型幻覺：
# 1. 編造不存在的醫學事實
# 2. 過度自信(沒附來源就斷言)
# 3. 為了「有幫助」而硬湊建議
# 4. 跨領域亂套(化學藥理硬套到中藥)
# 5. 把「常見」當成「適用此病人」
# ============================================================
ANTI_HALLUCINATION_RULES = """
【反幻覺五型紅線】(嚴格遵守，違反即失敗)

1. 不可編造任何醫學事實。任何具體斷言(藥物作用、交互作用、診斷標準)
   必須附 PubMed/openFDA 可驗證來源。沒來源 = 不講。

2. 不可過度自信。對任何不確定，明確說「不確定 / 需要進一步檢查」。
   寧可少喊喊得準，絕不亂示警(警示疲勞)。

3. 不可為了「有用」而硬湊內容。
   如果這個病人這個情境沒事，就回「未發現需特別注意之處」。
   湊數說廢話 = 自毀信用 = 嚴重違規。

4. 不可跨領域亂套。
   中藥、保健品成分不明時，明確標 unknown 不假裝知道。
   西藥藥理不要硬套到中藥。

5. 不可把「常見」當成「適用此病人」。
   一律對「這個病人」「這個情境」的具體資料推理，
   不要用「一般而言」「通常」當主軸。
"""


# ============================================================
# JSON 解析(從 LLM 自由文字回應裡撈 JSON)
# ============================================================
def extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """
    從 LLM 回應文字裡撈 JSON。

    容錯處理：
    - ```json ... ``` markdown code block
    - 開頭/結尾多餘文字
    - 解析失敗回 None(呼叫端要決定怎麼 fallback)

    Args:
        text: LLM 回應原文

    Returns:
        dict / list / None
    """
    if not text:
        return None

    # 1. 試直接 parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 試 markdown code block
    code_block = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 試找第一個 { 或 [ 到最後一個 } 或 ]
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    logger.warning(f"extract_json failed; preview={text[:200]!r}")
    return None


# ============================================================
# 構造 JSON 輸出指示(附在 system prompt 結尾)
# ============================================================
def json_output_instruction(schema_hint: str) -> str:
    """
    產生「請以 JSON 格式輸出」的指示。

    Args:
        schema_hint: 給 LLM 看的 JSON 範例(不必嚴格 schema)

    Returns:
        附在 system prompt 結尾的指示字串
    """
    return f"""

【輸出格式】
請只輸出單一 JSON 物件(可選擇用 ```json ... ``` 包裹)。
不要任何前後說明文字。

JSON 結構：
{schema_hint}
"""
