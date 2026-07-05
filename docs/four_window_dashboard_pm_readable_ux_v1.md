# Four-Window Dashboard PM-Readable UX V1

AI-DEV-146 rewrites the controlled four-window Dashboard preview from a technical contract page into a PM-readable decision dashboard.

## Why This Exists

AI-DEV-145 successfully published the controlled static route, but the first version surfaced engineering artifacts before business context. It exposed route contracts, runtime keys, UI IDs, boolean safety flags, nested preview iframe content, and placeholder copy. The page was technically correct but not useful for a human decision maker.

## UX Direction

The page now starts with `四時段 AI 決策儀表板`, a clear preview badge, and a Today Decision Summary. The primary content is four readable cards:

- 07:00 盤前預測 / Pre-open Forecast
- 13:05 盤中追蹤 / Intraday Tracking
- 13:35 收盤快照 / Close Snapshot
- 15:00 盤後檢討 / Prediction Review

The 13:35 card is explicitly a close snapshot. It is not a full prediction review and must not use pre-close / 收盤前 as the primary UI concept. Full prediction review remains at 15:00.

## Source Quality Section

The page explains evidence quality in PM language:

- 官方公告 / 財報 / 法說會：高可信，可作核心證據
- 產業供應鏈 / 同業脈絡：中可信，作為背景脈絡
- Google News / yfinance / broker target：輔助資訊，不直接改變評等
- Gemini / AI summary：解釋層，不是原始證據

## Debug Placement

Technical checks are moved to a bottom `技術檢查 / Debug` details section. The main page no longer starts with route contracts, runtime keys, schema language, or wide technical tables.

## Static Preview Only

This remains a controlled static preview. It does not fabricate market predictions and clearly states that formal runtime data is not connected yet.

## Safety

- no LINE / Email / notification
- no scheduler / cron / systemd / timer changes
- no DB writes
- no production pipeline
- no `python3 main.py`
- no secrets touched
- no broker / order / trading
- no production rating/action/confidence/weight mutation
- no formal delivery behavior change
- no nginx/systemd/firewall change
