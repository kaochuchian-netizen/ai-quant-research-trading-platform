# Strategy Signal Logs Upgrade Plan

本文件設計 04 階段 `strategy_signal_logs.csv` 的欄位擴充方向。目標是讓後續策略指標、排行榜、回測追溯與風控分析有足夠資料基礎。

本文件只定義設計方向，不代表已實作。04 階段仍維持 research-only，不直接影響正式 LINE 推播、自動下單或 production 策略。

## 1. 目前 strategy_signal_logs.csv 定位

`strategy_signal_logs.csv` 是 04 階段策略分析的重要基礎，主要定位如下：

- 由 `strategy_backtest_engine.py` 產生。
- 用於記錄策略命中的信號明細。
- 連接策略條件、信號來源、持有天期與未來報酬。
- 作為策略指標、策略排行榜、回測追溯與風險分析的原始明細資料。

目前它不應被視為正式交易指令，也不應直接作為 LINE 推播內容來源。任何策略啟用前仍需另行完成回測、風控門檻與人工確認。

## 2. 目前既有欄位

目前已知欄位如下：

| 欄位 | 說明 |
| --- | --- |
| `strategy_name` | 策略名稱。 |
| `signal_session` | 信號所屬交易 session，例如 `pre_open`。 |
| `run_date` | 回測或信號所屬日期。 |
| `future_date` | 用於計算未來報酬的目標日期。 |
| `stock_id` | 股票代號。 |
| `stock_name` | 股票名稱。 |
| `rating` | 分析評級。 |
| `action` | 分析建議或策略動作。 |
| `total_score` | 總分。 |
| `adr_score` | ADR 分數。 |
| `holding_days` | 持有天期。 |
| `future_return_pct` | 持有期未來報酬百分比。 |
| `result` | 回測結果分類或狀態。 |

## 3. 建議新增欄位

建議新增欄位如下。本階段只設計，不實作：

| 欄位 | 類型建議 | 初期語意 |
| --- | --- | --- |
| `pipeline_run_id` | text | 信號來源 pipeline 執行批次。 |
| `signal_time` | text | 信號產生或可被交易採用的時間。 |
| `pipeline_type` | text | 寫入信號的 pipeline 類型。 |
| `schema_version` | integer | `strategy_signal_logs.csv` 資料列 schema 版本。 |
| `chip_score` | numeric | 籌碼分數。 |
| `technical_score` | numeric | 技術面分數。 |
| `news_score` | numeric | 新聞面分數。 |
| `strategy_version` | text | 策略條件或公式版本。 |
| `strategy_group` | text | 策略分類或研究群組。 |
| `entry_price` | numeric | 回測進場價格。 |
| `exit_price` | numeric | 回測出場價格。 |
| `max_drawdown_during_holding` | numeric | 單筆交易持有期間最大回撤。 |
| `return_rank` | integer | 同批或同策略內報酬排序。 |
| `is_completed` | boolean / integer | 是否已完成持有期並可計算最終結果。 |
| `is_valid_for_ranking` | boolean / integer | 是否符合排行榜納入條件。 |

## 4. 新增欄位用途

### `pipeline_run_id`

- 欄位用途：追蹤每筆信號屬於哪一次 pipeline 執行批次。
- 來源資料：`analysis_results.pipeline_run_id` 或 pipeline 執行上下文。
- 是否必要：高優先必要欄位。
- 是否可先留空：可。舊資料或無法追溯批次的資料可留空。
- 對 04 指標的幫助：支援批次追溯、異常批次排除、同日多批信號去重，避免排行榜混用不同來源批次。

### `signal_time`

- 欄位用途：記錄信號真正產生或可被交易採用的時間。
- 來源資料：`analysis_results.signal_time`，建議使用 Asia/Taipei ISO 8601 時間。
- 是否必要：高優先必要欄位。
- 是否可先留空：可。舊資料可 fallback 使用既有日期欄位，但精準度較低。
- 對 04 指標的幫助：支援依時間排序、確認信號是否符合盤前或盤中語意，避免用寫入時間推論交易可用性。

### `pipeline_type`

- 欄位用途：標示信號來自哪一類 pipeline，例如 `pre_open`、`intraday`、`pre_close` 或 `post_close`。
- 來源資料：`analysis_results.pipeline_type` 或 pipeline runner。
- 是否必要：建議必要。
- 是否可先留空：可。舊資料可留空或由 `signal_session` 輔助判讀。
- 對 04 指標的幫助：支援分 pipeline 評估策略績效，避免不同交易情境的信號混入同一組排行榜。

### `schema_version`

