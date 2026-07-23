# AI-DEV-190 — TW 07:00 Summary & US 06:30 Outcome V1

## Root causes

- TW 07:00 的 Dashboard、Email 與 LINE 使用不同呈現邏輯；LINE 固定寫成 `Top 3`，並把 `no_trade` 當成 `Avoid`。原 aggregate 沒有 watch-only 與逐來源 coverage。
- TW news direction 沒有 canonical producer；部分卡將策略 action 或空值誤當新聞方向。公開 renderer 對 watch/no-trade 仍呈現完整交易計畫。
- US 06:30 只讀 per-symbol prediction snapshot 與日內 high/low，沒有綁定同交易日 admitted 20:00 immutable snapshot 的 trade plan，因此程式固定輸出 pending，MFE/MAE 也沒有 evaluator。

## TW canonical decision and coverage

主要互斥分類為 `top_opportunity`、`watch_only`、`no_trade`、`unavailable`；`entry_ready` 與 `avoid_chase` 是受約束的衍生維度。所有 count、symbol list、Email、LINE 與 Dashboard 都使用 `pre_open_summary`。

Coverage 逐批計算 technical、ADR、overnight、chip、news、gap、event risk 的 available/total。Market bias 同時保存 confidence 與 reason codes；低 coverage 不得描述成完整市場判斷。

News direction 僅允許 bullish、neutral、bearish、unavailable。交易 action 與新聞方向分離。Watch-only 只呈現觀察區與等待條件；no-trade 不呈現正式 Entry/Stop/Target。

## US immutable source-plan binding

06:30 只掃描：

`artifacts/archive/window_snapshots/us/us_pre_market_2000/<effective_date>/revision-*.json`

選擇 admitted 的最高 revision，再以 admitted/revision time 決定；禁止使用 global latest 或 filesystem mtime。Review 保留 source window、effective date、snapshot ID、revision、source hash 與 symbol plan。

## Trade outcome and MFE/MAE

公開 review outcome 為 win、loss、not_triggered、no_trade、pending_evidence；並映射至既有 hit、fail、not_triggered、no_trade、pending canonical enum，維持既有 aggregate contract。

優先使用 bounded 5-minute bars判定 entry/target/stop 先後。若只有 daily OHLC：未觸及 entry 可判 not_triggered；只跨單一 target/stop 可判定；同時跨兩側必須 pending_evidence。MFE/MAE 以 entry reference 與 entry 後 extrema 計算；未觸發或 no-trade 為不適用。

## SEC, News and event risk

06:30 直接沿用 20:00 source card 的 canonical event risk、SEC evidence、news evidence；不得以 SEC metadata 補成 news。

## Controlled verification and publish

Validators 僅使用 deterministic temporary fixtures與 read-only immutable artifacts；不執行 production pipeline、不寄 Email/LINE、不交易、不改 scheduler。Controlled static publish 僅可在 merge、CI、post-merge、worktree governance、安全 gates 通過後，從 resolver-selected admitted snapshots 重建 presentation；不得建立或重寫 snapshot。

## Rollback

Publish 前建立 `/var/www/stock-ai-dashboard/.ai_dev_170_rollback/<timestamp>`。若 public identity、route 或 marker 驗證失敗，依既有 controlled publisher rollback contract 還原 presentation；immutable archive 不動。

## Natural verification

下一次自然 TW 07:00 驗證 canonical groups、coverage、news enum、compact rendering 與 channel identity。下一次自然 US 06:30 驗證 source-plan identity、outcome、MFE/MAE、SEC/news/event-risk parity。完成前狀態為 `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`。

## Known limitations

Yahoo minute bars若不可用，只有 daily OHLC 且 target/stop 同時跨越時會保守保留 pending_evidence；不猜測先後。舊 immutable 20:00 snapshot 若缺 AI-DEV-189 fields，presentation 保留安全 unavailable semantics，不回填歷史。
