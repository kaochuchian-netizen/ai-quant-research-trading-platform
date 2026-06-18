# Backtest Migration Runbook

本文件定義正式執行 `app/database/migrations/001_add_backtest_signal_fields.py` 前後的備份、檢查、驗證與 rollback 流程。

此 runbook 只適用於手動維護 SQLite schema。不要把 migration 接進交易推播流程、`main.py` 或 pipeline 自動流程。

## 1. 執行前原則

- 不在交易推播流程中執行 migration。
- 不從 `main.py` 執行 migration。
- 不從 pipeline 自動執行 migration。
- 正式執行前必須先備份 `data/stock_analysis.db`。
- 正式執行前必須先跑 `--dry-run`，確認目前欄位狀態。

## 2. 備份指令

建議將備份放在 `data/backups/`，檔名包含 timestamp，並使用 `cp` 保留原 DB。

```bash
mkdir -p data/backups
cp data/stock_analysis.db "data/backups/stock_analysis_$(date +%Y%m%d_%H%M%S).db"
```

備份完成後，確認備份檔存在：

```bash
ls -lh data/backups/stock_analysis_*.db
```

## 3. 執行前檢查

確認 Git 工作樹乾淨：

```bash
git status --short
```

預期沒有輸出。若有任何未提交變更，先釐清來源，不要在狀態不明時執行 migration。

確認正式 DB 存在：

```bash
test -f data/stock_analysis.db && echo "DB exists"
```

執行 dry-run：

```bash
python3 app/database/migrations/001_add_backtest_signal_fields.py --dry-run
```

預期看到以下 6 個欄位狀態為 `missing`，或在部分欄位已建立過的情況下顯示部分 `exists`：

- `signal_session`
- `pipeline_type`
- `pipeline_run_id`
- `signal_time`
- `is_backtest_eligible`
- `schema_version`

若 dry-run 報錯、DB 不存在、表格不存在，或輸出與預期欄位不一致，停止執行並先調查。

## 4. 正式執行指令

正式執行：

```bash
python3 app/database/migrations/001_add_backtest_signal_fields.py
```

此步會修改 `data/stock_analysis.db` 的 SQLite schema，對 `analysis_results` 執行 `ALTER TABLE ... ADD COLUMN`。

## 5. 執行後驗證

再次執行 dry-run：

```bash
python3 app/database/migrations/001_add_backtest_signal_fields.py --dry-run
```

預期 6 個欄位都顯示 `exists`。

使用 `sqlite3` 檢查 `analysis_results` schema：

```bash
sqlite3 data/stock_analysis.db "PRAGMA table_info(analysis_results);"
```

確認輸出包含以下欄位：

- `signal_session`
- `pipeline_type`
- `pipeline_run_id`
- `signal_time`
- `is_backtest_eligible`
- `schema_version`

確認 Git 工作樹仍乾淨：

```bash
git status --short
```

預期仍沒有輸出。`data/stock_analysis.db` 不應被 Git 追蹤，因此 schema 修改不應造成 Git diff。

## 6. Rollback 原則

若 migration 後需要 rollback：

1. 停止 pipeline，避免過程中有程式讀寫 DB。
2. 使用備份 DB 覆蓋回正式 DB。
3. 再跑 `--dry-run` 確認欄位狀態。
4. Rollback 後不要自動重跑 pipeline，先人工確認系統狀態。

範例指令：

```bash
cp data/backups/stock_analysis_YYYYMMDD_HHMMSS.db data/stock_analysis.db
python3 app/database/migrations/001_add_backtest_signal_fields.py --dry-run
```

Rollback 後 dry-run 的結果應回到備份當下的欄位狀態。

## 7. 風險說明

- `ALTER TABLE` 會修改正式 SQLite DB schema。
- Migration 以欄位是否存在判斷，可重複執行，但正式執行前仍應先備份。
- 舊資料的新欄位值會是 `NULL`。
- Python 尚未寫入新欄位前，新增 schema 不會自動改善回測篩選。
