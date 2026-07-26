# US Three-Window Source-Plan Continuity V1

## Ownership and root causes

The admitted `us_pre_market_2000` immutable snapshot is the only owner of a US trade plan. Before AI-DEV-192, the 23:00 producer rebuilt daily tactical levels, mixed them with a runtime prediction snapshot, and recomputed channel summaries. That allowed watch/no-trade symbols to regain formal levels and caused Top, invalidated, Dashboard, and LINE contradictions. Relative strength was already stored as a percentage-point difference but was rendered as a ratio percentage. The 06:30 source-plan resolver was mostly correct, but 23:00 evidence identity and SEC/news separation were incomplete.

## Canonical lifecycle

`20:00 admitted source plan → 23:00 observed evidence → 06:30 review`

The source binding stores effective date, snapshot ID, revision, source hash, admitted time, plan status, direction, eligibility, and formal geometry. The 23:00 window may update quote, gap, volume, trigger, proximity, and tactical action only. The 06:30 window reviews the same plan and may attach an admitted 23:00 evidence identity; it must never treat that evidence as a new plan.

Plan statuses are `active`, `watch`, and `no_trade`. Only `active` owns Entry/Stop/Target. Watch and no-trade cards use observation-only presentation and `not_applicable` trigger semantics.

## Direction-aware rules

For long plans, `stop < entry.low` and `target.low > entry.high`. For short plans, `stop > entry.high` and `target.high < entry.low`. Stop and target proximity use direction-specific formulas. Invalid geometry fails validation instead of being rendered.

Top opportunities and still-actionable lists require the 20:00 canonical flag and a non-invalidated 23:00 state. `top_opportunity && invalidated`, `actionable && invalidated`, and watch/no-trade promotion are invalid.

## Relative strength and presentation

Relative strength is a percentage-point difference:

`symbol premarket change % - benchmark premarket change %`

For example, -1.03% versus QQQ -1.65% is shown as `+0.62 個百分點`. Price ranges use `low–high`; Python dict representation is forbidden. Public enums are localized. An active setup shown against a conflicting market regime includes direction, setup type, relative strength, rationale, and invalidation condition.

## SEC and news

SEC filing evidence and timely news are separate structures. Missing news is shown as unavailable and must never copy a filing summary. The same canonical event-risk and evidence structures flow to Dashboard, Archive, Email/LINE previews, and Operations.

## Channel parity

Archive, Dashboard, Email preview, LINE preview, and Operations consume the admitted snapshot summary. Identity parity covers effective date, snapshot ID, revision, source hash, admitted time, symbol groups, and counts. Formatters do not classify symbols independently.

## Controlled verification and rollback

Controlled verification uses deterministic quotes and temporary targets with delivery disabled. It exercises active long, valid short, invalid geometry, watch/no-trade non-promotion, invalidation exclusivity, relative-strength units, channel summaries, and SEC/news separation. It does not execute the production pipeline, send notifications, trade, change the scheduler, or rewrite snapshots.

Rollback is the ordinary Git revert of the implementation merge plus a static presentation rebuild from resolver-selected admitted snapshots. Immutable history and runtime evidence are never modified.

## Natural verification

Keep AI-DEV-192 as `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until the next natural 20:00, 23:00, and 06:30 sequence proves exact plan binding, no regeneration or promotion, direction-aware geometry, prediction/trade separation, five-channel parity, and SEC/news separation.

## Known limitations

When no admitted same-date 20:00 source snapshot exists, 23:00 safely reports an unavailable plan and does not infer levels. Minute data may improve stop/target sequencing, but absence of minute evidence must remain explicit and cannot be replaced by daily-bar ordering assumptions.
