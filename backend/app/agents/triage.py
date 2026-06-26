"""
============================================================
agents/triage.py — Sentinel Agent 2：前閘門鑑別診斷官
============================================================
身份：醫生的盲點守門員，不是更厲害的醫生。

唯一使命：確保「會死人但被忽略的可能」沒因錨定偏誤被跳過。

核心紀律：
- 最大失敗不是想不出，是亂喊
- 只在「當前假設」與「病人既有事實」有真實矛盾時才提反面可能
- 沒矛盾 = 回 has_conflict=False，differentials=[]，絕不湊數

知識來源：
- 一律附 PubMed 可驗證來源連結
- 程式呼叫 PubMed E-utilities 補來源(避免 LLM 編連結)
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
from app.medical_apis.pubmed import search_pubmed
from app.providers import get_default_provider
from app.providers.base import ChatMessage
from app.schemas.sentinel import (
    TriageRequest,
    TriageResponse,
    TriageDifferential,
    HeartFlag,
    HeartProblem,
    HeartMedication,
)

logger = logging.getLogger(__name__)


# ============================================================
# System Prompt
# ============================================================
_SYSTEM_PROMPT = f"""
你是「哨兵」系統的 Agent 2：前閘門鑑別診斷官。

【你的身份】
醫生的盲點守門員，不是更厲害的醫生。
唯一使命：確保「會死人但被忽略的可能」沒因錨定偏誤被跳過。
不搶當最可能診斷的判斷者。

【核心紀律：最大失敗不是想不出，是亂喊】
只在「當前假設」與「病人既有事實(尤其紅旗/病史)」有真實矛盾時才提反面可能。
沒具體矛盾的反調 = 噪音 = 禁止。
核心能力是「偵測假設與既有事實的矛盾」，不是「生成可能性」。

【你要做的】
1. 接收醫生工作假設 + 病人縱向真相(含紅旗/病史/長期用藥)
2. 把假設建構到最強(讓錨定展現)
3. 帶病史紅旗攻擊它：會死人的可能是什麼? 哪條紅旗衝突? 漏排除什麼?
4. 只在矛盾夠強時提至多 3 個鑑別，每個必附「為何排除」
5. 然後停，交醫生判斷

【絕不能做】
- 不下最終診斷
- 不在沒矛盾時亂喊
- 不超過 3 個鑑別(數字由矛盾決定，有兩個給兩個、不硬湊)
- 湊數說廢話 = 自毀信用 = 嚴重違規

【語氣鐵律：補位不糾錯】
不說「你錯了 / 你漏看中風」。
說「此人有中風史，除 MG 外腦傷後癲癇亦需排除，供參考」。

{ANTI_HALLUCINATION_RULES}
"""


# ============================================================
# 輸出 schema hint
# ============================================================
_OUTPUT_SCHEMA_HINT = """
{
  "has_conflict": true,
  "conflict_summary": "病人有[紅旗X]，與假設[Y]衝突，具體在...",
  "differentials": [
    {
      "diagnosis": "鑑別診斷名稱",
      "reasoning": "為什麼這個病人此情境需要排除這個診斷",
      "pubmed_search_query": "用來搜 PubMed 的英文關鍵字(例：post-stroke epilepsy diagnosis)"
    }
  ]
}

注意：
- has_conflict=false 時，differentials 必須是 []，conflict_summary=""
- differentials 最多 3 個，沒有就 [] 不要硬湊
- pubmed_search_query 用英文，醫學術語，3-6 個字
- 不要自己寫 source_url，後端會用 pubmed_search_query 去 PubMed 補真實連結
"""


# ============================================================
# 主入口
# ============================================================
async def run_triage_agent(req: TriageRequest) -> TriageResponse:
    """跑前閘門鑑別診斷官。"""
    provider = get_default_provider()

    user_content = _build_user_message(req)
    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT + json_output_instruction(_OUTPUT_SCHEMA_HINT)),
        ChatMessage(role="user", content=user_content),
    ]

    resp = await provider.chat(messages=messages, temperature=0.2, max_tokens=2000)
    parsed = extract_json(resp.text)
    if not isinstance(parsed, dict):
        logger.warning(f"triage JSON parse failed; raw={resp.text[:200]}")
        return TriageResponse(
            has_conflict=False,
            conflict_summary="(LLM 回應 JSON 解析失敗，保守回報為無衝突)",
            differentials=[],
            model_used=resp.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

    has_conflict = bool(parsed.get("has_conflict", False))
    summary = str(parsed.get("conflict_summary", "")).strip()
    raw_diffs = parsed.get("differentials", [])

    # 沒衝突 → 直接回空
    if not has_conflict or not isinstance(raw_diffs, list):
        return TriageResponse(
            has_conflict=False,
            conflict_summary="",
            differentials=[],
            model_used=resp.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

    # 有衝突 → 用 LLM 提的搜尋 query 去 PubMed 補真實來源
    differentials = await _enrich_with_pubmed(raw_diffs[:3])

    return TriageResponse(
        has_conflict=True,
        conflict_summary=summary,
        differentials=differentials,
        model_used=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
    )


# ============================================================
# 構造 user message
# ============================================================
def _build_user_message(req: TriageRequest) -> str:
    parts: list[str] = [f"【醫生工作假設】\n{req.working_hypothesis}"]

    if req.flags:
        flag_lines = [_format_flag(f) for f in req.flags]
        parts.append("【病人紅旗】\n" + "\n".join(flag_lines))

    if req.problems:
        problem_lines = [_format_problem(p) for p in req.problems]
        parts.append("【慢性病】\n" + "\n".join(problem_lines))

    if req.medications:
        med_lines = [_format_med(m) for m in req.medications]
        parts.append("【長期用藥】\n" + "\n".join(med_lines))

    return "\n\n".join(parts)


def _format_flag(f: HeartFlag) -> str:
    sev = f" [{f.severity}]" if f.severity else ""
    valid = f" (有效至 {f.valid_until})" if f.valid_until else ""
    return f"- [{f.type}]{sev} {f.content}{valid} (來源:{f.source})"


def _format_problem(p: HeartProblem) -> str:
    status = f" [{p.control_status}]" if p.control_status else ""
    meds = f" 對應用藥:{', '.join(p.medications)}" if p.medications else ""
    return f"- {p.name}{status}{meds}"


def _format_med(m: HeartMedication) -> str:
    unknown = " (成分不明)" if not m.composition_certain else ""
    return f"- {m.name} [{m.category}]{unknown}"


# ============================================================
# 用 LLM 提的 pubmed_search_query 補真實 PubMed 來源
# ============================================================
async def _enrich_with_pubmed(raw_diffs: list[Any]) -> list[TriageDifferential]:
    out: list[TriageDifferential] = []
    for item in raw_diffs:
        if not isinstance(item, dict):
            continue
        diagnosis = str(item.get("diagnosis", "")).strip()
        reasoning = str(item.get("reasoning", "")).strip()
        query = str(item.get("pubmed_search_query", "")).strip()
        if not diagnosis or not reasoning:
            continue

        source_pmid = None
        source_url = None
        if query:
            try:
                articles = await search_pubmed(query, max_results=1)
                if articles:
                    source_pmid = articles[0].pmid
                    source_url = articles[0].url
            except Exception as e:
                logger.warning(f"PubMed enrich failed for {query!r}: {e}")

        out.append(
            TriageDifferential(
                diagnosis=diagnosis,
                reasoning=reasoning,
                source_pmid=source_pmid,
                source_url=source_url,
            )
        )
    return out
