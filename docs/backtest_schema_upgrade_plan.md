# Backtest Schema Upgrade Plan

本文件設計進入 04 階段前，`analysis_results` 與回測資料鏈路需要補強的欄位與遷移策略。

本 Task 只做設計文件，不修改 DB schema、不新增 migration、不調整 Python 實作。

## 1. 問題背景

目前回測信號主要從 `analysis_results` 讀取，但資料表缺少足夠明確的信號語意欄位。

- 缺少明確 `signal_session`
  - 目前無法直接從 DB 原始資料判斷該筆分析結果屬於 `pre_open`、`intraday`、`pre_close` 或 `post_close`。
  - 回測若只依靠時間推論 session，未來多 pipeline 寫入後會增加誤判風險。
- 缺少 `pipeline_type`
  - 無法直接辨識該筆資料由哪一類 pipeline 寫入。
  - 未來若不同 pipeline 共用 `analysis_results`，資料來源會變得不清楚。
- 缺少 `pipeline_run_id`
  - 無法追蹤單次 pipeline 執行批次。
  - 重跑、補跑、查錯與審計時，難以將同一批結果串起來。
- `created_at` 可能是 UTC
  - 目前 `created_at` 可能由 SQLite `CURRENT_TIMESTAMP` 產生，實際語意偏向系統或 SQLite 時間，不一定是 Asia/Taipei。
  - 若直接用 `created_at` 判斷交易 session，可能在時區不同時篩錯盤前資料。
  - `created_at` 適合作為寫入時間參考，不適合作為交易 session 的唯一判斷依據。

## 2. 建議新增欄位

建議在 `analysis_results` 補強以下欄位：

| 欄位 | 型別 | 範例 | 說明 |
| --- | --- | --- | --- |
| `signal_session` | `TEXT` | `pre_open` | 信號所屬交易 session。 |
| `pipeline_type` | `TEXT` | `pre_open` | 寫入資料的 pipeline 類型。 |
| `pipeline_run_id` | `TEXT` | `pre_open-20260619-070000` | 單次 pipeline 執行批次 ID。 |
| `signal_time` | `TEXT` | `2026-06-19T07:00:00+08:00` | 信號產生時間，建議儲存 Asia/Taipei 時間。 |
| `is_backtest_eligible` | `INTEGER` | `1` | 是否可進入正式回測，使用 0/1。 |
| `schema_version` | `INTEGER` | `1` | 資料列 schema 版本，方便未來演進。 |

## 3. 欄位用途

### `signal_session`

- 用途
  - 明確標示信號屬於哪個交易 session。
  - 建議初期值包含 `pre_open`、`intraday`、`pre_close`、`post_close`。
- 為什麼需要
  - session 是交易語意，不應只由寫入時間推論。
  - 未來盤中、收盤前、收盤後 pipeline 都可能寫入分析結果，必須能明確區分來源情境。
- 回測使用方式
  - `backtest_engine.py` 可優先篩選 `signal_session = 'pre_open'` 的正式盤前信號。
  - 未來若新增 intraday 回測，可用 `signal_session = 'intraday'` 建立獨立回測邏輯。

### `pipeline_type`

- 用途
  - 記錄資料由哪一類 pipeline 寫入。
  - 可與 runner 支援的 pipeline 名稱保持一致。
- 為什麼需要
  - `signal_session` 描述交易信號語意，`pipeline_type` 描述系統流程來源。
  - 兩者初期可能相同，但未來可能出現同一 pipeline 產出多種 session，或研究 pipeline 產出非正式信號。
- 回測使用方式
  - 回測主要不應只依賴 `pipeline_type` 判斷是否可用，但可用於查錯與結果追溯。
  - 當某批資料異常時，可用 `pipeline_type` 快速確認來源流程。

### `pipeline_run_id`

- 用途
  - 串接同一次 pipeline 執行產生的多筆分析結果。
  - 讓每次正式執行、補跑或重跑都有可追蹤的批次 ID。
- 為什麼需要
  - 同一個 `run_date` 可能因補跑、修正或不同 pipeline 重複寫入多批資料。
  - 沒有批次 ID 時，很難定位某筆資料屬於哪一次執行。
- 回測使用方式
  - 回測結果可保留或輸出 `pipeline_run_id`，方便追蹤信號來源。
  - 若同日多批信號並存，未來可依 `pipeline_run_id` 選擇最新批次、指定批次或排除異常批次。

### `signal_time`

- 用途
  - 記錄信號真正產生或對外生效的時間。
  - 建議以 ISO 8601 格式儲存 Asia/Taipei 時間，例如 `2026-06-19T07:00:00+08:00`。
- 為什麼需要
  - `created_at` 只代表 DB 寫入時間，且可能是 UTC。
  - 信號時間應反映交易決策可被採用的時間點。
