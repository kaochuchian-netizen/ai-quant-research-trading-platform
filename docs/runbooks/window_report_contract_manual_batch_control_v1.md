# AI-DEV-178 Window Report Contract & Manual Batch Control V1

## Background
AI-DEV-178 separates TW/US scheduled reports by decision window. The goal is to stop replaying the same stock-card report across every batch and to make Landing the single manual batch control center.

## Window Contracts
Source of truth: `app/reports/window_report_contract.py`.

TW windows:
- `pre_open_0700`: 07:00 盤前決策, pre-open opportunities, risk, entry/stop/target.
- `intraday_1305`: 13:05 盤中變化, setup trigger and mid-session risk changes.
- `pre_close_1335`: 13:35 收盤快照, late-session risk and no-chase decisions.
- `post_close_1500`: 15:00 盤後檢討, prediction/review/outcome and next-day watchlist.

US windows:
- `us_pre_market_2000`: 20:00 美股盤前, premarket/gap/event risk.
- `us_intraday_2300`: 23:00 美股盤中, gap follow-through and confirmation.
- `us_post_close_review_0630`: 06:30 美股檢討, prediction review and next-day observation.

Alias policy:
- `prediction_review_1500` maps to TW `post_close_1500`.
- `us_review_0630` maps to US `us_post_close_review_0630`.

## Dashboard / Email / LINE Scope
Dashboard, Email, and LINE should read the contract fields:
- `dashboard_sections`
- `email_sections`
- `line_summary_scope`
- `suppressed_sections`
- `dashboard_url`

LINE remains concise. It must not include full Entry/Stop/Target/News/SEC tables.

## Landing Manual Batch Control Center
Landing contains the full control center:
- 台股手動批次: 07:00, 13:05, 13:35, 15:00.
- 美股手動批次: 20:00, 23:00, 06:30.
- One selected market/window at a time.
- Confirmation text is market/window specific.
- PIN input is a 6 digit numeric field.

TW and US dashboards must not contain the full form. They may link back to Landing.

## Manual Backend Flow
Backend entry:
- `scripts/orchestrator/manual_rerun_single_window.py`
- Runtime route bridge: `scripts/orchestrator/manual_rerun_runtime_bridge.py`

Allowed windows are generated from `manual_batch_contracts()` in the contract module.

TW backend commands are dashboard-refresh-only dry-run commands against the approved TW wrapper.
US backend commands are no-send dry-run production-artifact commands against `approved_us_stock_delivery.py`.

The handler records backend command metadata for audit, but validation mode does not execute production delivery.

## PIN Guard
PIN hash is runtime-only:
- env: `STOCK_AI_MANUAL_RERUN_PIN_HASH`
- runtime config file supported by the bridge

Never commit PINs, plaintext PINs, hashes, secrets, or tokens.

## One-batch Lock
TW and US share the same global lock:
- `/tmp/stock_ai_manual_rerun_global.lock`

Window-specific locks still exist, but the global lock prevents TW and US batches from running together.

## No-send Safety
Manual batch result must keep:
- `email_attempted=false`
- `line_attempted=false`
- `trading_or_order_executed=false`
- `scheduler_changed=false`
- `production_pipeline_executed=false`

## Artifact Isolation
TW manual batches target TW artifacts / TW Dashboard.
US manual batches target US artifacts / US Dashboard.
Multi-market publish may publish Landing/TW/US together, but validators must confirm TW-only and US-only pages remain isolated.

## Dashboard URL Contract
TW windows must use `/dashboard/tw/index.html`.
US windows must use `/dashboard/us/index.html`.
Deprecated four-window preview URLs must not appear in delivery/manual batch payloads.

## Validator
Primary validator:
- `scripts/orchestrator/validate_window_report_contract_manual_batch_v1.py --pretty`

It checks markers, non-identical window sections, Landing manual UI, dashboard form isolation, backend mappings, no-send matrix, URL contract, and mobile CSS basics.

## Controlled Publish
After PR merge, run controlled Dashboard publish only:
- `scripts/orchestrator/publish_multi_market_dashboard_v2.py --apply --pretty`

Do not run production-approved delivery, LINE send, Email send, trading, scheduler change, or `python3 main.py`.

## Rollback
Use the backup path returned by controlled publish. Restore Landing/TW/US static HTML from that backup only if instructed.

## Known Limitations
Manual backend execution is guarded and no-send by design. This task establishes executable window mappings and validation, not scheduler activation or production notification delivery.
