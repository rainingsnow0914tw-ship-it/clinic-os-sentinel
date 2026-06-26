"""
============================================================
rules/drug_interaction.py — 藥物交互作用規則引擎
============================================================
🔒 哨兵鐵律 1：事實查表非編造。

工作流：
1. 接收一組藥(任意寫法：品牌名/學名/中文/拼錯)
2. 對每種藥呼叫 RxNorm 標準化 → RxCUI
3. 對每對 (drug_a, drug_b) 兩兩比對：
   - openFDA 查 drug label，掃 "drug_interactions" 章節提到 drug_b
   - 找不到 → 標 needs_confirmation=true，不假裝沒事
4. 回傳 Interaction list

⚠️ 比賽期限制：
- RxNorm + openFDA 是美國 NLM/FDA 資料，澳門中文藥名/中成藥可能查不到
- 查不到 → 老實標 "unknown_drug"，符合鐵律「對不確定誠實」

⚠️ 不做的：
- 不算嚴重度分級的「最終決定」(只引用 openFDA 標籤原文)
- 不下「絕對禁用」結論(留給後閘門 agent + 醫生)
============================================================
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.medical_apis.rxnorm import standardize_drug_name, RxNormResult
from app.medical_apis.openfda import fetch_interaction_text

logger = logging.getLogger(__name__)


# ============================================================
# 結構化結果
# ============================================================
class InteractionSeverity(str, Enum):
    """
    嚴重度。

    取自 openFDA 標籤常用詞彙(contraindicated > major > moderate > minor)，
    但我們不自己分級，只引用 openFDA 標籤原文裡的關鍵字。
    """

    CONTRAINDICATED = "contraindicated"   # 禁忌
    MAJOR = "major"                       # 重大
    MODERATE = "moderate"                 # 中度
    MINOR = "minor"                       # 輕微
    UNKNOWN = "unknown"                   # 查不到 / 無法判定


class Interaction(BaseModel):
    """
    一筆「藥 A × 藥 B」的交互作用查證結果。

    drug_a / drug_b:        使用者輸入的原始藥名(可能未標準化)
    rxcui_a / rxcui_b:      RxNorm 標準代碼(查得到才有)
    severity:               嚴重度(以 openFDA 標籤詞彙為準)
    description:            交互作用描述(直接從 openFDA 標籤節錄)
    source:                 引用來源("openFDA" / "RxNorm" / "unknown")
    source_url:             可驗證來源連結(評審/醫生可點)
    needs_confirmation:     true = 查不到或信心低，請醫生再確認
    """

    drug_a: str
    drug_b: str
    rxcui_a: str | None = None
    rxcui_b: str | None = None
    severity: InteractionSeverity = InteractionSeverity.UNKNOWN
    description: str = ""
    source: str = "unknown"
    source_url: str | None = None
    needs_confirmation: bool = True

    # 原始查證資料留作 debug
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)


# ============================================================
# 規則引擎本體
# ============================================================
class DrugInteractionEngine:
    """
    藥物交互作用查證引擎。

    用法：
        engine = DrugInteractionEngine()
        result = await engine.check([
            "warfarin",       # 抗凝血
            "ibuprofen",      # NSAID(會增加出血風險)
            "vitamin K",      # 拮抗 warfarin
        ])
        for interaction in result:
            print(interaction.drug_a, "×", interaction.drug_b, ":", interaction.severity)
    """

    async def check(self, drug_names: list[str]) -> list[Interaction]:
        """
        檢查一組藥彼此的兩兩交互作用。

        Args:
            drug_names: 藥名 list(任意寫法)

        Returns:
            list[Interaction]，每對組合一筆(N 個藥 = N×(N-1)/2 筆)
        """
        if len(drug_names) < 2:
            return []

        # 第一步：每個藥名標準化(RxNorm)
        standardized: list[RxNormResult] = []
        for name in drug_names:
            try:
                std = await standardize_drug_name(name)
            except Exception as e:
                logger.warning(f"RxNorm standardize failed for {name}: {e}")
                std = RxNormResult(query=name, rxcui=None, standard_name=None)
            standardized.append(std)

        # 第二步：兩兩比對交互作用
        results: list[Interaction] = []
        for i in range(len(standardized)):
            for j in range(i + 1, len(standardized)):
                a, b = standardized[i], standardized[j]
                interaction = await self._check_pair(a, b)
                results.append(interaction)

        return results

    # --------------------------------------------------------
    # 兩兩比對
    # --------------------------------------------------------
    async def _check_pair(
        self,
        a: RxNormResult,
        b: RxNormResult,
    ) -> Interaction:
        """
        對單一對藥查交互作用。

        策略：
        - 若兩邊都有 RxCUI → openFDA 撈 drug A label，搜尋是否提及 drug B
        - 若任何一邊沒 RxCUI → severity=unknown, needs_confirmation=true
        """
        if not a.rxcui or not b.rxcui or not a.standard_name or not b.standard_name:
            # 至少一邊查不到 — 老實標記
            return Interaction(
                drug_a=a.query,
                drug_b=b.query,
                rxcui_a=a.rxcui,
                rxcui_b=b.rxcui,
                severity=InteractionSeverity.UNKNOWN,
                description=(
                    "其中一個或兩個藥名在 RxNorm 查不到，無法自動查證交互作用。"
                    "可能原因：中文藥名 / 中成藥 / 拼錯。請醫生人工確認。"
                ),
                source="unknown",
                needs_confirmation=True,
            )

        # 兩邊都有 RxCUI → 查 openFDA
        try:
            fda = await fetch_interaction_text(
                rxcui=a.rxcui,
                drug_name=a.standard_name,
                target_drug_name=b.standard_name,
            )
        except Exception as e:
            logger.warning(f"openFDA query failed for {a.standard_name}×{b.standard_name}: {e}")
            return Interaction(
                drug_a=a.query,
                drug_b=b.query,
                rxcui_a=a.rxcui,
                rxcui_b=b.rxcui,
                severity=InteractionSeverity.UNKNOWN,
                description=f"openFDA 查證失敗：{e}。請醫生人工確認。",
                source="openFDA",
                needs_confirmation=True,
            )

        if not fda or not fda.get("interaction_text"):
            # openFDA 沒明確提到 → 不代表沒交互作用，標 needs_confirmation
            return Interaction(
                drug_a=a.query,
                drug_b=b.query,
                rxcui_a=a.rxcui,
                rxcui_b=b.rxcui,
                severity=InteractionSeverity.UNKNOWN,
                description=(
                    f"openFDA {a.standard_name} 標籤未明確提及與 {b.standard_name} 的交互作用。"
                    f"不代表沒風險(僅代表標籤未列)，請醫生確認。"
                ),
                source="openFDA",
                # fda 可能整個是 None(label 撈不到)→ 不能 .get;這個 bug 5/26 baseline 抓到
                source_url=(fda or {}).get("source_url"),
                needs_confirmation=True,
            )

        # 有命中 — 推斷嚴重度(從文字關鍵字)
        text = fda["interaction_text"]
        severity = self._infer_severity(text)

        return Interaction(
            drug_a=a.query,
            drug_b=b.query,
            rxcui_a=a.rxcui,
            rxcui_b=b.rxcui,
            severity=severity,
            description=text[:500],  # 截短，agent 拿全文時看 raw
            source="openFDA",
            source_url=fda.get("source_url"),
            needs_confirmation=(severity == InteractionSeverity.UNKNOWN),
            raw=fda,
        )

    # --------------------------------------------------------
    # 嚴重度推斷(從 openFDA 標籤文字)
    # --------------------------------------------------------
    @staticmethod
    def _infer_severity(text: str) -> InteractionSeverity:
        """
        從 openFDA 標籤文字推斷嚴重度。

        ⚠️ 不是 AI 判斷，是純關鍵字 match。openFDA 標籤本身就是 FDA 審過的事實文字。
        哨兵鐵律 1：事實查表非編造。
        """
        t = text.lower()
        if "contraindicated" in t or "contraindication" in t:
            return InteractionSeverity.CONTRAINDICATED
        if "major" in t or "serious" in t or "severe" in t or "life-threatening" in t:
            return InteractionSeverity.MAJOR
        if "moderate" in t:
            return InteractionSeverity.MODERATE
        if "minor" in t or "mild" in t:
            return InteractionSeverity.MINOR
        return InteractionSeverity.UNKNOWN
