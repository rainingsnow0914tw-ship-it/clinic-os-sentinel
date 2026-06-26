"""
Pydantic schemas — API 的 request / response 資料結構

Sprint 0 先放空，每個 Sprint 開始時補對應的 schema 檔案：
- Sprint 1: auth_schemas.py / clinic_schemas.py / user_schemas.py
- Sprint 2: patient_schemas.py / visit_schemas.py
- Sprint 3: drug_schemas.py / batch_schemas.py
- Sprint 4: prescription_schemas.py
- Sprint 5: invoice_schemas.py
- Sprint 6: document_schemas.py
- Sprint 7: ai_schemas.py
- Sprint 8: agent_schemas.py

設計原則：
1. Request schema 命名以 ...Create / ...Update / ...Patch 結尾
2. Response schema 命名以 ...Response 或 ...Read 結尾
3. 不直接在 route 裡寫 dict，全部走 Pydantic 驗證（醫療系統不能容忍髒資料）
"""
