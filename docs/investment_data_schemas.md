# Investment Data Schemas

This document defines research-only data schemas for future investment signals,
forecasts, reports, prediction reviews, company intelligence, and industry
intelligence.

These schemas are design targets only. They do not implement a production
pipeline, database migration, dashboard, notification flow, trading action, or
order execution. Downstream implementation must remain append-only,
version-aware, auditable, and compatible with existing backtest and strategy
research documents.

## Shared Schema Principles

All investment research records should include these common fields whenever
possible:

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `schema_version` | integer | required | Starts at `1`; increment only when field semantics change. |
| `record_id` | text | required | Stable unique id for the record. |
| `entity_id` | text | required when applicable | Stock id, company id, industry id, strategy id, or report id. |
| `entity_type` | text | required | Example: `company`, `stock`, `industry`, `strategy`, `market`. |
| `as_of_date` | text | required | Business date the record describes, using `YYYY-MM-DD`. |
| `created_at` | text | required | ISO 8601 timestamp when this record was created. |
| `updated_at` | text | optional | ISO 8601 timestamp when revised. |
| `source` | object / array | required | Source metadata; see `docs/source_credibility_taxonomy.md`. |
| `source_tier` | text | required | Highest effective source tier used by this record. |
| `confidence` | numeric / text | required | Suggested range `0.0` to `1.0`, plus optional label. |
| `data_quality` | object | required | Completeness, freshness, consistency, and audit notes. |
| `missing_data_policy` | text | required | How unavailable data is represented; do not infer unavailable facts. |
| `notes` | text | optional | Human-readable context and caveats. |

Missing values must mean unavailable, not assumed. Do not backfill subjective
values without a traceable source and explicit review policy.

## 1. Signal Schema

Signals are research records describing an investment setup or ranking state.
They are not orders, order recommendations, or production trading instructions.

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `signal_id` | text | required | Stable unique signal id. |
| `schema_version` | integer | required | Signal schema version. |
| `stock_id` | text | required | Taiwan stock id or equivalent security id. |
| `stock_name` | text | optional | Display name. |
| `signal_session` | text | required | Example: `pre_open`, `intraday`, `pre_close`, `post_close`. |
| `pipeline_type` | text | optional | Pipeline that produced the signal. |
| `pipeline_run_id` | text | optional | Batch/run id for traceability. |
| `as_of_date` | text | required | Date the signal applies to. |
| `signal_time` | text | required | ISO 8601 Asia/Taipei timestamp when usable. |
| `created_at` | text | required | Record creation time. |
| `strategy_name` | text | optional | Strategy or rule set name. |
| `strategy_version` | text | optional | Version of strategy logic. |
| `signal_type` | text | required | Example: `score_rank`, `event_watch`, `risk_alert`, `forecast_input`. |
| `direction` | text | optional | `positive`, `negative`, `neutral`, or `mixed`; not an order side. |
| `rating` | text | optional | Internal research rating, if any. |
| `action_label` | text | optional | Internal label only; must not imply order execution. |
| `total_score` | numeric | optional | Aggregated research score. |
| `technical_score` | numeric | optional | Technical component. |
| `chip_score` | numeric | optional | Chip / flow component. |
| `news_score` | numeric | optional | News or text component. |
| `fundamental_score` | numeric | optional | Company financial component. |
| `industry_score` | numeric | optional | Industry context component. |
| `source` | array | required | Source references supporting the signal. |
| `source_tier` | text | required | Highest effective tier. |
| `confidence` | numeric | required | Confidence in data and signal construction, not profit certainty. |
| `data_quality` | object | required | Completeness, stale inputs, and conflicting inputs. |
| `missing_data_policy` | text | required | Explicit handling for missing components. |
| `is_backtest_eligible` | boolean | required | Whether the signal can enter research backtests. |
| `is_valid_for_ranking` | boolean | optional | Whether the signal can affect ranking outputs. |
| `risk_flags` | array | optional | Data or business risks. |
| `notes` | text | optional | Additional explanation. |

Signals must preserve source traceability. Analyst target prices, broker
ratings, and buy/sell calls may appear only in `source` or low-priority
sentiment metadata and must not be core scoring inputs.

## 2. Forecast Schema

