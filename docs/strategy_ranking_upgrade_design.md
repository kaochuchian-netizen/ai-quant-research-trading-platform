# Strategy Ranking Upgrade Design

本文件設計 04 階段 `strategy_ranking_engine.py` 的策略排行榜升級方向。目標是讓策略排名不只看報酬，也納入樣本數、pending、最大回撤、風險調整報酬與穩定度。

本文件只定義設計方向，不修改既有程式、不執行回測、不代表正式策略啟用，也不直接影響 LINE 推播、自動下單或 production 行為。

## 1. 升級背景

目前策略排行榜已有基礎排序能力，可用於檢視策略回測結果與初步比較不同策略表現。04 階段需要將排行榜從單純績效排序升級為 research-only 的策略比較與風險過濾工具。

排行榜不應只看勝率或累積報酬。高勝率可能伴隨少數大虧損，累積報酬也可能由少數極端交易貢獻。若忽略樣本數、pending 比例、最大回撤與穩定度，排行榜容易高估尚未成熟或風險過高的策略。

04 階段排行榜應支援以下用途：

- 比較不同 research-only 策略、策略版本與持有天期。
- 過濾樣本數不足、pending 過高或風險過大的策略。
- 協助找出可進一步觀察的策略候選，而不是直接決定正式啟用。
- 保留可解釋欄位，讓每個策略排名結果能說明進入或排除原因。

## 2. 排行榜核心原則

排行榜升級應遵守以下原則：

- 不用單一指標排序。
- 先過濾不適合排名的策略。
- 再做多指標排序。
- 樣本數不足不可正式比較。
- pending 過高不可正式判斷。
- `max_drawdown` 是必要風控欄位。
- 所有策略在 04 階段仍維持 research-only，不因排行榜名次改變正式推播或交易行為。

建議流程是先用最低門檻排除不適合正式比較的策略，再對通過門檻的策略做多指標排序。被排除的策略仍可顯示在研究結果中，但應清楚標示 `ranking_status` 與 `ranking_reason`。

## 3. 建議輸出欄位

以下欄位為後續 `strategy_ranking_engine.py` 的建議輸出設計，本文件不實作：

| 欄位 | 說明 |
| --- | --- |
| `strategy_name` | 策略名稱。 |
| `strategy_version` | 策略條件、門檻或公式版本。 |
| `strategy_group` | 策略分類或研究群組，例如 `score_threshold`、`rating_action`、`adr_filter`、`chip_filter`、`technical_trend` 或 `hybrid`。 |
| `holding_days` | 持有天期，用於區分不同回測口徑。 |
| `trade_count` | 已完成且可計算報酬的交易筆數。 |
| `pending_count` | 尚未完成或暫時無法計算最終報酬的信號筆數。 |
| `pending_ratio` | `pending_count / (trade_count + pending_count)`，分母為 0 時應標記為無法評估。 |
| `win_rate` | 已完成交易中報酬大於 0 的比例。 |
| `avg_return` | 已完成交易的平均報酬。 |
| `cumulative_return` | 依交易報酬累乘後的累積報酬。 |
| `max_drawdown` | 策略簡化 equity curve 的最大回撤。 |
| `sharpe_like_score` | 報酬相對波動的簡化風險調整分數。 |
| `stability_score` | 績效穩定度輔助分數，用於辨識是否集中在少數交易、股票或期間。 |
| `ranking_status` | 排行榜狀態，用於標記策略是否可進入候選觀察或被排除原因。 |
| `ranking_reason` | 人類可讀的狀態原因，例如樣本不足、pending 過高或回撤超標。 |

## 4. `ranking_status` 設計

`ranking_status` 應使用固定值，避免下游報表或 dashboard 依賴自由文字判斷。

| 狀態 | 語意 |
| --- | --- |
| `research_only` | 僅供研究檢視，不代表可正式比較或啟用。可用於預設狀態或尚未完成完整排名檢查的策略。 |
| `insufficient_sample` | `trade_count` 未達最低門檻，樣本不足以正式比較。 |
| `too_many_pending` | `pending_ratio` 過高，已完成交易不足以代表完整策略結果。 |
| `risk_rejected` | `max_drawdown` 超過可接受範圍，或風險欄位缺失導致無法通過風控檢查。 |
| `candidate_watchlist` | 通過初步樣本數、pending 與回撤門檻，可列入候選觀察，但仍不代表正式策略。 |

