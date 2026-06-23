# Source Inventory Registry

## Purpose

This document defines the research-only source inventory registry for the
current stock-ai workspace. It is a read-only governance artifact that lists
connected data sources, notification outputs, and candidate sources that are
not yet connected.

The registry is intended to support source cost governance, credentials
separation, and read-only auditing. It does not authorize production pipeline
execution, database writes, notifications, trading, or order placement.

## Registry Scope

The inventory covers three source groups:

1. Connected sources
2. Notification outputs
3. Candidate sources

The connected group is limited to sources that are already referenced by local
code. The notification group is separated so that outbound delivery channels
cannot be confused with data sources. Candidate sources remain unconnected and
should stay that way until a separate approved task explicitly changes the
integration boundary.

## Governance Rules

- Dry-run first.
- Read-only audit by default.
- No DB mutation by default.
- No notifications by default.
- No `.env`, secret, token, or credential values in the registry.
- Source ids must be unique across all groups.
- Notification outputs must remain separate from data sources.
- Candidate sources must not be marked connected.
- Gemini, FinMind, and MOPS must be treated as distinct governance cases.
- Cost tier should be recorded for every source entry.

## Connected Sources

The current connected sources are:

- `google_sheet`
- `shioaji_sinopac`
- `twse_openapi`
- `google_news_rss`
- `gemini_google_generative_ai`
- `yfinance_yahoo`
- `sqlite_historical_csv`

These sources are currently referenced in local code and docs as active
read-only or pipeline inputs. Some of them may still call external services, but
that is a source-level integration concern and not a permission boundary for
production use.

## Notification Outputs

The current notification outputs are:

- `line_push`
- `smtp_email`

These are outbound delivery channels. They must never be mixed into the data
source inventory and should always be treated as notification surfaces, not as
input sources.

## Candidate Sources

The current candidate sources are:

- `finmind`
- `mops_public_information_observatory`
- `eyuanta`

These sources are recorded for future research planning only. They are not
connected in the current codebase and should remain disconnected unless a
future task explicitly approves the integration.

## Cost Governance

Each source entry includes a cost tier so that future integration decisions can
compare free, low-cost, variable-cost, and unknown-cost surfaces before making a
change.

Suggested review questions:

- Is the source free or quota-limited?
- Does the source require a paid key or subscription?
- Can the source be cached locally?
- Does the source belong in a notification path or a data path?
- Can the source stay candidate-only until a future task proves value?

## Read-Only Audit

Run the audit helper with:

```bash
python3 scripts/orchestrator/audit_source_inventory_registry.py --pretty
```

The audit is read-only. It validates required fields, enumerations, unique
source ids, credentials consistency, notification separation, Gemini category,
and that FinMind and MOPS remain unconnected.

## Runtime Loader

The registry can also be loaded through the reusable helper:

```bash
python3 scripts/orchestrator/source_inventory_registry_loader.py --pretty
```

That helper returns a read-only summary contract for scripts that need to reuse
the registry without re-implementing JSON parsing or source-group counting.
The loader does not call external services, read secrets, write files, touch
databases, send notifications, or run production workflows.

## Validation Flow

The AI development validation flow is expected to include both the registry
loader and the registry audit so source governance stays part of branch
validation instead of being checked only as a standalone script.

## Relationship to Other Governance Docs

- `docs/schema_examples_validation.md`
- `docs/source_credibility_taxonomy.md`
- `docs/actual_outcome_backfill_plan.md`
- `docs/pipeline_overview.md`

This registry is a review aid only. It does not imply permission to run
production pipelines, modify credentials, send notifications, or trade.
