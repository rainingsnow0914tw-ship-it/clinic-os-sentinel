# External mock data sources

Jimmy（Gemini）給的原始 mock data 備份。

格式跟 `MOCK_DATA_PLAN.md` 規範**不同**（欄位命名差異），所以不直接放在
`seed_data/mock_data.json`。要用：

```bash
python -m scripts.import_jimmy_mock \
  --input backend/seed_data/external_sources/mock_data.json \
  --output backend/seed_data/mock_data.json
```

然後跑正常的 validate / seed / reset 流程。
