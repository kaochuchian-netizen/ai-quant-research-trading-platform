# Backtest Data Flow Review

本文件整理目前回測資料鏈路、已知風險，以及進入 04 階段前建議補強的項目。

## 1. 目前資料來源

目前回測主要依賴兩類資料：

- `data/stock_analysis.db`
  - SQLite 資料庫。
  - 儲存每日分析結果，供回測引擎讀取信號資料。
- `analysis_results` table
  - 目前回測讀取的主要信號表。
  - 重要欄位包含 `run_date`、`stock_id`、`stock_name`、各面向分數、`total_score`、`rating`、`action`、`strategy`、`created_at`。
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
  - 目前 `app/pipelines/runner.py` 對 `pre_open` 的正式執行仍有保護規則；若未來放行正式執行，需同步確認寫入資料可明確標示信號來源。

## 3. 回測讀取流程

目前回測相關流程如下：

- `analysis/backtest_engine.py`
  - 從 `data/stock_analysis.db` 的 `analysis_results` 讀取分析結果。
  - 以 `created_at` 篩選盤前資料。
  - 讀取 `data/historical/{stock_id}_daily.csv`。
  - 以 `run_date` 對應歷史 CSV 的 `date`，計算 1、3、5、10、20 日後報酬。
- `analysis/strategy_backtest_engine.py`
  - 同樣從 `analysis_results` 讀取資料並以 `created_at` 篩選盤前資料。
  - 依策略條件篩選信號，例如 A 級、B 級以上、偏多續抱、總分門檻、ADR 門檻。
  - 輸出策略績效與 `strategy_signal_logs.csv`。
  - 目前輸出的 signal log 中有 `signal_session = "pre_open"`，但這是輸出階段補上的欄位，不是 DB 原始信號欄位。
- `analysis/backtest_auto_updater.py`
  - 串接回測更新流程。
  - 依序執行基礎回測、策略回測、策略排行榜。
  - 在 `pre_open_pipeline.py` 非 dry-run 完成後會被呼叫。

## 4. 目前回測基準

目前回測把 07:00 盤前推播視為信號基準。

實作上並沒有直接儲存 `signal_session` 或 `pipeline_type` 到 `analysis_results`，而是用 `created_at` 的 hour 做時間區間判斷：

- `PRE_OPEN_START_HOUR = 5`
- `PRE_OPEN_END_HOUR = 9`
- 篩選條件為 `05:00 <= created_at.hour < 09:00`

因此，目前「盤前信號」是由 `created_at` 推論而來，不是由資料表中的明確欄位宣告。

## 5. 已知風險

- `created_at` 使用 SQLite `CURRENT_TIMESTAMP`，可能是 UTC。
  - 若部署環境、SQLite 預設時間與 Asia/Taipei 不一致，`05:00 <= hour < 09:00` 可能篩錯資料。
- 缺少明確 `signal_session` 欄位。
  - 目前無法從 DB 原始資料直接分辨 `pre_open`、`intraday`、`pre_close`、`post_close` 等信號 session。
- 未來多 pipeline 寫入時，不能只靠 `created_at` 判斷信號來源。
  - 多個 pipeline 可能在相近時間補跑、重跑或批次寫入，時間不等於信號語意。
- historical CSV 若缺 `run_date`，該筆會被略過。
  - `run_date` 找不到對應 CSV `date` 時，該筆分析結果不會進入回測紀錄。
- 未來日資料不足時 return 會是 pending / None。
  - 若持有天數超過現有歷史資料範圍，基礎報酬會是 `None`。
  - 策略回測會將這類結果判定為 `pending`。

## 6. 進入 04 階段前建議補強

- 新增或規劃 `signal_session` 欄位。
  - 建議明確記錄 `pre_open`、`intraday`、`pre_close`、`post_close` 等信號 session。
  - 回測應以此欄位判斷信號來源，而不是只依賴 `created_at`。
- 明確儲存 `pipeline_type` 或 `pipeline_run_id`。
  - `pipeline_type` 可描述資料來源流程。
  - `pipeline_run_id` 可追蹤單次 pipeline 執行批次，利於重跑、查錯與資料審計。
- 明確處理 Asia/Taipei 時區。
  - 寫入與讀取時應定義統一時區策略。
  - 若保留 SQLite `CURRENT_TIMESTAMP`，需明確轉換或避免用它判斷交易 session。
- 明確定義每個 pipeline 是否可進入回測。
  - 例如 `pre_open` 可作為正式信號，`intraday` 是否進入獨立回測，`post_close` 是否只作研究用途。
  - 這個規則應在資料欄位與回測讀取條件中被明確表達。
- 保留 dry-run 不寫入原則。
  - dry-run 應持續避免寫入 SQLite、更新 historical CSV、發送 LINE 與觸發回測補值。
  - 測試資料若未來需要留存，應使用獨立測試 DB 或明確標記，避免污染正式回測信號。
