# US Research Intelligence, Prediction Calibration & Continuity V2

## Purpose

AI-DEV-201 extends the existing admitted US institutional research bundle. It does not introduce a parallel truth source and does not change Decision Layer action, eligibility, ranking, strategy weights, thresholds, execution, scheduler, or delivery policy.

Canonical flow:

`source facts → institutional research bundle → Research Intelligence V2 → existing Decision Layer → Dashboard / Archive / Email preview / LINE preview / Operations`

The 20:00 admitted bundle owns the origin research identity. Later windows retain that immutable origin and append window evidence to produce a distinct `window_research_identity`.

## Layer ownership

- Evidence Layer owns facts, source, timestamps, freshness, source quality, materiality and dedup identity.
- Research Layer owns interpretation, supporting/opposing/missing evidence, market/sector regime, hypothesis and counterargument.
- Prediction/Evaluation Layer owns range, direction, regime, setup and calibration evaluation.
- Decision Layer remains the sole owner of action, eligibility, lifecycle and ranking.
- Notification Layer only formats the canonical projection.

The V2 boundary object must remain read-only. Any trade action export, rank mutation, scoring mutation, strategy-weight mutation, prediction-model mutation or auto-learning is a validation failure.

## Source quality and availability

Source quality is ordered from Tier 1 official/regulatory/company evidence through Tier 5 weak or unverified reference. Lower-quality secondary evidence cannot replace or silently override primary evidence. Conflicts stay explicit.

Provider states remain truthful: connected, configured, available, not configured, not licensed, failed or stale. Missing or failed sources never create neutral evidence. A missing live-news feed produces an explicit coverage gap; it never fabricates a headline.

## Evidence and SEC classification

Every admitted V2 evidence record retains source, source class, quality tier, published/observed timestamps, freshness, stale flag, materiality, direction, role, provenance and dedup identity.

SEC classification uses deterministic form/item/summary rules for earnings, guidance, M&A, material agreements, financing, issuance, buybacks, management changes, legal/regulatory matters, cybersecurity, restructuring, business updates and insider-related events. Insufficient metadata remains `other` and `neutral`; direction is never fabricated.

## Effective coverage

Coverage is a weighted research-utility measurement, not a source count and not a trading score. Categories include official, fundamentals, earnings, macro, market, sector, ETF, news, options, analyst and insider evidence. `NOT_APPLICABLE` is excluded from penalty, stale/contradictory/partial evidence receives reduced utility, and duplicate evidence is counted once.

Unavailable options, analyst and insider providers remain explicit contextual gaps. They never create actions.

## Three-window continuity

### 20:00

Build the initial Research Brief, evidence partitions, effective coverage, decomposed broad/growth/sector regime, hypothesis, trigger, invalidation and counterargument.

### 23:00

Read the exact admitted 20:00 bundle by effective date/revision/admitted time. Append observed Gap, volume and market evidence. Classify the hypothesis as confirmed, strengthened, unchanged, weakened, contradicted, invalidated or insufficient new evidence. Never promote a watch/no-trade plan or mutate the Decision Layer.

### 06:30

Evaluate range width and errors, direction, regime/setup availability and calibration when a deterministic probability with method metadata exists. No-trade cases still produce prediction usefulness, conservative-decision review, possible missed-opportunity candidate, evidence-quality diagnosis and next-session carryforward. This is review evidence only; no threshold or model weight changes automatically.

## Prediction calibration

The existing deterministic interval forecast remains unchanged. V2 adds optional contracts for direction probability, regime forecast and setup probability. A probability is evaluated only when both a value and method/provenance exist. Brier score is absent otherwise. Interval hit never alone proves prediction quality; interval width and high/low/midpoint errors are retained.

## Channel parity

Dashboard and Archive render the Research Brief first and keep detailed evidence in an expandable section. Email preview may include fuller context. LINE remains concise. Operations records origin and window identities plus hypothesis state. All channels consume the same canonical bundle; formatters do not recompute research.

## Deterministic replay

Run:

```bash
./venv/bin/python scripts/orchestrator/validate_ai_dev_201_us_research_intelligence_v2.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_dev_201_us_historical_replay_v1.py --pretty
```

The replay uses a temporary archive only. It proves same evidence yields the same identity, changed evidence yields an explainable new identity, later windows retain the admitted origin identity, and post-close evaluation links to the originating prediction. It sends no notification, writes no production DB/archive, changes no scheduler and places no order.

## Degradation and timeouts

Secondary source failure must be isolated by the existing provider adapter boundary. V2 consumes only data already returned by the source layer and performs no one-off network calls. Missing, stale and failed states are preserved. Primary market data and Decision Layer continue under existing safe-degradation rules.

## Rollback

Revert the AI-DEV-201 implementation commit. No schema migration, scheduler change, production publish, archive rewrite or backfill is required. Existing V1 fields remain present for backward compatibility.

## Natural verification

Status remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until one complete natural US 20:00 → 23:00 → 06:30 lifecycle demonstrates source truthfulness, research differentiation, SEC/news behavior, broad/sector divergence, meaningful hypothesis evolution, no-trade learning and five-channel identity parity without Decision Layer ownership regression.
# AI-DEV-212 semantic integrity addendum

Company Research direction follows `research_direction_ownership_v1`:

- official/company-specific filings, earnings, guidance, fundamentals and
  qualified substantive company events may establish direction when their own
  direction is safely evaluated;
- SPY/QQQ/SOXX, sector, ETF, price, volume, technical and ADR observations are
  `contextual_confirmation_only` and cannot create company direction;
- qualified directionless news remains selected/rendered with contribution
  `bullish=0, bearish=0`;
- absent company-direction evidence resolves to `insufficient_evidence` and an
  unavailable expected direction, without creating a Decision state.

Narratives use `deterministic_company_event_narrative_v1`. The primary company
event is assigned to an evidence family (earnings/guidance, regulatory/legal,
product/demand, capex/supply-chain, contract/partnership,
management/capital-allocation, filing/disclosure, or material company news).
Hypothesis, confirmation, invalidation and risk cite the actual headline and
family. Price confirmation is secondary.

Yahoo entity attribution uses `us_entity_attribution_v2`. Explicit provider
related-ticker metadata is accepted; an unambiguous title entity is accepted;
summary-only co-mentions and competing primary-title entities are rejected with
machine-readable provenance. All user-visible current-news surfaces consume the
post-selection finalized funnel; compatibility fields are projections, not an
independent truth.
