"""
醫學 API 包裝層 — Sentinel 知識來源

🔒 哨兵鐵律 2：AI 斷言必附可驗證來源連結。不靠 AI 記憶編造醫學知識。

三個免費來源(已查證，見「醫學API查證_方向版.md」)：
- RxNorm   (NLM) — 藥名標準化 → RxCUI
- openFDA  (FDA) — 藥物標籤/警告/交互作用
- PubMed   (NIH) — 醫學文獻索引(前閘門 agent 附鑑別診斷來源)

⚠️ 都是美國英文資料。澳門中文藥名/中成藥可能查不到 →
   查不到就老實標 "unknown"，不瞎猜(符合鐵律「對不確定誠實」)。
"""

from app.medical_apis.rxnorm import standardize_drug_name, RxNormResult
from app.medical_apis.openfda import fetch_interaction_text, fetch_drug_label
from app.medical_apis.pubmed import search_pubmed, PubMedArticle

__all__ = [
    "standardize_drug_name",
    "RxNormResult",
    "fetch_interaction_text",
    "fetch_drug_label",
    "search_pubmed",
    "PubMedArticle",
]
