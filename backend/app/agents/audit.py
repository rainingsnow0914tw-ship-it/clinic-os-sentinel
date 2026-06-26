"""
============================================================
agents/audit.py — Sentinel Agent 3：後閘門處方審計官
============================================================
身份：開完藥後做最後安全檢查的人。

界線清楚(三層)：
- 第一層(藥 vs 藥)：規則引擎查表，不是 AI 的事
- 第二層(藥 vs 長期用藥全圖)：湊齊後比對仍查表，AI 確保湊齊
- 第三層(藥 vs 此病人完整縱向狀態)：這才是 AI 的事 ← 情境推理

工作流：
1. 先 call DrugInteractionEngine 算第一層(規則引擎結果)
2. 把規則引擎結果 + 病人紅旗 + 長期用藥 給 LLM
3. LLM 只做第三層情境推理，且必附來源或標 needs_confirmation
4. 提醒成分不明保健品(不假裝確定)
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
from app.rules import DrugInteractionEngine, Interaction
from app.schemas.sentinel import (
    AuditRequest,
    AuditResponse,
    RuleEngineFinding,
    ContextualRisk,
    HeartFlag,
    HeartProblem,
    HeartMedication,
)

logger = logging.getLogger(__name__)


# ============================================================
# System Prompt
# ============================================================
_SYSTEM_PROMPT = f"""
你是「哨兵」系統的 Agent 3：後閘門處方審計官。

【你的身份】
開完藥後做最後安全檢查。
界線清楚：會打架的藥物組合是「事實」由程式查表，
你只負責程式查不到、需「理解病人情境」那層。
不是 DDI checker 替代品。

【三層界線(認清你站第幾層)】
第一層(藥 vs 藥)：規則引擎查表，已經給你 → 不重複囉嗦
第二層(藥 vs 長期用藥全圖)：湊齊後比對仍查表 → 你的價值是確認湊齊了
第三層(藥 vs 此病人縱向狀態) ← 這才是你

【鐵律：事實查表，判斷才給你，絕不編交互作用】
「A+B 會出血」這種事實 → 規則引擎，你不可生成不可編造
(幻覺出不存在的交互作用會殺人)。
你做情境推理且必附來源。

【你要做的】
1. 接收新處方 + 病人縱向真相(紅旗/慢性病/長期用藥含保健品)
2. 規則引擎結果已給你，不重複
3. 撞紅旗：尤其⚠過敏、⚠懷孕哺乳(時效型確認仍有效) 必撞
4. 第三層推理：此病人特定狀態下這藥安全嗎? 只在有具體情境風險時示警附來源
5. 成分不明保健品：提醒此處有不確定，不假裝知道

【絕不能做】
- 不編造交互作用(規則引擎沒查到的不要硬講)
- 不重複規則引擎已攔的
- 不在沒具體風險時亂示警(寧少勿濫)
- 不下最終處方決定
- 對成分不明不假裝確定

{ANTI_HALLUCINATION_RULES}
"""


# ============================================================
# 輸出 schema hint
# ============================================================
_OUTPUT_SCHEMA_HINT = """
{
  "contextual_risks": [
    {
      "drug": "新處方的藥名",
      "risk": "第三層情境風險的具體描述(此病人特定狀態下)",
      "triggered_by": "哪條紅旗 / 病史 / 長期用藥觸發的"
    }
  ],
  "unknowns": [
    "成分不明保健品提醒文字"
  ]
}

