"""
============================================================
medical_apis/rxnorm.py — RxNorm 藥名標準化
============================================================
NLM RxNorm 公開 REST API：
- 免費、免 API key、無 rate limit (合理使用)
- 把品牌名/學名/縮寫/拼錯 → 標準代碼 RxCUI
- RxCUI 之後才能查 openFDA 標籤、DDInter 交互作用

Endpoint:
- 精確：https://rxnav.nlm.nih.gov/REST/rxcui.json?name=X
- 模糊：https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term=X&maxEntries=1

⚠️ 中文藥名 / 中成藥多半查不到 → RxNormResult.rxcui=None，呼叫端要處理。
============================================================
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
_REQUEST_TIMEOUT = 10  # 秒


class RxNormResult(BaseModel):
    """
    RxNorm 標準化結果。

    query:          原始藥名(使用者輸入)
    rxcui:          RxNorm Concept Unique Identifier(查不到=None)
    standard_name:  標準學名(查不到=None)
    confidence:     0.0~1.0，approximate match 才有意義
    source_url:     可驗證來源連結(評審/醫生可點)
    """

    query: str
    rxcui: str | None = None
    standard_name: str | None = None
    confidence: float = 0.0
    source_url: str | None = None


async def standardize_drug_name(drug_name: str) -> RxNormResult:
    """
    把任意藥名標準化成 RxCUI。

    流程：
    1. 先試精確匹配 (/rxcui.json?name=X)
    2. 沒中再試模糊匹配 (/approximateTerm.json?term=X)
    3. 都沒中 → 回 rxcui=None

    對所有意外錯誤兜底:回 rxcui=None 而非丟 exception
    (Sentinel 鐵律「對不確定誠實」+ 規則引擎不能因網路波動連帶炸整個 audit agent)
    """
    if not drug_name or not drug_name.strip():
        return RxNormResult(query=drug_name, rxcui=None)

    query = drug_name.strip()

    try:
        # === Step 1: 精確匹配 ===
        exact = await _exact_match(query)
        if exact:
            return exact

        # === Step 2: 模糊匹配 ===
        approx = await _approximate_match(query)
        if approx:
            return approx
    except Exception as e:
        logger.warning(f"RxNorm standardize unexpected error for {query!r}: {e}")

    # === Step 3: 全沒中 ===
    logger.info(f"RxNorm: no match for {query!r}")
    return RxNormResult(query=query, rxcui=None)


# ============================================================
# 內部：精確匹配
# ============================================================
async def _exact_match(query: str) -> RxNormResult | None:
    """呼叫 /rxcui.json?name=X，回傳精確匹配的 RxCUI。"""
    url = f"{_RXNAV_BASE}/rxcui.json"
    params = {"name": query}
    try:
        data = await _get_json(url, params)
    except Exception as e:
        logger.warning(f"RxNorm exact match failed for {query!r}: {e}")
        return None

    # RxNav 在沒命中時 idGroup 可能是 null 不是 {} → 用 `or {}` 保險
    rxcui_list = (data.get("idGroup") or {}).get("rxnormId", []) or []
    if not rxcui_list:
        return None

    rxcui = rxcui_list[0]
    return RxNormResult(
        query=query,
        rxcui=rxcui,
        standard_name=query,                              # 精確匹配，輸入就是標準名
        confidence=1.0,
        source_url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}",
    )


# ============================================================
# 內部：模糊匹配
# ============================================================
async def _approximate_match(query: str) -> RxNormResult | None:
    """呼叫 /approximateTerm.json，取最佳模糊匹配。"""
    url = f"{_RXNAV_BASE}/approximateTerm.json"
    params = {"term": query, "maxEntries": "1"}
    try:
        data = await _get_json(url, params)
    except Exception as e:
        logger.warning(f"RxNorm approx match failed for {query!r}: {e}")
        return None

    candidates = (data.get("approximateGroup") or {}).get("candidate", []) or []
    if not candidates:
        return None

    best = candidates[0]
    rxcui = best.get("rxcui")
    if not rxcui:
        return None

    # 取標準名(用 rxcui 反查)
    standard_name = await _lookup_name(rxcui) or query
    score = float(best.get("score", 0))
    confidence = min(score / 100.0, 1.0)

    return RxNormResult(
        query=query,
        rxcui=rxcui,
        standard_name=standard_name,
        confidence=confidence,
        source_url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}",
    )


# ============================================================
# 內部：反查標準名
# ============================================================
async def _lookup_name(rxcui: str) -> str | None:
    """用 RxCUI 反查標準藥名。"""
    url = f"{_RXNAV_BASE}/rxcui/{rxcui}/property.json"
    params = {"propName": "RxNorm Name"}
    try:
        data = await _get_json(url, params)
    except Exception:
        return None
    prop = (data.get("propConceptGroup") or {}).get("propConcept", []) or []
    if not prop:
        return None
    return prop[0].get("propValue")


# ============================================================
# 內部：HTTP helper
# ============================================================
async def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()