- 欄位用途：標示該資料列符合的 `strategy_signal_logs.csv` schema 版本。
- 來源資料：回測輸出邏輯固定寫入。
- 是否必要：建議必要。
- 是否可先留空：可。舊資料缺欄時視為 legacy schema。
- 對 04 指標的幫助：支援欄位演進與 fallback 判斷，避免新舊資料語意混用。

### `chip_score`

- 欄位用途：保存策略命中當下的籌碼分數。
- 來源資料：分析結果中的籌碼面計算結果。
- 是否必要：中期必要。
- 是否可先留空：可。若當前資料源尚未穩定，可先保留空值。
- 對 04 指標的幫助：支援籌碼條件策略、分數分層績效分析與穩定度檢查。

### `technical_score`

- 欄位用途：保存策略命中當下的技術面分數。
- 來源資料：分析結果中的技術面計算結果。
- 是否必要：中期必要。
- 是否可先留空：可。
- 對 04 指標的幫助：支援技術面策略分層、趨勢條件比較、報酬與技術強度關聯分析。

### `news_score`

- 欄位用途：保存策略命中當下的新聞面分數。
- 來源資料：分析結果中的新聞分析或情緒分數。
- 是否必要：中期必要。
- 是否可先留空：可。新聞資料缺漏或尚未標準化時可留空。
- 對 04 指標的幫助：支援新聞面策略研究，檢查新聞分數是否改善勝率、平均報酬或穩定度。

### `strategy_version`

- 欄位用途：標示策略條件、門檻或公式版本。
- 來源資料：策略定義檔、策略函式常數或回測輸出設定。
- 是否必要：高優先必要欄位。
- 是否可先留空：可。初期 legacy 策略可留空，但新策略應固定寫入。
- 對 04 指標的幫助：支援同名策略不同版本的績效比較，避免排行榜把不同策略邏輯合併計算。

### `strategy_group`

- 欄位用途：標示策略所屬分類，例如 `score_threshold`、`rating_action`、`adr_filter`、`chip_filter`、`technical_trend` 或 `hybrid`。
- 來源資料：策略定義或回測輸出設定。
- 是否必要：建議必要。
- 是否可先留空：可。
- 對 04 指標的幫助：支援分群排行榜、策略族群穩定度檢查與 overfitting 風險比較。

### `entry_price`

- 欄位用途：保存回測進場價格。
- 來源資料：historical CSV 或後續明確定義的進場價格資料源。
- 是否必要：中後期必要。
- 是否可先留空：可。若初期僅使用 `future_return_pct`，可暫時不填。
- 對 04 指標的幫助：支援報酬重算、交易成本與滑價模擬、異常報酬查核。

### `exit_price`

- 欄位用途：保存回測出場價格。
- 來源資料：historical CSV 或後續明確定義的出場價格資料源。
- 是否必要：中後期必要。
- 是否可先留空：可。
- 對 04 指標的幫助：支援報酬重算、進出場價格審計與持有期績效追溯。

### `max_drawdown_during_holding`

- 欄位用途：保存單筆交易在持有期間內相對進場後高點或進場價的最大不利變動。
- 來源資料：持有期間 historical CSV 逐日價格。
- 是否必要：風控指標必要，但可後置。
- 是否可先留空：可。最大回撤計算方式尚未固定前不應填入模糊值。
- 對 04 指標的幫助：支援單筆交易風險分析、策略 `max_drawdown` 近似計算與風控門檻設計。

### `return_rank`

- 欄位用途：標示同批、同策略或同持有天期內的報酬排序。
- 來源資料：由回測結果依 `future_return_pct` 或後續標準報酬欄位計算。
- 是否必要：低優先輔助欄位。
- 是否可先留空：可。排行榜可先即時計算。
- 對 04 指標的幫助：支援報酬集中度與穩定度檢查，辨識策略績效是否依賴少數極端交易。

### `is_completed`

- 欄位用途：標示持有天期是否已結束，且是否已有足夠資料計算最終報酬。
- 來源資料：`future_date`、historical CSV 可用日期與回測結果狀態。
- 是否必要：高優先必要欄位。
- 是否可先留空：可。舊資料可由 `future_return_pct` 是否為空或 `result` 推論，但新資料應明確寫入。
- 對 04 指標的幫助：直接支援 `trade_count`、`pending_count`、`pending_ratio`、`win_rate` 與 `avg_return` 的穩定計算。

### `is_valid_for_ranking`

- 欄位用途：標示該筆信號是否符合排行榜納入條件。
- 來源資料：回測資格規則、資料完整性檢查、策略狀態與風控規則。
- 是否必要：高優先必要欄位。
- 是否可先留空：可。初期排行榜可先由規則即時計算，但後續建議明確落欄。
- 對 04 指標的幫助：避免資料缺漏、未完成信號、異常價格或不合格策略污染排行榜。

