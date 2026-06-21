# Source Credibility Taxonomy

This document defines source credibility tiers and usage rules for investment
research records. It is a design policy only and does not implement scraping,
notification, production pipeline execution, trading, or order placement.

## Core Principle

Investment institution target prices, broker buy/sell calls, and analyst ratings
must not be core decision inputs. They may be stored only as low-priority market
sentiment, consensus, or context metadata after being clearly labeled.

Core research should prioritize:

- Company official material information.
- Financial statements.
- Earnings calls and investor conferences.
- Annual reports and monthly revenue.
- Company official press releases.
- Management media interviews.
- Company guidance.
- Upstream and downstream industry trends.
- Peer financial reports and industry supply/demand changes.

## Source Tier Definitions

| Tier | Name | Examples | Default Use |
| --- | --- | --- | --- |
| `tier_1_official_filing` | Official filing / regulatory disclosure | MOPS material information, audited financial statements, annual reports, monthly revenue filings | Primary factual source; allowed for core company facts. |
| `tier_1_company_official` | Company official communication | Official press releases, investor presentations, earnings call transcripts, company guidance | Primary company source; allowed for core facts when attributable. |
| `tier_2_peer_and_industry_primary` | Peer or industry primary data | Peer earnings reports, industry association data, supply/demand statistics, customs/shipment data | Core industry context when methodology is clear. |
| `tier_2_management_interview` | Attributed management interview | Named executive interviews in reputable media | Useful qualitative context; requires attribution and review. |
| `tier_3_reputable_media` | Reputable news media | Established financial or business media with named sourcing | Context source; should not override official disclosures. |
| `tier_3_market_data` | Market data | Price, volume, ADR, index, rates, FX, sector performance | Quantitative context; source and timestamp required. |
| `tier_4_consensus_and_analyst` | Analyst / broker / consensus metadata | Target prices, rating changes, broker reports, consensus EPS | Low-priority sentiment/consensus metadata only. Not a core decision input. |
| `tier_5_unverified_or_social` | Unverified or social source | Forums, anonymous posts, unsourced rumors, social media | Excluded from core scoring; may only trigger manual review if retained. |

## Source Metadata Schema

Every source reference should include:

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `source_id` | text | required | Stable id for the source item. |
| `source_tier` | text | required | One of the taxonomy tiers. |
| `source_type` | text | required | Example: `filing`, `press_release`, `earnings_call`, `media`, `market_data`, `analyst_report`. |
| `publisher` | text | required | Company, regulator, exchange, media, or provider. |
| `title` | text | optional | Source title. |
| `published_at` | text | required when available | ISO 8601 timestamp or date. |
| `retrieved_at` | text | required | Timestamp when captured. |
| `url` | text | optional | Source URL if available. |
| `document_id` | text | optional | Filing id, report id, or provider id. |
| `language` | text | optional | Source language. |
| `attribution` | text | required for interviews/media | Named speaker, author, or organization. |
| `license_or_access` | text | optional | Internal note for access restrictions. |
| `excerpt_policy` | text | required | Prefer paraphrase and short excerpts only. |
| `notes` | text | optional | Caveats. |

Do not store credentials, API keys, passwords, tokens, or private provider
secrets in source metadata.

## Effective Source Tier

When multiple sources support one record, `source_tier` should represent the
highest-quality source that directly supports the conclusion.

Rules:

1. A high-tier source cannot upgrade an unrelated low-tier claim.
2. Conflicting sources require `data_quality.conflicting_sources = true`.
3. If an analyst report cites a company filing, use the company filing directly
   where possible instead of treating the analyst report as the primary source.
4. Market price reaction can be `tier_3_market_data`, but interpretation still
   needs separate evidence.
5. Unverified rumors must not be promoted into core scoring through repetition.

## Allowed Uses By Tier

| Tier | Core factual fields | Core scoring | Forecast assumptions | Dashboard display | Email report |
| --- | --- | --- | --- | --- | --- |
| `tier_1_official_filing` | yes | yes | yes | yes | yes |
| `tier_1_company_official` | yes | yes | yes | yes | yes |
| `tier_2_peer_and_industry_primary` | yes | yes for industry context | yes | yes | yes |
| `tier_2_management_interview` | yes with attribution | limited | yes with caveat | yes | yes with caveat |
| `tier_3_reputable_media` | limited | limited | limited | yes with source label | yes with source label |
| `tier_3_market_data` | yes for market facts | yes for quantitative context | yes | yes | yes |
| `tier_4_consensus_and_analyst` | metadata only | no | no as primary basis | yes as context | yes as context |
| `tier_5_unverified_or_social` | no | no | no | hidden by default | no by default |

## Analyst Target Price Handling Policy

Analyst target prices, broker ratings, upgrades, downgrades, and buy/sell calls
may be retained only under a clearly separated metadata policy.

Allowed fields:

| Field | Type | Notes |
| --- | --- | --- |
| `analyst_metadata_id` | text | Stable id. |
| `stock_id` | text | Security id. |
| `as_of_date` | text | Date of rating or target price. |
| `publisher` | text | Broker or institution name. |
| `rating_text` | text | Original rating label, if retained. |
| `target_price` | numeric | Target price, if available. |
| `target_price_currency` | text | Currency. |
| `previous_target_price` | numeric | Optional. |
| `rating_change` | text | `upgrade`, `downgrade`, `initiate`, `maintain`, or `unknown`. |
| `source_tier` | text | Must be `tier_4_consensus_and_analyst`. |
| `allowed_usage` | array | Must not include core decision scoring. |
| `notes` | text | Context and caveats. |

Required restrictions:

- Do not use target price as a core score component.
- Do not use broker rating as a buy/sell decision rule.
- Do not promote analyst consensus above company filings, financial statements,
  official guidance, or primary industry evidence.
- If displayed, label it as market consensus or sentiment metadata.
- If used in models later, it must be a low-priority contextual feature with
  separate ablation tests and explicit review.

## Confidence Guidance

`confidence` should reflect the reliability and relevance of source evidence,
not expected investment return.

Suggested mapping:

| Confidence | Meaning |
| --- | --- |
| `0.80-1.00` | Strong official or primary-source basis, recent, consistent. |
| `0.60-0.79` | Good source basis with minor gaps or some interpretation. |
| `0.40-0.59` | Mixed evidence, stale inputs, or material assumptions. |
| `0.20-0.39` | Weak or indirect evidence; human review required. |
| `0.00-0.19` | Unusable for automated scoring; retain only for audit if needed. |

## Review Rules

Set `requires_human_review = true` when:

- Source tier is `tier_4_consensus_and_analyst` or `tier_5_unverified_or_social`.
- Sources conflict on material facts.
- Source is stale relative to the forecast horizon.
- Missing data affects a required schema field.
- A record may appear in dashboard or email output with investment implications.

