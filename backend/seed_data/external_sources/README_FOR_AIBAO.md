# Clinic Mock Data Package

Extracted from Jimmy's pasted Markdown and cleaned into separate files for Aibao.

## Files
- `MOCK_DATA_PLAN.md`
- `SCENARIOS.md`
- `mock_data.json`

## Counts
- clinic: 1
- users: 6
- patients: 60
- drugs: 30
- drug_batches: 4
- fee_catalog: 5
- visits: 5
- prescription_items: 5
- invoices: 4
- stock_movements: 4
- medical_documents: 2
- ai_drafts: 1
- agent_tasks: 1
- audit_logs: 1

## Notes
- This is mock/dev data only. Do not seed into production.
- `mock_data.json` is valid JSON.
- Some sections are intentionally partial: drug_batches, visits, invoices, stock_movements, ai_drafts, agent_tasks, audit_logs are scenario seeds, not full-scale complete datasets.
- Aibao should create/complete `validate_mock_data.py`, `seed_dev_data.py`, and `reset_dev_data.py`, and generate missing `prescriptions` / `invoice_items` if the database schema requires them.