## 5. 與 strategy_metrics_definition.md 的關係

新增欄位應支援 `docs/strategy_metrics_definition.md` 定義的核心指標。建議關係如下：

| 指標 | 主要支援欄位 | 說明 |
| --- | --- | --- |
| `trade_count` | `is_completed`, `is_valid_for_ranking`, `future_return_pct`, `holding_days`, `strategy_name`, `strategy_version` | 計算已完成且可納入評估的交易筆數。 |
| `pending_count` | `is_completed`, `future_date`, `signal_time`, `holding_days` | 計算尚未完成或資料不足的信號筆數。 |
| `pending_ratio` | `is_completed`, `is_valid_for_ranking` | 由 completed 與 pending 筆數計算結果成熟度。 |
| `win_rate` | `is_completed`, `is_valid_for_ranking`, `future_return_pct` | 只用已完成且有效的交易計算獲利比例。 |
| `avg_return` | `is_completed`, `is_valid_for_ranking`, `future_return_pct`, `entry_price`, `exit_price` | 初期可用 `future_return_pct`，後續可由進出場價重算。 |
| `cumulative_return` | `is_completed`, `is_valid_for_ranking`, `future_return_pct`, `signal_time`, `run_date` | 依交易順序建立累積報酬或資金曲線。 |
| `max_drawdown` | `future_return_pct`, `signal_time`, `run_date`, `max_drawdown_during_holding`, `entry_price`, `exit_price` | 初期可由交易序列近似，後續可加入持有期間最大不利變動。 |
| `sharpe_like_score` | `is_completed`, `is_valid_for_ranking`, `future_return_pct` | 由已完成交易報酬平均與標準差計算。 |
| `stability_score` | `strategy_group`, `strategy_version`, `stock_id`, `signal_time`, `return_rank`, `chip_score`, `technical_score`, `news_score` | 支援分策略、分股票、分期間與分條件穩定度檢查。 |

其中 `pipeline_run_id`、`pipeline_type`、`schema_version` 雖然不一定直接進入公式，但會影響資料篩選、版本判斷與結果追溯，是避免指標失真的基礎欄位。

## 6. 擴充原則

`strategy_signal_logs.csv` 的擴充應遵守以下原則：

- 不破壞既有 CSV 消費者。
- 優先 append 欄位，不改既有欄位名稱。
- 舊資料可維持缺欄，不要求一次性回填。
- 新欄位語意應能從原始信號、回測資料或策略定義追溯。
- 欄位缺值應代表資料尚不可得，不應用主觀推測補值。
- 04 階段維持 research-only。
- 新欄位不直接影響 LINE 推播。
- 不因欄位新增而改變正式 pipeline、Google Sheet 設定、cron 或 production `.env`。
- 排行榜與風控規則應能辨識 legacy rows 與新 schema rows。

## 7. 建議實作順序

建議分階段實作，降低對既有流程的影響。

### 第一階段：先補追溯欄位

優先新增：

- `pipeline_run_id`
- `signal_time`
- `pipeline_type`
- `schema_version`
- `strategy_version`
- `strategy_group`
- `is_completed`

目的：

- 讓每筆策略信號能追溯到來源批次、時間、pipeline 與策略版本。
- 讓 pending 與 completed 的判斷更穩定。
- 為 `trade_count`、`pending_count`、`pending_ratio` 建立明確資料基礎。

### 第二階段：再補分數欄位

新增：

- `chip_score`
- `technical_score`
- `news_score`

目的：

- 支援分數分層與策略條件拆解。
- 評估籌碼、技術、新聞分數對勝率、平均報酬與穩定度的影響。

### 第三階段：再補價格欄位

新增：

- `entry_price`
- `exit_price`

目的：

- 支援報酬重算、價格審計、交易成本與滑價模擬。
- 降低只依賴 `future_return_pct` 的追溯風險。

### 第四階段：最後補 max drawdown / ranking flags

新增或啟用：

- `max_drawdown_during_holding`
- `return_rank`
- `is_valid_for_ranking`

目的：

- 強化風控分析與排行榜品質。
- 避免極端交易、未完成信號或不合格資料扭曲策略排序。
- 為後續最大回撤與穩定度計算建立可檢查的明細欄位。

## 8. 初期不做事項

本設計文件不包含以下實作：

- 不修改 Python。
- 不修改 DB。
- 不新增或修改 CSV。
- 不執行 `main.py`。
- 不執行回測。
- 不改 LINE 推播邏輯。
- 不改 cron、Google Sheet 設定或 production `.env`。