- 回測使用方式
  - 回測可用 `signal_time` 判斷信號是否在交易前、交易中或交易後產生。
  - 盤前回測可確認 `signal_time` 落在盤前規則允許範圍，而不是依賴 `created_at` hour。

### `is_backtest_eligible`

- 用途
  - 明確標示該筆信號是否可進入正式回測。
  - 使用 `INTEGER` 儲存 0/1，便於 SQLite 篩選。
- 為什麼需要
  - 不是所有分析結果都適合回測。
  - intraday、pre_close、post_close 的方法尚未定義前，若直接混入盤前回測會污染績效。
- 回測使用方式
  - 回測引擎可優先篩選 `is_backtest_eligible = 1`。
  - 初期可搭配 `signal_session = 'pre_open'`，形成正式盤前回測資料集。

### `schema_version`

- 用途
  - 標記資料列符合哪個 schema 寫入規格。
  - 初期建議從 `1` 開始。
- 為什麼需要
  - 未來欄位新增、語意修正或回測規則變更時，可保留資料版本資訊。
  - 舊資料與新資料共存時，版本欄位有助於判斷可用欄位與轉換邏輯。
- 回測使用方式
  - 回測引擎可依 `schema_version` 決定使用新欄位或 fallback 到舊邏輯。
  - 若未來新增更嚴格信號規格，可只納入特定版本以上的資料。

## 4. 初期建議規則

- `pre_open`
  - `is_backtest_eligible = 1`
  - 作為目前正式盤前回測的主要信號來源。
- `intraday`
  - `is_backtest_eligible = 0`
  - 暫時不進入正式回測，等 intraday 回測方法、進出場價格與持有規則定義後再開啟。
- `pre_close`
  - `is_backtest_eligible = 0`
  - 暫時不進入正式回測，避免與盤前信號混用。
- `post_close`
  - `is_backtest_eligible = 0`
  - 初期可視為 research-only，除非後續定義專屬收盤後研究或隔日交易回測規則。
- dry-run
  - 永遠不寫入 DB。
  - 不應產生正式 `analysis_results` 紀錄，也不應進入回測資料鏈路。

## 5. 遷移策略

### 第一階段：只新增欄位

- 在 DB schema 新增欄位，但允許舊資料為 `NULL`。
- 不立即要求舊資料回填。
- 不破壞既有 `analysis_results` 查詢與回測流程。

### 第二階段：寫入新欄位

- 調整 `save_analysis_result()`，讓新的正式寫入資料帶入：
  - `signal_session`
  - `pipeline_type`
  - `pipeline_run_id`
  - `signal_time`
  - `is_backtest_eligible`
  - `schema_version`
- dry-run 維持不寫入 DB。
- 寫入邏輯應由 pipeline context 提供 `pipeline_type` 與 `pipeline_run_id`，避免每個呼叫點自行組裝。

### 第三階段：回測優先使用新欄位

- 調整 `backtest_engine.py` 優先使用：
  - `signal_session`
  - `is_backtest_eligible`
  - `signal_time`
- 新資料應以 `signal_session = 'pre_open'` 且 `is_backtest_eligible = 1` 作為正式盤前回測條件。
- 舊資料若新欄位為 `NULL`，可暫時 fallback 到現有 `created_at` hour 判斷，直到回填策略完成。

### 第四階段：考慮回填舊資料

- 在新寫入與新回測邏輯穩定後，再評估是否回填舊資料。
- 回填規則需要保守：
  - 只對可高信心判定為盤前正式信號的資料補 `signal_session = 'pre_open'`。
  - 無法確認來源的資料應保留 `NULL` 或標記為不可回測。
  - 回填前需先備份 DB，並產生可審查的 dry-run report。

## 6. 風險控管

- 不直接破壞既有 `analysis_results`
  - 新欄位初期允許 `NULL`。
  - 既有欄位與既有查詢不應被移除或改名。
- 不一次重構回測引擎
  - 先讓資料寫入具備足夠語意，再逐步調整回測讀取條件。
  - 初期保留舊資料 fallback，降低切換風險。
- migration 需可重複執行
  - 新增欄位的 migration 應檢查欄位是否已存在。
  - 重跑 migration 不應造成錯誤或重複欄位。
- 新舊資料需可共存
  - 舊資料可維持新欄位為 `NULL`。
  - 新資料使用明確欄位供回測篩選。
  - 回測讀取邏輯在過渡期需同時支援新舊資料。
- dry-run 不得污染正式資料
  - dry-run 不寫入 DB、不更新回測資料、不觸發正式信號鏈路。
  - 若未來需要保存測試結果，應使用獨立測試 DB 或明確的測試資料表。
