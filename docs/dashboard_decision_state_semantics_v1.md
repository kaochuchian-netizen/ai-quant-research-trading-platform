# AI-DEV-150 Dashboard Decision State Semantics V1

AI-DEV-150 turns the four-window Dashboard from a wiring/status page into a PM-readable decision-state page. It does not add new data, build prediction logic, or fabricate forecasts.

## Main semantic rules
- Global state must say `部分資料可用；正式預測與檢討資料待接` when prediction/review artifacts are missing.
- 07:00 shows `盤前摘要：可用`, `每日股價預測：資料待接`, and `整體狀態：部分缺資料`.
- 13:05 shows formal intraday runtime data as missing when absent.
- 13:35 remains `收盤快照 / Close Snapshot`; full review is deferred to 15:00.
- 15:00 does not reuse 07:00 local analysis as prediction-review freshness.
- Stock cards say `追蹤名單有效`, not generic `資料正常`.
- Example artifacts are moved to Debug / Artifact inventory and are not official latest reports.
- LINE/Email audit wording states actual delivery content was not verified.

## Non-actions
No secrets, DB writes, scheduler changes, LINE/Email sends, production pipeline, `python3 main.py`, trading/order, rating/action/confidence/weight mutation, formal delivery behavior change, nginx/systemd/firewall change, or local Mac/iPhone/wimac workspace changes.
