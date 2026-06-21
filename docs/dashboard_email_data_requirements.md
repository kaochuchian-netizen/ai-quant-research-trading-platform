# Dashboard and Email Data Requirements

This document defines data requirements for future dashboard and email report
outputs. It does not implement UI, email delivery, LINE delivery, production
pipelines, trading, order placement, cron, systemd, or timer changes.

## Shared Output Rules

Dashboard and email outputs must be derived from traceable records such as:

- Signals from `docs/investment_data_schemas.md`.
- Forecasts and prediction reviews.
- Company intelligence.
- Industry intelligence.
- Report metadata.
- Source metadata and credibility tiers from
  `docs/source_credibility_taxonomy.md`.

Outputs must preserve:

- `schema_version`
- `as_of_date`
- `created_at`
- `source`
- `source_tier`
- `confidence`
- `data_quality`
- `missing_data_policy`
- `notes`

Analyst target prices, broker calls, and analyst ratings may appear only as
low-priority market sentiment or consensus metadata. They must not determine
headline ranking, action labels, or core recommendation text.

## Dashboard Data Requirement

The future dashboard should support repeated scanning, comparison, and review.
It should separate research status from any production action.

### Required Dashboard Datasets

| Dataset | Purpose | Required keys |
| --- | --- | --- |
| `signal_summary` | Current signal and ranking state. | `signal_id`, `stock_id`, `as_of_date`, `signal_session`, `schema_version`. |
| `forecast_summary` | Open forecasts and review due dates. | `forecast_id`, `entity_id`, `forecast_horizon`, `review_due_date`. |
| `prediction_review_summary` | Forecast/signal outcome tracking. | `review_id`, `forecast_id` or `signal_id`, `outcome_status`. |
| `company_intelligence_feed` | Company events and factual updates. | `company_intel_id`, `company_id`, `event_type`, `event_date`. |
| `industry_intelligence_feed` | Industry and peer context. | `industry_intel_id`, `industry_id`, `topic`, `as_of_date`. |
| `source_quality_summary` | Source tier and data-quality visibility. | `record_id`, `source_tier`, `confidence`, `data_quality`. |
| `report_registry` | Generated report metadata and lineage. | `report_id`, `report_type`, `pipeline_run_id`, `publication_status`. |

### Dashboard Field Requirements

| Field | Requirement | Notes |
| --- | --- | --- |
| `display_status` | required | Example: `research_only`, `watchlist`, `needs_review`, `stale`, `blocked`. |
| `ranking_status` | required | Must be rule-based and versioned; do not use free text. |
| `source_tier_badge` | required | Show effective source tier. |
| `confidence_label` | required | Derived from numeric confidence. |
| `data_quality_flags` | required | Missing, stale, conflicting, or review-required flags. |
| `last_updated_at` | required | Timestamp for UI freshness. |
| `linked_record_ids` | required | Traceback to source records. |
| `analyst_metadata_available` | optional | Display as context only, never as core rank reason. |
| `human_review_required` | required | True when source or data-quality policy requires it. |

### Dashboard Filtering Requirements

The dashboard should support filtering by:

- `as_of_date`
- `signal_session`
- `pipeline_type`
- `source_tier`
- `confidence_label`
- `data_quality_flags`
- `industry_id`
- `stock_id`
- `display_status`
- `ranking_status`
- `human_review_required`

### Dashboard Safety Requirements

- Do not expose order buttons or trading actions in this schema phase.
- Do not treat dashboard visibility as permission to send notifications.
- Do not hide missing-data flags from the operator.
- Do not rank records with `missing_data_policy = exclude_from_ranking`.
- Do not rank records where `data_quality.requires_human_review = true` unless
  a later reviewed policy explicitly allows it.
- Show analyst target prices only in a clearly labeled context panel.

## Email Report Data Requirement

Email reports should be concise, source-aware, and safe by default. This
document only defines required data; it does not authorize sending email.

### Required Email Report Sections

| Section | Purpose | Required data |
| --- | --- | --- |
| `report_header` | Identify report and freshness. | `report_id`, `report_type`, `as_of_date`, `created_at`, `schema_version`. |
| `top_research_changes` | Highlight material changes. | Linked signals, company intelligence, and industry intelligence. |
| `watchlist_summary` | Show research candidates or risks. | `stock_id`, `display_status`, `confidence`, `source_tier`, `data_quality_flags`. |
| `forecast_updates` | Track open forecasts. | Forecast status, review due date, changed assumptions. |
| `prediction_review_updates` | Show completed reviews. | Outcome status, error metrics, attribution. |
| `source_quality_summary` | Expose evidence quality. | Source tier counts, stale/missing/conflicting counts. |
| `risk_and_caveats` | Avoid overstatement. | Missing data policy, human review flags, analyst metadata caveat. |

### Email Report Metadata Fields

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `email_report_id` | text | required | Stable id for draft/report metadata. |
| `schema_version` | integer | required | Email data schema version. |
| `report_id` | text | required | Linked report metadata id. |
| `as_of_date` | text | required | Business date. |
| `created_at` | text | required | Draft creation timestamp. |
| `recipient_scope` | text | optional | Example: `operator_preview`; no addresses or secrets. |
| `source_tier_summary` | object | required | Count by tier. |
| `confidence_summary` | object | required | Count by confidence label. |
| `data_quality_summary` | object | required | Missing/stale/conflicting/review counts. |
| `included_record_ids` | array | required | Traceable input records. |
| `excluded_record_summary` | object | required | Records excluded due to missing data or policy. |
| `analyst_metadata_summary` | object | optional | Context only; must include restriction label. |
| `notification_sent` | boolean | required | Must default to false. |
| `send_allowed` | boolean | required | Must default to false in this schema phase. |
| `notes` | text | optional | Operator caveats. |

### Email Safety Requirements

- Do not include credentials, tokens, API keys, email passwords, or secret paths.
- Do not include direct trading instructions.
- Do not claim that target prices or analyst ratings are core decision inputs.
- Do not send automatically from schema generation.
- Do not reuse orchestrator stage email approval as investment approval.
- Include source tier and data-quality caveats for highlighted records.
- Include `research_only` or equivalent status until a later reviewed policy
  defines production use.

## Report Readiness Rules

A dashboard or email report record is `ready_for_preview` only when:

- Required schema fields are present.
- Source metadata is attached.
- `source_tier` is not empty.
- `confidence` is populated.
- `data_quality` is populated.
- Missing-data policy is explicit.
- Analyst metadata is separated from core score/rank fields.

A record is `blocked_for_output` when:

- Required fields are missing.
- Source is unverified and no human review is recorded.
- Data-quality conflicts are unresolved.
- Missing-data policy is `defer_record`.
- A section would imply trading, order placement, or production approval.

## Suggested Future Validation

Future implementation may add read-only validators that:

- Check required Markdown-defined schema fields in sample JSON.
- Verify allowed `source_tier` values.
- Verify analyst metadata is not referenced by core scoring fields.
- Verify report records include source and data-quality summaries.
- Verify `notification_sent` and `send_allowed` default to false in examples.

Such validators must not send email, LINE, notifications, run production
pipelines, trade, place orders, modify scheduler settings, or read secrets.

