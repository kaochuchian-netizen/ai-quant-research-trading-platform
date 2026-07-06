# Four-Batch Delivery Content Strategy V2 Alignment Runbook

## Operator flow
1. Run the four-batch delivery audit in read-only mode.
2. Validate the four-batch content contract.
3. Build the production runtime export and Dashboard runtime data.
4. Build and publish the controlled static Dashboard preview.
5. Validate the public Dashboard URL.

## Missing data handling
Do not hide missing prediction fields. Use `資料待接：尚未找到正式 prediction runtime artifact，不產生假預測。` for unavailable high/low/trend/confidence/rationale data.

## Channel policy
LINE is short. Email is complete. Dashboard shows full state, freshness, missing data, and a LINE / Email / Dashboard delivery audit summary.

## 13:35 wording
User-facing wording must be `收盤快照 / Close Snapshot`. The runtime key `pre_close_1335` may appear only in debug or compatibility fields.

## Prohibited actions
Do not resend LINE/Email. Do not change scheduler. Do not run production pipeline or `python3 main.py`. Do not write DB. Do not use secrets. Do not trade/order. Do not mutate rating/action/confidence/weight.
