# 資源盤點操作指引

使用 `ops/scripts/collect_system_info.py` 可快速收集 CPU / RAM / 磁碟 / GPU 狀況並輸出 JSON 報告。

```bash
python ops/scripts/collect_system_info.py
# 或指定輸出路徑
python ops/scripts/collect_system_info.py --output docs/infra/system_report.json
```

建議於重大升級前執行，並將輸出檔案提交到 `docs/infra/` 以便日後比對。