注意：
- 沒任何第三層風險就回 contextual_risks: []
- 不要硬湊。沒事就明確說沒事(整個 contextual_risks 為空陣列)。
- 規則引擎結果已附在 user message，你不必複述。
- 不要自己編 source_url，後端會處理。
"""


# ============================================================
# 主入口
# ============================================================
async def run_audit_agent(req: AuditRequest) -> AuditResponse:
    """跑後閘門處方審計官。"""

    # === 第一步：規則引擎(事實查表) ===
    rule_findings = await _run_rule_engine(req)

    # === 第二步：LLM 第三層情境推理 ===
    provider = get_default_provider()
    user_content = _build_user_message(req, rule_findings)

    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT + json_output_instruction(_OUTPUT_SCHEMA_HINT)),
        ChatMessage(role="user", content=user_content),
    ]

    resp = await provider.chat(messages=messages, temperature=0.2, max_tokens=2000)
    parsed = extract_json(resp.text)

    contextual_risks: list[ContextualRisk] = []
    unknowns: list[str] = []

    if isinstance(parsed, dict):
        raw_risks = parsed.get("contextual_risks", [])
        if isinstance(raw_risks, list):
            for item in raw_risks:
                if not isinstance(item, dict):
                    continue
                drug = str(item.get("drug", "")).strip()
                risk = str(item.get("risk", "")).strip()
                triggered_by = str(item.get("triggered_by", "")).strip()
                if not drug or not risk:
                    continue
                contextual_risks.append(
                    ContextualRisk(
                        drug=drug,
                        risk=risk,
                        triggered_by=triggered_by,
                        needs_confirmation=True,  # 第三層推理永遠標待確認
                    )
                )

        raw_unknowns = parsed.get("unknowns", [])
        if isinstance(raw_unknowns, list):
            unknowns = [str(u).strip() for u in raw_unknowns if u]

    # 自動加成分不明保健品提醒(如 user message 已有,LLM 也應該回，雙保險)
    for med in req.long_term_medications:
        if not med.composition_certain:
            line = f"長期服 {med.name} 成分不明，交互作用無法完整確認，建議留意。"
            if line not in unknowns:
                unknowns.append(line)

    return AuditResponse(
        rule_engine_findings=rule_findings,
        contextual_risks=contextual_risks,
        unknowns=unknowns,
        model_used=resp.model,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
    )


# ============================================================
# 第一步：跑規則引擎
# ============================================================
async def _run_rule_engine(req: AuditRequest) -> list[RuleEngineFinding]:
    """
    把 new_prescription + long_term_medications 全部丟進 DrugInteractionEngine。
    """
    all_drugs: list[str] = list(req.new_prescription)
    for med in req.long_term_medications:
        if med.composition_certain:                         # 成分不明的不丟進規則引擎
            all_drugs.append(med.name)

    if len(all_drugs) < 2:
        return []

    engine = DrugInteractionEngine()
    try:
        interactions = await engine.check(all_drugs)
    except Exception as e:
        logger.warning(f"DrugInteractionEngine error: {e}")
        return []

    return [
        RuleEngineFinding(
            drug_a=i.drug_a,
            drug_b=i.drug_b,
            severity=i.severity.value,
            description=i.description,
            source=i.source,
            source_url=i.source_url,
            needs_confirmation=i.needs_confirmation,
        )
        for i in interactions
    ]


# ============================================================
# 構造 user message
# ============================================================
def _build_user_message(
    req: AuditRequest,
    rule_findings: list[RuleEngineFinding],
) -> str:
    parts: list[str] = []

    parts.append("【新處方】\n" + ", ".join(req.new_prescription))

    if req.long_term_medications:
        med_lines = [_format_med(m) for m in req.long_term_medications]
        parts.append("【長期用藥(全圖)】\n" + "\n".join(med_lines))

    if req.problems:
        problem_lines = [_format_problem(p) for p in req.problems]
        parts.append("【慢性病】\n" + "\n".join(problem_lines))

    if req.flags:
        flag_lines = [_format_flag(f) for f in req.flags]
        parts.append("【病人紅旗】\n" + "\n".join(flag_lines))

    if rule_findings:
        rule_lines = [
            f"- {r.drug_a} × {r.drug_b}: {r.severity} — {r.description[:200]}"
            for r in rule_findings
        ]
        parts.append("【規則引擎結果(事實查表，你不必複述)】\n" + "\n".join(rule_lines))
    else:
        parts.append("【規則引擎結果】無命中(規則引擎未找到藥物對藥物層級的交互作用)")

    return "\n\n".join(parts)


def _format_med(m: HeartMedication) -> str:
    unknown = " (⚠ 成分不明)" if not m.composition_certain else ""
    return f"- {m.name} [{m.category}]{unknown}"


def _format_problem(p: HeartProblem) -> str:
    status = f" [{p.control_status}]" if p.control_status else ""
    return f"- {p.name}{status}"


def _format_flag(f: HeartFlag) -> str:
    sev = f" [{f.severity}]" if f.severity else ""
    valid = f" (有效至 {f.valid_until})" if f.valid_until else ""
    return f"- [{f.type}]{sev} {f.content}{valid} (來源:{f.source})"
