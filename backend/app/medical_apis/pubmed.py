"""
============================================================
medical_apis/pubmed.py — PubMed E-utilities 醫學文獻
============================================================
NCBI PubMed E-utilities：
- 免費、免 key (有 key 升到 10 reqs/sec)、3500 萬+ 醫學論文
- 用途：前閘門 agent 提鑑別診斷時附「可驗證來源連結」

🔒 哨兵鐵律 2：AI 斷言必附可驗證來源。

工作流：
1. ESearch (用病名/症狀關鍵字搜) → 拿 PMID list
2. ESummary (用 PMID 拿標題/作者/年份)
3. 回 PubMed URL 給 agent，agent 嵌在輸出裡

Endpoint:
- https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
- https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi
============================================================
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_REQUEST_TIMEOUT = 15  # 秒


class PubMedArticle(BaseModel):
    """
    PubMed 文獻摘要(只放給 agent 看的必要欄位)。

    pmid:    PubMed ID
    title:   文章標題
    authors: 作者 list (最多前 3 位)
    year:    出版年
    url:     PubMed 公開連結(評審/醫生可點)
    """

    pmid: str
    title: str
    authors: list[str] = []
    year: str | None = None
    url: str


async def search_pubmed(
    query: str,
    max_results: int = 3,
) -> list[PubMedArticle]:
    """
    搜 PubMed，回前 N 篇文獻摘要。

    Args:
        query: 搜尋關鍵字(英文，醫學術語)
            例：'post-stroke epilepsy' / 'warfarin NSAID bleeding'
        max_results: 取前幾篇(預設 3，agent 引用 1-3 篇就夠)

    Returns:
        list[PubMedArticle]，按 PubMed 相關度排序
    """
    if not query or not query.strip():
        return []

    # === Step 1: ESearch ===
    pmids = await _esearch(query.strip(), max_results)
    if not pmids:
        return []

    # === Step 2: ESummary ===
    return await _esummary(pmids)


async def _esearch(query: str, max_results: int) -> list[str]:
    """
    呼叫 ESearch，回 PMID list。
    """
    url = f"{_EUTILS_BASE}/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": str(max_results),
        "sort": "relevance",
    }
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"PubMed ESearch failed for {query!r}: {e}")
        return []

    return data.get("esearchresult", {}).get("idlist", [])


async def _esummary(pmids: list[str]) -> list[PubMedArticle]:
    """
    呼叫 ESummary，把 PMID list → PubMedArticle list。
    """
    if not pmids:
        return []

    url = f"{_EUTILS_BASE}/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"PubMed ESummary failed: {e}")
        return []

    result = data.get("result", {})
    articles: list[PubMedArticle] = []

    for pmid in pmids:
        item = result.get(pmid)
        if not item:
            continue

        # ESummary 的 authors 是 list[{"name": "Smith J", "authtype": "Author"}]
        authors_raw = item.get("authors", []) or []
        authors = [a.get("name", "") for a in authors_raw[:3]]

        articles.append(
            PubMedArticle(
                pmid=pmid,
                title=item.get("title", "").rstrip("."),
                authors=authors,
                year=_extract_year(item.get("pubdate", "")),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
        )

    return articles


def _extract_year(pubdate: str) -> str | None:
    """
    從 ESummary 的 pubdate 字串抓年份。
    格式可能是 "2024 Mar 15" / "2024" / "2024 Spring"。
    """
    if not pubdate:
        return None
    # 取開頭 4 個數字
    for i in range(len(pubdate) - 3):
        chunk = pubdate[i : i + 4]
        if chunk.isdigit():
            return chunk
    return None
