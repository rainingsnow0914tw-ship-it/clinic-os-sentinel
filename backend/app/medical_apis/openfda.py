"""
============================================================
medical_apis/openfda.py — openFDA 藥物標籤 / 交互作用
============================================================
openFDA Drug Label API：
- 免費、免 API key、限制 240 reqs/min/IP (無 key) 或 240 reqs/min/key
- 內容：FDA 審過的處方藥仿單(label)
- 用途：撈「drug_interactions」章節，看 drug A 標籤是否提及 drug B

⚠️ FDA 自己明講「不要依賴 openFDA 做醫療決定」 → 完美符合哨兵鐵律：
    它給事實(標籤原文)，醫生做判斷。

Endpoint:
- https://api.fda.gov/drug/label.json?search=...
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_OPENFDA_BASE = "https://api.fda.gov/drug/label.json"
_REQUEST_TIMEOUT = 15  # 秒


async def fetch_drug_label(
    drug_name: str | None = None,
    rxcui: str | None = None,
) -> dict[str, Any] | None:
    """
    撈某藥的 FDA label。

    Args:
        drug_name:  英文藥名(品牌或學名都行)
        rxcui:      RxNorm 標準代碼(若有，優先用)

    Returns:
        openFDA results[0] 整段 dict，找不到 → None
    """
    if not drug_name and not rxcui:
        return None

    # 構造 search query
    # openFDA 搜尋語法：openfda.rxcui:"123" 或 openfda.brand_name:"warfarin"
    if rxcui:
        search = f'openfda.rxcui:"{rxcui}"'
    else:
        # 同時搜 brand_name + generic_name 提高命中率
        name = drug_name.lower()
        search = (
            f'openfda.brand_name:"{name}"+OR+'
            f'openfda.generic_name:"{name}"+OR+'
            f'openfda.substance_name:"{name}"'
        )

    url = f"{_OPENFDA_BASE}?search={search}&limit=1"
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(url)
    except Exception as e:
        logger.warning(f"openFDA fetch failed for {drug_name}/{rxcui}: {e}")
        return None

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        logger.warning(f"openFDA status={resp.status_code} for {drug_name}/{rxcui}")
        return None

    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None

    return results[0]


async def fetch_interaction_text(
    rxcui: str,
    drug_name: str,
    target_drug_name: str,
) -> dict[str, Any] | None:
    """
    撈 drug A 的標籤，在 drug_interactions 章節中搜尋是否提及 drug B。

    Returns:
        {
            "interaction_text": "...原文片段...",
            "source_url": "https://...",
            "raw_section": "...完整 drug_interactions 原文...",
        }
        找不到 → None
    """
    label = await fetch_drug_label(drug_name=drug_name, rxcui=rxcui)
    if not label:
        return None

    # 多 section 抓:OTC 藥(如 ibuprofen)不一定有 drug_interactions,
    # 但 warnings / precautions 會以 lay 詞(blood thinner / anticoagulant)提
    # 處方藥則在 drug_interactions + drug_and_or_laboratory_test_interactions
    candidate_sections = [
        "drug_interactions",
        "drug_and_or_laboratory_test_interactions",
        "contraindications",
        "warnings_and_cautions",
        "warnings",
        "precautions",
    ]
    text_chunks: list[str] = []
    for sec in candidate_sections:
        v = label.get(sec)
        if not v:
            continue
        if isinstance(v, list):
            text_chunks.extend(str(x) for x in v if x)
        else:
            text_chunks.append(str(v))

    if not text_chunks:
        return None

    full_text = "\n".join(text_chunks)

    # 搜尋 target_drug_name 是否出現在 interactions 原文裡
    # ⚠️ RxNorm 回的 standard_name 可能是 "warfarin sodium 3 MG Oral Tablet"，
    # 在 ibuprofen label 裡用整串 grep 找不到。
    # 策略：抽 first word (active ingredient) 當搜尋 key + word boundary
    search_keys = _build_search_keys(target_drug_name)
    matched_key = None
    for key in search_keys:
        # \b word boundary 避免 metformin 命中 metforminxxx
        pattern = re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE)
        if pattern.search(full_text):
            matched_key = key
            break

    if not matched_key:
        return None

    # 抓含 matched_key 的句子當摘錄
    excerpt = _extract_sentence(full_text, matched_key)

    # 來源 URL：openFDA 本身的 search query URL，評審/醫生可點
    source_url = (
        f"https://api.fda.gov/drug/label.json?"
        f'search=openfda.rxcui:"{rxcui}"&limit=1'
    )

    return {
        "interaction_text": excerpt,
        "source_url": source_url,
        "raw_section": full_text,
    }


def _build_search_keys(drug_name: str) -> list[str]:
    """
    從 RxNorm standard name 抽 search keys。

    例：
      "warfarin sodium 3 MG Oral Tablet" → ["warfarin sodium", "warfarin"]
      "ibuprofen 400 MG"                 → ["ibuprofen"]
      "acetaminophen"                    → ["acetaminophen"]

    優先順序：完整 ingredient phrase → first word(active ingredient)
    過濾掉純數字 / 單位 / dose form。
    """
    if not drug_name:
        return []

    # 砍掉常見的劑量/劑型尾巴
    cleaned = re.sub(
        r"\b(\d+(\.\d+)?\s*(mg|mcg|g|ml|iu|units?)?\s*(oral|tablet|capsule|injection|solution|cream|ointment)?)\b.*$",
        "",
        drug_name,
        flags=re.IGNORECASE,
    ).strip()

    # 也砍尾巴單純的 "MG Oral Tablet" 這種
    cleaned = re.sub(
        r"\b(oral\s+tablet|tablet|capsule|injection|solution|cream|ointment)\b.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    if not cleaned:
        cleaned = drug_name

    keys: list[str] = []

    # Key 1：清理後的整段 (含 ingredient + salt，如 "warfarin sodium")
    if cleaned and cleaned.lower() != drug_name.lower():
        keys.append(cleaned)

    # Key 2：first word (active ingredient core, 如 "warfarin")
    first_word = cleaned.split()[0] if cleaned else ""
    if first_word and (not keys or first_word.lower() != keys[0].lower()):
        keys.append(first_word)

    return keys


def _extract_sentence(text: str, keyword: str) -> str:
    """
    從一段文字中抓出含 keyword 的句子(粗略以 . / 。 / ; 切)。
    """
    keyword_lower = keyword.lower()
    # 用句號/分號/換行切句
    sentences = re.split(r"[.\n;。]", text)
    hits = [s.strip() for s in sentences if keyword_lower in s.lower()]
    if not hits:
        return text[:500]
    # 回前 3 句相關句子
    return ". ".join(hits[:3])[:1000]
