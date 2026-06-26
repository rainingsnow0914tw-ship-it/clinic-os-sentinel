"""
規則引擎 — Sentinel 後閘門的「事實查表」層

🔒 哨兵鐵律 1：事實查表，判斷給 AI。絕不讓 AI 編造藥物交互作用。

職責：
- 接收一組藥(可能是品牌名、學名、縮寫、拼錯)
- 標準化藥名 → RxCUI (透過 medical_apis/rxnorm.py)
- 查交互作用 → openFDA / DDInter (透過 medical_apis/openfda.py)
- 回傳結構化結果，後閘門 agent 拿這個結果做情境推理(不重複規則引擎工作)

跟 AI 的界線(取自 docs/AI_BOUNDARY.md 哨兵延伸版)：
- 規則引擎：事實(A+B 會出血)
- AI(後閘門 agent)：情境推理(此病人中風史 + 腎功能 + 新處方 → 相對禁忌嗎)
"""

from app.rules.drug_interaction import (
    DrugInteractionEngine,
    Interaction,
    InteractionSeverity,
)

__all__ = [
    "DrugInteractionEngine",
    "Interaction",
    "InteractionSeverity",
]
