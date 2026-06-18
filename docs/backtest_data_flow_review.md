# Backtest Data Flow Review

本文件整理目前回測資料鏈路、已完成的欄位補強、舊資料 fallback 規則，以及後續仍需注意的風險。

## 1. 目前資料來源

目前回測主要依賴兩類資料：

- `data/stock_analysis.db`
  - SQLite 資料庫。
  - 儲存每日分析結果，供回測引擎讀取信號資料。
- `analysis_results` table
  - 目前回測讀取的主要信號表。
  - 重要欄位包含 `run_date`、`stock_id`、`stock_name`、各面向分數、`total_score`、`rating`、`action`、`strategy`、`created_at`。
  - 已新增回測信號語意欄位：`signal_session`、`pipeline_type`、`pipeline_run_id`、`signal_time`、`is_backtest_eligible`、`schema_version`。
  - `created_at` 目前由 SQLite `CURRENT_TIMESTAMP` 預設值產生。
- `data/historical/{stock_id}_daily.csv`
  - 每檔股票的歷史日資料。
  - 回測以 `run_date` 對應 CSV 的 `date` 欄位，找到信號日收盤價，再計算後續持有天數報酬。

## 2. 寫入來源

目前寫入 `analysis_results` 的主要來源是盤前 pipeline：

- `app/pipelines/pre_open_pipeline.py`
  - `run_pre_open_pipeline()` 會在非 dry-run 模式下呼叫 `save_analysis_result()`。
  - `save_analysis_result()` 來自 `app/database/analysis_result_repository.py`。
- dry-run 不寫入
  - `dry_run=True` 時會略過 SQLite 初始化、historical CSV 更新、SQLite 寫入、LINE 推播與回測自動補值。
  - dry-run 只輸出分析與推播內容預覽，不產生正式回測信號資料。
- 正式 pre_open 才會寫入
  - 程式流程上，只有非 dry-run 的 `pre_open` 會寫入 `analysis_results`。
  - 正式 `pre_open` 寫入會同步寫入 `signal_session = "pre_open"`、`pipeline_type`、`pipeline_run_id`、Asia/Taipei ISO 8601 格式的 `signal_time`、`is_backtest_eligible = 1`、`schema_version = 1`。

## 3. 回測讀取流程

目前回測相關流程如下：

- `analysis/backtest_engine.py`
  - 從 `data/stock_analysis.db` 的 `analysis_results` 讀取分析結果。
  - 優先以新欄位篩選正式盤前資料：`signal_session = 'pre_open'` 且 `is_backtest_eligible = 1`。
  - 舊資料若 `signal_session` 或 `is_backtest_eligible` 為 `NULL`，fallback 使用 `created_at` 05:00～09:00 判斷盤前資料。
  - 讀取 `data/historical/{stock_id}_daily.csv`。
  - 以 `run_date` 對應歷史 CSV 的 `date`，計算 1、3、5、10、20 日後報酬。
- `analysis/strategy_backtest_engine.py`
  - 同樣從 `analysis_results` 讀取資料，並優先以 `signal_session = 'pre_open'` 且 `is_backtest_eligible = 1` 篩選正式盤前資料。
  - 舊資料若 `signal_session` 或 `is_backtest_eligible` 為 `NULL`，fallback 使用 `created_at` 05:00～09:00 判斷盤前資料。
  - 依策略條件篩選信號，例如 A 級、B 級以上、偏多續抱、總分門檻、ADR 門檻。
  - 輸出策略績效與 `strategy_signal_logs.csv`。
  - signal log 可對應 DB 原始信號欄位中的 `signal_session`，新資料不再只依賴輸出階段補值。
- `analysis/backtest_auto_updater.py`
  - 串接回測更新流程。
  - 依序執行基礎回測、策略回測、策略排行榜。
  - 在 `pre_open_pipeline.py` 非 dry-run 完成後會被呼叫。

## 4. 目前回測基準

目前回測把正式 `pre_open` 信號視為盤前回測基準。

新資料已直接在 `analysis_results` 儲存明確信號欄位：

- `signal_session = "pre_open"`
- `pipeline_type`
- `pipeline_run_id`
- `signal_time` 使用 Asia/Taipei ISO 8601 格式
- `is_backtest_eligible = 1`
- `schema_version = 1`

回測引擎會優先使用 `signal_session` 與 `is_backtest_eligible` 判斷正式盤前信號。

舊資料仍保留 fallback。當 `signal_session` 或 `is_backtest_eligible` 為 `NULL` 時，才使用 `created_at` 的 hour 做時間區間判斷：

- `PRE_OPEN_START_HOUR = 5`
- `PRE_OPEN_END_HOUR = 9`
- 篩選條件為 `05:00 <= created_at.hour < 09:00`

因此，新資料的「盤前信號」已由資料表欄位明確宣告；只有舊資料仍由 `created_at` 推論。

## 5. 已知風險

- 舊資料 fallback 仍依賴 `created_at`。
  - 舊資料若 `signal_session` 或 `is_backtest_eligible` 為 `NULL`，仍需使用 `05:00 <= created_at.hour < 09:00` 判斷。
  - `created_at` 使用 SQLite `CURRENT_TIMESTAMP`，可能是 UTC；舊資料 fallback 仍有時區誤判風險。
- 新欄位只解決新寫入資料的信號語意。
  - 舊資料的新欄位可能仍為 `NULL`，除非另外完成保守回填。
  - 未來新增 `intraday`、`pre_close`、`post_close` 等 session 時，仍需定義是否可進入回測。
- historical CSV 若缺 `run_date`，該筆會被略過。
  - `run_date` 找不到對應 CSV `date` 時，該筆分析結果不會進入回測紀錄。
- 未來日資料不足時 return 會是 pending / None。
  - 若持有天數超過現有歷史資料範圍，基礎報酬會是 `None`。
  - 策略回測會將這類結果判定為 `pending`。

## 6. 已完成補強與後續注意事項

- 已新增並正式遷移 `analysis_results` 欄位。
  - `signal_session`
  - `pipeline_type`
  - `pipeline_run_id`
  - `signal_time`
  - `is_backtest_eligible`
  - `schema_version`
- 已完成正式 `pre_open` 寫入規格。
  - `signal_session = "pre_open"`
  - `pipeline_type` 與 `pipeline_run_id`
  - `signal_time` 使用 Asia/Taipei ISO 8601 格式
  - `is_backtest_eligible = 1`
  - `schema_version = 1`
- 已完成回測讀取條件切換。
  - `backtest_engine.py` 已優先使用新欄位篩選正式 `pre_open` 信號。
  - `strategy_backtest_engine.py` 已優先使用新欄位篩選正式 `pre_open` 信號。
  - 舊資料仍在新欄位為 `NULL` 時 fallback 使用 `created_at` 05:00～09:00。
- migration 已正式執行完成。
  - 目前再執行 dry-run，應看到 6 個新增欄位皆為 `exists`。
- 後續仍需明確定義其他 pipeline 是否可進入回測。
  - 例如 `intraday` 是否進入獨立回測，`post_close` 是否只作研究用途。
  - 這些規則應在資料欄位與回測讀取條件中被持續明確表達。
- 保留 dry-run 不寫入原則。
  - dry-run 應持續避免寫入 SQLite、更新 historical CSV、發送 LINE 與觸發回測補值。
  - 測試資料若未來需要留存，應使用獨立測試 DB 或明確標記，避免污染正式回測信號。