若同一策略同時符合多個排除條件，初期建議使用明確優先順序：

1. `insufficient_sample`
2. `too_many_pending`
3. `risk_rejected`
4. `candidate_watchlist`

`ranking_reason` 應保留具體原因與門檻資訊，例如 `trade_count 12 < minimum 20` 或 `pending_ratio 0.42 > maximum 0.30`。這能讓研究者判斷策略是資料尚未成熟、風險不合格，或只是需要更多樣本。

## 5. 初期排序邏輯

初期排行榜應先通過門檻，再進行排序。

建議門檻檢查：

1. `trade_count` 需達最低門檻。初期可參考至少 20 筆已完成交易，但實際門檻應集中設定並可調整。
2. `pending_ratio` 不可過高。初期可參考不高於 30%，避免未完成信號扭曲判讀。
3. `max_drawdown` 不可過大。具體上限應依持有天期、策略類型與風險承受度另行定義。
4. 缺少必要風控欄位時，不應讓策略進入 `candidate_watchlist`。

通過門檻後，排序不應只使用單一欄位。建議以以下指標綜合排序：

- `avg_return`：衡量單筆交易平均期望值。
- `cumulative_return`：衡量策略期間整體報酬。
- `sharpe_like_score`：衡量報酬相對波動的風險調整表現。
- `stability_score`：作為輔助，用於降低績效集中或不穩定策略的優先度。

排序設計應避免單一極端交易主導排名。可採取的設計方向包含：

- 對 `trade_count` 設最低門檻，樣本過少不納入候選排序。
- 對報酬分布做穩定度檢查，辨識累積報酬是否由少數交易貢獻。
- 讓 `sharpe_like_score` 與 `max_drawdown` 影響排序，避免高報酬高波動策略直接排前面。
- 使用 `stability_score` 輔助調整同分或近似分數策略的排序。
- 排行榜顯示名次時，同時顯示 `ranking_status` 與 `ranking_reason`，避免使用者只看第一名。

## 6. 與既有文件關係

本文件與既有 04 階段文件的關係如下：

| 文件 | 關係 |
| --- | --- |
| `docs/strategy_metrics_definition.md` | 定義排行榜使用的核心指標語意，例如 `trade_count`、`pending_ratio`、`max_drawdown`、`sharpe_like_score` 與 `stability_score`。本文件沿用這些欄位作為排行榜輸出與排序基礎。 |
| `docs/strategy_signal_logs_upgrade_plan.md` | 定義 `strategy_signal_logs.csv` 後續應補足的資料欄位，例如 `strategy_version`、`strategy_group`、`is_completed` 與 `is_valid_for_ranking`。這些欄位是排行榜穩定計算與追溯的資料基礎。 |
| `docs/max_drawdown_calculation_design.md` | 定義 `max_drawdown` 初期計算口徑、資料需求與限制。本文件將 `max_drawdown` 視為排行榜必要風控欄位。 |
| `docs/strategy_optimization_phase_04.md` | 定義 04 階段 research-only、風控優先與策略優化任務拆分。本文件對應其中的 04-04 策略排行榜升級。 |

## 7. 實作建議順序

後續若要落實本設計，建議採小步驟實作：

1. 先新增純函式計算 `ranking_status` 與 `ranking_reason`。
2. 再新增 `max_drawdown` 計算，並固定負值或絕對幅度口徑。
3. 再擴充 `strategy_ranking_engine.py` 輸出欄位。
4. 再調整排序邏輯，讓通過門檻的策略使用多指標排序。
5. 最後補文件與 smoke test，確認欄位、狀態與排序行為符合 research-only 原則。

實作時應優先使用純函式處理門檻與排序規則，讓測試可以直接覆蓋樣本不足、pending 過高、回撤超標與候選觀察等情境。

## 8. 初期不做事項

本設計明確不做以下事項：

- 不啟用正式策略。
- 不改 LINE 推播。
- 不自動下單。
- 不把排行榜第一名直接視為正式策略。
- 不執行 production side effect。
- 不修改 Google Sheet 設定。
- 不修改 cron 排程。
- 不修改 production `.env`。
- 不回填或刪除既有 CSV、SQLite 或回測輸出資料。

04 階段排行榜的用途是研究、比較與風險過濾。任何正式策略啟用、LINE 推播變更或 production 行為調整，都應在後續獨立 task 中明確設計、審查與驗證。
