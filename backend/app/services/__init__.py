"""
Services — 商業邏輯層（business logic）

Routes 只做：請求驗證、權限檢查、呼叫 service、組 response
真正的醫療業務邏輯都在這層，方便單元測試。

未來會有的 services：
- audit_service.py     ← Sprint 1：寫 audit log 的統一入口
- patient_service.py   ← Sprint 2
- visit_service.py     ← Sprint 2
- inventory_service.py ← Sprint 3：FEFO 扣庫存、stock_movements
- prescription_service.py ← Sprint 4：藥量計算、總價計算
- invoice_service.py   ← Sprint 5：開收據、作廢、回補庫存（atomic transaction）
- document_service.py  ← Sprint 6：病假紙 / 轉診信 PDF 生成
- ai_service.py        ← Sprint 7：AI provider 抽象層 + ai_drafts 寫入
- agent_service.py     ← Sprint 8：agent_tasks 排程與 lifecycle

⚠️ 商業底線第 8 條：AI 不可直接寫正式表
    所有 AI 產物先寫 ai_drafts 或 agent_tasks.output_json，由人類確認後
    才由對應的 service（不是 AI service）寫入正式表。
"""
