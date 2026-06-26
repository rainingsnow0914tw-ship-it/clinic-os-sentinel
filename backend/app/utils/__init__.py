"""
Utils — 通用工具函數

之後會放：
- pdf_renderer.py   ← Jinja2 + WeasyPrint 把 template_content 渲染成 PDF
- gcs_uploader.py   ← 上傳 PDF 到 Cloud Storage 並產生 signed URL
- invoice_number.py ← 收據編號生成（格式如 YYYYMMDD-XXXX，每間診所獨立流水號）
- fefo.py           ← FEFO 排序輔助（first expired, first out）
- timezone.py       ← 處理診所時區轉換（每間 clinic 有自己的 timezone）
"""
