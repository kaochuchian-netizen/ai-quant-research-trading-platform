# TW 15:00 Outcome Delivery Contract V1

## Purpose

AI-DEV-181C prevents presentation contract labels such as `已觸發 setup：N` from becoming production LINE content. The seven window contracts still describe channel scope, but delivery renderers must output only values projected from the current window artifact or an explicit pending state.

## TW 15:00 outcome aggregation

The scheduler-equivalent delivery entrypoint reads the current TW Daily Tactical artifact and classifies explicit `review_snapshot` values through Decision Intelligence V4. The delivery contract exposes five mutually exclusive counts: `win` as 命中, `not_triggered` as 未觸發, `loss` as 失敗, `no_trade` as 無交易, and any unclassified or ambiguous state as 待確認. Missing values are never converted to success or failure.

LINE and Email call the same `delivery_summary_lines` projection. The resulting lines include all five counts. Seven-day status reads only numeric `seven_day_hit_rate` values from the formal review artifact. When there are no numeric samples it says `待累積` and `命中率待確認`; it does not invent a zero hit rate.

## Canonical link

TW 15:00 delivery owns the existing latest archive route:

`/stock-ai-dashboard/dashboard/archive/tw/post_close_1500/latest/index.html`

The unbuilt `/dashboard/tw/15-00/latest/index.html` path is not emitted. This task does not alter production Landing ownership, staging, or publish isolation.

## Other windows

TW 07:00, 13:05, 13:35 and US 20:00, 23:00, 06:30 use actual Decision Intelligence counts. `line_summary_scope` remains contract metadata and is never appended to LINE output. A missing artifact produces an explicit data-pending sentence rather than an `N` placeholder.

## Controlled no-send verification

Run:

`python scripts/orchestrator/validate_tw_post_close_outcome_delivery_v1.py --pretty`

The validator invokes all seven scheduler delivery scripts in their default/dry-run no-send mode, checks LINE and Email previews, confirms the TW 15:00 canonical URL and actual counts, rejects scope/N placeholders, and compares formal-runtime hashes before and after. Fixtures and outputs live only in a temporary directory and are removed automatically. It does not run a production pipeline or send notifications.

## Rollback

Revert the AI-DEV-181C implementation commit and run the normal controlled static publisher. Do not delete runtime or archive artifacts. Rollback must not copy legacy/debug content into the production Landing root and must not modify scheduler configuration.

## Safety and limitations

This contract changes presentation only. It does not alter scoring, Entry/Stop/Target semantics, scheduler cadence, archive selection, manual revision policy, or Landing route ownership. Existing daily tactical review data can contain ambiguous `breakeven` records; those remain 待確認 until a formal outcome classification is available. No LINE, Email, production-approved delivery, trading, `main.py`, or secrets are used by validation.