Forecasts describe expected future business, price, ranking, or risk outcomes
for research review. They must be testable and reviewable.

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `forecast_id` | text | required | Stable unique forecast id. |
| `schema_version` | integer | required | Forecast schema version. |
| `entity_id` | text | required | Stock, company, industry, or strategy id. |
| `entity_type` | text | required | `company`, `stock`, `industry`, or `strategy`. |
| `as_of_date` | text | required | Date of forecast basis. |
| `created_at` | text | required | Creation timestamp. |
| `forecast_horizon` | text | required | Example: `5d`, `20d`, `quarter`, `fy`. |
| `forecast_target` | text | required | What is being forecast. |
| `forecast_value` | object | required | Numeric, categorical, or interval value. |
| `forecast_direction` | text | optional | `up`, `down`, `flat`, `volatile`, `mixed`. |
| `base_case` | object | optional | Central scenario. |
| `bull_case` | object | optional | Upside scenario. |
| `bear_case` | object | optional | Downside scenario. |
| `assumptions` | array | required | Traceable assumptions. |
| `source` | array | required | Primary supporting sources. |
| `source_tier` | text | required | Highest effective tier. |
| `confidence` | numeric | required | Confidence in forecast basis, not guarantee of outcome. |
| `data_quality` | object | required | Freshness, completeness, and conflict notes. |
| `missing_data_policy` | text | required | How missing inputs affect confidence. |
| `invalidated_by` | array | optional | Events that would invalidate forecast. |
| `review_due_date` | text | required | Date when forecast must be reviewed. |
| `linked_signal_ids` | array | optional | Related signals. |
| `notes` | text | optional | Research caveats. |

Forecasts should prioritize company disclosures, financial statements, official
guidance, industry supply/demand changes, and peer fundamentals over market
commentary.

## 3. Report Metadata Schema

Report metadata tracks generated research artifacts and their input lineage.

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `report_id` | text | required | Stable report id. |
| `schema_version` | integer | required | Report metadata schema version. |
| `report_type` | text | required | Example: `pre_open`, `company_brief`, `industry_brief`, `forecast_review`. |
| `as_of_date` | text | required | Date the report describes. |
| `created_at` | text | required | Report creation timestamp. |
| `pipeline_type` | text | optional | Pipeline context, if produced by a pipeline. |
| `pipeline_run_id` | text | optional | Run id for traceability. |
| `entity_scope` | array | required | Companies, stocks, industries, or strategies included. |
| `input_record_ids` | array | required | Signals, intelligence, forecasts, and review ids. |
| `source_summary` | object | required | Counts by source tier and stale/missing inputs. |
| `source_tier` | text | required | Highest effective tier present. |
| `confidence` | numeric | required | Overall report confidence. |
| `data_quality` | object | required | Completeness, freshness, and blocked sections. |
| `missing_data_policy` | text | required | Report-level missing data handling. |
| `audience` | text | optional | Example: `research`, `dashboard`, `email_summary`. |
| `publication_status` | text | required | `draft`, `preview`, `published`, or `archived`. |
| `notification_sent` | boolean | required | Must be false unless an explicit future sender updates it. |
| `notes` | text | optional | Human review notes. |

This schema defines metadata only. It does not authorize email, LINE, dashboard
publishing, or production execution.

## 4. Prediction Review Schema

Prediction reviews compare forecasts or signals with later outcomes.

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `review_id` | text | required | Stable review id. |
| `schema_version` | integer | required | Review schema version. |
| `forecast_id` | text | optional | Forecast being reviewed. |
| `signal_id` | text | optional | Signal being reviewed. |
| `entity_id` | text | required | Reviewed entity. |
| `as_of_date` | text | required | Original forecast/signal date. |
| `review_date` | text | required | Review date. |
| `created_at` | text | required | Review record creation timestamp. |
| `review_horizon` | text | required | Horizon being evaluated. |
| `expected_outcome` | object | required | Original expected value or state. |
| `actual_outcome` | object | required | Observed result. |
| `outcome_status` | text | required | `hit`, `miss`, `partial`, `inconclusive`, or `not_reviewable`. |
| `error_metrics` | object | optional | Absolute error, percentage error, rank error, or return delta. |
| `attribution` | array | optional | Drivers explaining hit or miss. |
| `source` | array | required | Outcome and attribution sources. |
| `source_tier` | text | required | Highest effective source tier. |
| `confidence` | numeric | required | Confidence in review conclusion. |
| `data_quality` | object | required | Missing outcome data, stale sources, or conflicts. |
| `missing_data_policy` | text | required | Whether review is delayed or marked inconclusive. |
| `lessons_learned` | array | optional | Improvements for future schema, score, or strategy rules. |
| `notes` | text | optional | Context. |

