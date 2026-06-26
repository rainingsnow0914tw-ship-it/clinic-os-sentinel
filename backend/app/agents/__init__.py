"""
Sentinel 4 個 Agent —— 哨兵守門員

🛡️ 哨兵設計七鐵律(取自 Chat 寶 PRD 與作戰情報 Artifact)：
1. 事實查表，判斷給 AI
2. 醫學知識也查表：AI 斷言必附可驗證來源
3. 入口分類不過濾
4. 對抗警示疲勞(寧少勿濫)
5. AI 提示不拍板(醫生最終決定)
6. AI 寫草稿不寫正式表
7. 模型可抽換(賽後 Chloe 自用版用)

⚠️ 比賽期紀律：模型抽換層存在但 demo/video/README 不強調「可換」。
"""

from app.agents.intake import run_intake_agent
from app.agents.triage import run_triage_agent
from app.agents.audit import run_audit_agent
from app.agents.education import run_education_agent

__all__ = [
    "run_intake_agent",
    "run_triage_agent",
    "run_audit_agent",
    "run_education_agent",
]
