# Industry Intelligence + Peer Context V1

## Purpose

Industry Intelligence + Peer Context V1 defines a repo-only, fixture-only,
advisory-only contract for turning industry and peer evidence fixtures into
deterministic industry intelligence and peer context records.

This contract does not enable live scraping, external AI calls, market data
calls, notifications, production database writes, trading, order placement,
cron, systemd, timers, n8n mutation, GitHub Issue mutation, or runtime forecast
weight updates.

## Dependency

This contract depends on AI-DEV-075 and AI-DEV-076 being completed and merged
before implementation. The current repository history shows AI-DEV-075 merged
into `main` by PR #85 and AI-DEV-076 merged into `main` by PR #87 before this
V1 contract was added.

## Contract Identity

The result must include:

- `contract_name = industry_intelligence_peer_context`
- `contract_version = v1`
- `schema_version = industry_intelligence_peer_context_v1`
- `mode = fixture_dry_run`

## Fixture Input

The input fixture is:

```text
templates/industry_intelligence_peer_context_input.example.json
```

Top-level input sections:

- `industry`
- `target_company`
- `sources`
- `industry_topics`
- `peer_companies`
- `peer_context_items`
- `scoring_policy`
- `safety`

`sources` must use the tier names from:

```text
docs/source_credibility_taxonomy.md
```

## Industry Intelligence Contract

The result fixture is:

```text
templates/industry_intelligence_peer_context_result.example.json
```

Top-level result fields:

- `contract_name`
- `contract_version`
- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `industry`
- `target_company`
- `industry_intelligence`
- `peer_context`
- `industry_peer_context_summary`
- `source_credibility_scores`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

`industry_intelligence.items` must preserve:

- `industry_intel_id`
- `industry_id`
- `industry_name`
- `as_of_date`
- `topic`
- `summary`
- `metrics`
- `affected_company_ids`
- `peer_references`
- `upstream_downstream_context`
- `evidence_source_ids`
- `source_tier`
- `confidence`
- `data_quality`
- `missing_data_policy`
- `risk_flags`
- `advisory_only`
- `requires_human_review`

The topic-level `confidence` is the deterministic average of available
evidence source scores for that topic unless the fixture provides a lower
explicit confidence cap.

## Peer Context Contract

`peer_context` compares the target company with fixture peer companies. It is
contextual research metadata only and must not produce buy, sell, long, short,
or order instructions.

`peer_context.items` must preserve:

- `peer_context_id`
- `topic`
- `summary`
- `target_company_id`
- `peer_company_ids`
- `comparison_metrics`
- `relative_position`
- `evidence_source_ids`
- `source_credibility_score`
- `confidence`
- `data_quality`
- `advisory_only`
- `requires_human_review`

`industry_peer_context_summary` is a compact consumer-facing summary. The
standalone example is:

```text
templates/industry_peer_context_summary.example.json
```

It must include:

- `contract_name`
- `contract_version`
- `industry_id`
- `target_company_id`
- `as_of_date`
- `industry_topic_count`
- `peer_context_count`
- `average_confidence`
- `highest_risk_flags`
- `requires_human_review`
- `advisory_only`
- `summary_points`

## Source Credibility Scoring Contract

Source credibility scoring follows AI-DEV-076 and the source credibility
taxonomy. Base scores:

| Source tier | Base score |
| --- | ---: |
| `tier_1_official_filing` | 0.95 |
| `tier_1_company_official` | 0.90 |
| `tier_2_peer_and_industry_primary` | 0.80 |
| `tier_2_management_interview` | 0.70 |
| `tier_3_reputable_media` | 0.65 |
| `tier_3_market_data` | 0.60 |
| `tier_4_consensus_and_analyst` | 0.35 |
| `tier_5_unverified_or_social` | 0.10 |

Deterministic adjustments:

| Condition | Adjustment |
| --- | ---: |
| `recency = current` | +0.03 |
| `recency = stale` | -0.15 |
| `conflicting = true` | -0.20 |
| media or management interview without attribution | -0.10 |
| unverified or social source | -0.05 |

`tier_4_consensus_and_analyst` and `tier_5_unverified_or_social` are not
allowed as core scoring sources and always require human review.

## Safety Requirements

The result must preserve:

- `fixture_only: true`
- `repo_only: true`
- `advisory_only: true`
- `research_only: true`
- `requires_human_review: true`
- `no_trading: true`
- `no_notification: true`
- `no_external_ai_runtime: true`
- `no_external_market_data: true`
- `no_production_db_write: true`
- `no_runtime_weight_change: true`

All side-effect flags must remain false. Fixtures must not contain secrets,
tokens, credentials, private runtime payloads, production config values, live
runtime terms, or trading/order instructions.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/industry_intelligence_peer_context_dry_run.py \
  --input templates/industry_intelligence_peer_context_input.example.json \
  --output /tmp/industry_intelligence_peer_context_result.example.json \
  --summary-output /tmp/industry_peer_context_summary.example.json \
  --pretty
```

The dry-run helper reads fixture input only and writes deterministic JSON. It
does not call external APIs, send notifications, read production data, mutate
production databases, run production pipelines, or execute Issue text.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_industry_intelligence_peer_context_result.py \
  --input templates/industry_intelligence_peer_context_result.example.json \
  --pretty

python3 scripts/orchestrator/validate_industry_intelligence_peer_context_result.py \
  --input /tmp/industry_intelligence_peer_context_result.example.json \
  --pretty
```

Validation is structural and safety-focused. It verifies contract identity,
industry intelligence fields, peer context fields, source score ranges,
deterministic fixture flags, and forbidden secret/runtime/trading text
patterns. It does not approve production use or delivery channel activation.