Reviews must preserve original forecast assumptions. Do not rewrite the original
forecast to match observed outcomes.

## 5. Company Intelligence Schema

Company intelligence records source-grounded company facts and qualitative
events.

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `company_intel_id` | text | required | Stable company intelligence id. |
| `schema_version` | integer | required | Company intelligence schema version. |
| `company_id` | text | required | Company identifier. |
| `stock_id` | text | optional | Listed security id. |
| `company_name` | text | optional | Display name. |
| `as_of_date` | text | required | Date the information applies to. |
| `created_at` | text | required | Record creation timestamp. |
| `event_type` | text | required | Example: `material_event`, `earnings`, `monthly_revenue`, `guidance`, `press_release`, `management_interview`. |
| `event_date` | text | required | Event or disclosure date. |
| `summary` | text | required | Concise factual summary. |
| `metrics` | object | optional | Revenue, margin, EPS, backlog, shipment, capex, or guidance values. |
| `guidance` | object | optional | Official company guidance only. |
| `management_commentary` | object | optional | Official or attributed management comments. |
| `source` | array | required | Source references. |
| `source_tier` | text | required | Highest effective tier. |
| `confidence` | numeric | required | Confidence in extracted facts. |
| `data_quality` | object | required | Completeness and freshness. |
| `missing_data_policy` | text | required | How unavailable metrics are represented. |
| `market_reaction` | object | optional | Price/volume reaction, if separately sourced. |
| `risk_flags` | array | optional | Accounting, guidance, demand, supply, regulation, or governance risks. |
| `notes` | text | optional | Caveats. |

Preferred company sources are official material information, financial
statements, earnings calls, annual reports, monthly revenue, company press
releases, management interviews, and official guidance.

## 6. Industry Intelligence Schema

Industry intelligence records supply chain, peer, demand, inventory, pricing,
and policy context.

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `industry_intel_id` | text | required | Stable industry intelligence id. |
| `schema_version` | integer | required | Industry intelligence schema version. |
| `industry_id` | text | required | Internal industry or supply-chain id. |
| `industry_name` | text | optional | Display name. |
| `as_of_date` | text | required | Date the intelligence applies to. |
| `created_at` | text | required | Record creation timestamp. |
| `topic` | text | required | Example: `supply`, `demand`, `inventory`, `pricing`, `capacity`, `policy`, `peer_earnings`. |
| `summary` | text | required | Factual summary. |
| `metrics` | object | optional | Supply, demand, price, inventory, capacity, utilization, or shipment metrics. |
| `affected_company_ids` | array | optional | Companies likely affected. |
| `peer_references` | array | optional | Peer earnings or disclosures. |
| `upstream_downstream_context` | object | optional | Supply-chain linkage. |
| `source` | array | required | Source references. |
| `source_tier` | text | required | Highest effective tier. |
| `confidence` | numeric | required | Confidence in industry conclusion. |
| `data_quality` | object | required | Completeness and conflicting sources. |
| `missing_data_policy` | text | required | Handling for unavailable industry metrics. |
| `risk_flags` | array | optional | Demand, inventory, pricing, regulation, technology, or geopolitical risks. |
| `notes` | text | optional | Caveats. |

Industry intelligence should use upstream/downstream trends, peer financial
reports, and industry supply/demand changes before analyst commentary.

## Data Quality Object

Use a consistent `data_quality` object across schemas:

| Field | Type | Notes |
| --- | --- | --- |
| `freshness` | text | Example: `current`, `stale`, `unknown`. |
| `completeness` | numeric | Suggested range `0.0` to `1.0`. |
| `source_count` | integer | Number of supporting sources. |
| `conflicting_sources` | boolean | Whether source conflict exists. |
| `conflict_notes` | text | Required when conflicts exist. |
| `requires_human_review` | boolean | True for low confidence, high impact, or conflicting data. |
| `legacy_record` | boolean | True when converted from older schema. |

## Missing Data Policy Values

Recommended values:

- `explicit_null`: field is unavailable and intentionally null.
- `defer_record`: record should not be used until required inputs arrive.
- `exclude_from_ranking`: record can be stored but not used for ranking.
- `review_required`: human review is required before use.
- `legacy_fallback`: legacy fields may be used with lower confidence.

