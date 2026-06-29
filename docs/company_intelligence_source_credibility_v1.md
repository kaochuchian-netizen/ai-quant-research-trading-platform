# Company Intelligence + Source Credibility V1

## Purpose

Company Intelligence + Source Credibility V1 defines a repo-only,
fixture-only, advisory-only contract for turning company evidence fixtures into
deterministic company intelligence records with source credibility scores.

This contract does not enable live scraping, external AI calls, market data
calls, notifications, production database writes, trading, order placement,
cron, systemd, timers, n8n mutation, GitHub Issue mutation, or runtime forecast
weight updates.

## Dependency

This contract depends on AI-DEV-075 being completed and merged before
implementation. The current repository history shows AI-DEV-075 merged into
`main` before this V1 contract was added.

## Contract Identity

The result must include:

- `contract_name = company_intelligence_source_credibility`
- `contract_version = v1`
- `schema_version = company_intelligence_source_credibility_v1`
- `mode = fixture_dry_run`

## Fixture Input

The input fixture is:

```text
templates/company_intelligence_input.example.json
```

Top-level input sections:

- `company`
- `sources`
- `intelligence_topics`
- `scoring_policy`
- `safety`

`sources` must use the tier names from:

```text
docs/source_credibility_taxonomy.md
```

## Source Credibility Scoring Contract

The per-source scoring example is:

```text
templates/source_credibility_score.example.json
```

Each score object includes:

- `contract_name`
- `contract_version`
- `source_id`
- `source_tier`
- `source_type`
- `publisher`
- `published_at`
- `retrieved_at`
- `base_score`
- `adjustments`
- `credibility_score`
- `core_scoring_allowed`
- `conflicting_source`
- `requires_human_review`
- `usage_policy`
- `notes`

`credibility_score` is deterministic and must be between `0.0` and `1.0`.

Base scores:

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

## Company Intelligence Contract

The result fixture is:

```text
templates/company_intelligence_result.example.json
```

Top-level result fields:

- `contract_name`
- `contract_version`
- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `company`
- `company_intelligence`
- `source_credibility_scores`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

`company_intelligence.items` must preserve:

- `topic_id`
- `topic`
- `summary`
- `evidence_source_ids`
- `source_credibility_score`
- `confidence`
- `data_quality`
- `advisory_only`
- `requires_human_review`

The topic-level `source_credibility_score` is the deterministic average of the
available evidence source scores for that topic.

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
python3 scripts/orchestrator/company_intelligence_source_credibility_dry_run.py \
  --input templates/company_intelligence_input.example.json \
  --output /tmp/company_intelligence_result.example.json \
  --pretty
```

The dry-run helper reads fixture input only and writes deterministic JSON. It
does not call external APIs, send notifications, read production data, mutate
production databases, run production pipelines, or execute Issue text.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_company_intelligence_source_credibility_result.py \
  --input templates/company_intelligence_result.example.json \
  --pretty

python3 scripts/orchestrator/validate_company_intelligence_source_credibility_result.py \
  --input /tmp/company_intelligence_result.example.json \
  --pretty
```

Validation is structural and safety-focused. It verifies contract identity,
company intelligence fields, source score ranges, deterministic fixture flags,
and forbidden secret/runtime/trading text patterns. It does not approve
production use or delivery channel activation.
