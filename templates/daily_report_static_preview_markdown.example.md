# Daily Report Static Preview 2026-06-30

- Generated at: `2026-06-30T09:40:00+08:00`
- Manifest ID: `daily_report_static_preview_manifest_20260630`
- Mode: `fixture_dry_run`
- Preview only: `true`
- Advisory only: `true`

> Static preview package only. No delivery action, external model call, market data call, persistent store write, portfolio action, or schedule/service change was performed.

## Renderer Source
- Source path: `templates/daily_report_renderer_result.example.json`
- Source run ID: `daily-report-renderer-fixture-20260630`
- Source decision: `daily_report_renderer_completed_with_warnings`
- Source warning count: `4`

## Section Index
- 1. `forecast_review` Forecast Review (body_01, high)
- 2. `daily_report_intelligence` Company And Industry Intelligence (body_02, medium)

## Validation Warnings
- forecast review source reports insufficient data
- human review required for one or more intelligence sources
- one or more source credibility records require human review
- source renderer completed with warnings
- source research pack completed with warnings

## Renderer Markdown Preview

# Daily Report 2026-06-30

- Report date: `2026-06-30`
- Mode: `fixture_dry_run`
- Advisory only: `true`
- Requires human review: `true`

> Repo-only, fixture-only daily report renderer output. This is not a delivery payload and must be reviewed by a human before any future 07:00 report use.

## Human Review Warnings
- forecast review source reports insufficient data
- human review required for one or more intelligence sources
- one or more source credibility records require human review
- source research pack completed with warnings

## Forecast Review

> 資料不足，不應過度解讀命中率。

- **Executive Summary**: Current quality status is `insufficient_data` with 3 evaluated records. 資料不足，不應過度解讀命中率。 Human review is required before any forecast tuning.
- **Forecast Quality Summary**: Overall grade: `Insufficient Data`; interval hit rate: `100.0%`.
- **Horizon Review Summary**: Horizon cards summarize evaluated records, pending records, hit rates, and error rates.
- **Confidence Calibration Summary**: Confidence buckets below sample thresholds remain insufficient for calibration conclusions.
- **Error Pattern Summary**: Detected 2 top error pattern groups.
- **Daily Improvement Recommendations**: Recommendations are advisory only, require human review, and are not applied automatically.
- **Risk And Limitations**: 樣本數不足時不得過度解讀。 Fixture-only result 不代表 production performance。 Review recommendations 不會自動修改 forecast weights。 本輸出不構成投資建議。
- **Next Steps**: Use this export as input for a future Daily Report Forecast Review Section or Dashboard MVP task.

_Fixture-only, advisory-only. Human review is required before any forecast tuning or report delivery._

## Company And Industry Intelligence

> Fixture-only intelligence section. Advisory only; human review is required before daily report insertion.

### Company Intelligence
- Monthly revenue fixture indicates stable demand momentum relative to the prior quarter.
- Industry primary data fixture supports continued demand for advanced semiconductor capacity.
- Consensus metadata is retained only as labeled sentiment context and is not a core input.

### Industry And Peer Context
- Fixture demand monitor indicates stable advanced-node wafer demand for the current quarter.
- Fixture market and peer context suggests pricing remains differentiated by process node and packaging demand.
- Target company fixture shows stronger exposure to advanced packaging demand than the peer set.
- Market data fixture is retained as quantitative context and does not override primary industry evidence.

### Source Credibility
- Combined source count: `8`
- Average credibility score: `0.792`
- Human-review source count: `1`

### Risk And Limitations
- Fixture summaries are static examples and are not connected to live report generation.
- This section is advisory only and must not be treated as investment advice.
- Lower-credibility and human-review sources remain labeled and must be reviewed before use.
- No portfolio, delivery, schedule, model, or market data action is authorized by this output.

_No delivery action, portfolio action, schedule change, or persistent store write was performed._

## Risk And Limitations
- This renderer output is assembled from static repo fixtures only.
- The source research pack is advisory-only and requires human review.
- Source refs, credibility metadata, and limitation notes are preserved from the source research pack.
- Forecast review content may be based on insufficient sample size and must not be over-interpreted.
- This output is not investment advice and does not authorize trading, portfolio, delivery, schedule, service, model, or data actions.

_No external model call, market data call, delivery action, persistent store write, portfolio action, schedule/service change, or production report send was performed._
