# Max Drawdown Calculation Design

本文件定義 04 階段策略回測使用的最大回撤 `max_drawdown` 初期計算方式。此設計先作為研究與排行榜風控口徑，不修改既有程式、不代表真實投組績效，也不直接影響正式 LINE 推播或自動交易。

## 1. 最大回撤定位

最大回撤用於衡量策略資金曲線從歷史高點下跌到後續低點的最大下跌風險。它回答的是：在指定策略、持有天期與回測期間內，若依策略交易結果逐筆累積，資金曲線曾經承受過多大的下跌。

`max_drawdown` 是策略排行榜與正式啟用門檻的重要風控指標。策略不應只看平均報酬或勝率，因為高勝率可能伴隨少數重大虧損，平均報酬也可能被少數極端獲利交易拉高。若忽略最大回撤，排行榜可能高估高波動或高尾端風險策略的品質。

## 2. 初期計算口徑

04 階段初期先以已完成交易的 `future_return_pct` 建立簡化 equity curve。此 equity curve 是研究用近似口徑，用來讓策略排行榜具備基本回撤檢查能力。

初期排序規則：

1. 以同一 `strategy_name`、`holding_days`、`strategy_version` 為主要分組。
2. 只納入已完成且可用於排名的交易。
3. 依 `signal_time` 排序。
4. 若 `signal_time` 不可用，改用 `run_date` 排序。
5. 若時間欄位仍不足以穩定排序，後續實作應補充明確排序欄位，不應依 CSV 原始列順序作為長期口徑。

初期資金曲線假設：

- 每筆交易等權重。
- 每筆交易依排序結果 sequential compounding。
- 不考慮同一時間多筆信號的資金分配問題。
- 初始 `equity` 可設為 `1.0`。

逐筆計算公式：

```text
equity = equity * (1 + future_return_pct / 100)
peak_equity = max(歷史 peak_equity, equity)
drawdown = (equity - peak_equity) / peak_equity
max_drawdown = min(drawdown)
```

呈現方式可採以下其中一種，但需在輸出欄位文件中固定：

- 負值口徑：例如 `-0.18` 或 `-18%`，表示最大下跌 18%。
- 絕對幅度口徑：例如 `0.18` 或 `18%`，表示最大回撤幅度 18%。

若排行榜欄位使用 `max_drawdown`，建議初期保留負值口徑，因為它直接對應 `drawdown` 的最小值；若 UI 或報表需要顯示風險幅度，可另外轉為正值顯示。

## 3. 資料需求

初期最大回撤應由 `strategy_signal_logs.csv` 計算，必要或建議欄位如下：

| 欄位 | 用途 |
| --- | --- |
| `strategy_name` | 策略分組與排行榜識別 |
| `holding_days` | 持有天期分組，避免不同持有期間混算 |
| `future_return_pct` | 已完成交易報酬，用於建立 equity curve |
| `result` | 判斷交易結果狀態與輔助檢查 |
| `is_completed` | 判斷是否已完成、可納入已完成交易曲線 |
| `is_valid_for_ranking` | 判斷是否可納入排行榜計算 |
| `signal_time` | 優先交易排序欄位 |
| `run_date` | `signal_time` 不可用時的替代排序欄位 |
| `strategy_version` | 區分不同策略版本，避免混合不同邏輯結果 |

後續若 backtest records 也提供等價欄位，可沿用相同語意，但同一排行榜輸出應避免同時混用多個資料來源而未標示來源。

## 4. Pending 與 Invalid Row 處理

Pending 交易不納入已完成 equity curve。常見 pending 狀態包含尚未到達持有天期、未來價格資料不足，或暫時無法計算 `future_return_pct`。將 pending 交易強行視為 0 報酬或虧損，會扭曲回撤與累積報酬。

Invalid row 不納入排行榜計算。若 `is_valid_for_ranking` 為 false，該列不應進入 `trade_count`、`avg_return`、`cumulative_return`、`max_drawdown` 或 `sharpe_like_score` 的正式排行榜口徑。

Pending 狀態仍需另外保留完成度資訊：

- `pending_count`
- `pending_ratio`

這兩個欄位應與 `max_drawdown` 一起檢視。若 pending 比例過高，即使已完成交易的最大回撤很低，也不代表策略風險已被充分觀察。

## 5. 限制與近似

初期 `max_drawdown` 是交易序列層級的簡化風控指標，不代表真實投組回撤。主要限制如下：

- 初期不處理重疊持倉。
- 初期不處理資金配置。
- 初期不處理交易成本與滑價。
- 初期不處理單一股票、產業或市場暴露集中度。
- 初期不代表真實 portfolio-level drawdown。

因此，初期最大回撤只能用來比較同一資料口徑下策略的相對風險，不應解讀為正式資金投入後的最大可能損失。後續若要提高精準度，應升級為 portfolio-level drawdown，納入部位大小、持倉重疊、交易成本、滑價與資金使用率。

## 6. 與 strategy_metrics_definition.md 的關係

`strategy_metrics_definition.md` 已將 `max_drawdown` 定義為 04 階段核心指標之一。本文件進一步補充最大回撤的初期計算口徑、資料需求與限制。

`max_drawdown` 是核心風控指標，應與以下指標一起解讀：

- `avg_return`
- `cumulative_return`
- `sharpe_like_score`
- `trade_count`
- `pending_ratio`
- `stability_score`

`max_drawdown` 不可單獨作為唯一排名依據。低回撤策略若平均報酬不足、樣本數太少或 pending 比例過高，仍不應被視為高品質策略；高報酬策略若最大回撤過大，也不應直接進入正式啟用候選。

## 7. 後續實作建議

後續落實時建議分階段進行，避免一次改動過大：

1. 先建立純函式，輸入已排序或可排序的交易報酬資料，輸出 equity curve、逐筆 drawdown 與 `max_drawdown`。
2. 在純函式中明確處理空資料、單筆交易、缺漏報酬、無效排序欄位與負值報酬。
3. 再接到 `strategy_ranking_engine.py`，依 `strategy_name`、`holding_days`、`strategy_version` 分組計算。
4. 再輸出到 strategy ranking，並在欄位說明中固定負值或絕對幅度口徑。
5. 最後再考慮 per-stock、per-strategy、per-period drawdown，協助檢查績效是否集中在特定股票、策略版本或市場期間。

實作時應維持 research-only 原則。任何門檻設定、正式啟用條件或 LINE 推播策略變更，都應另行設計與審核，不應由本指標接入自動觸發。
