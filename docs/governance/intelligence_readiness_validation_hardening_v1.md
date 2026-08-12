# Intelligence Readiness & Validation Hardening V1

## Purpose

Runtime completion and investment-intelligence readiness are different facts. `runtime SUCCESS` never upgrades market data, research, prediction, or Decision input readiness. Deterministic defects are fixed before natural verification; natural verification confirms that the repaired contract survives real scheduled data.

## Canonical readiness

`intelligence_readiness_v1` reports market data, historical data, technical evidence, research evidence, baseline prediction, full prediction, Decision input, outcome evaluation, and overall intelligence. Every applicable universe dimension preserves `ready_symbols`, `total_applicable_symbols`, `coverage_ratio`, method, version, provenance, and reason codes.

Universe aggregation is denominator based:

- `NONE`: 0 applicable symbols ready.
- `PARTIAL`: more than 0 but fewer than all applicable symbols ready.
- `COMPLETE`: all applicable symbols ready.
- `NOT_APPLICABLE`: no applicable symbols.

No `any()` promotion may turn 1/9 into complete or sufficient.

## Decision input readiness

Decision readiness is derived from explicitly declared Decision-required inputs. For TW intelligence health V1 these are admitted market evidence, full technical evidence, and research evidence meeting the named full-readiness coverage threshold. This health projection does not change action, eligibility, ranking, entry, stop, target, or execution.

The states are `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, and `NOT_EVALUATED`. A read-only research bundle that does not contain the Decision contract reports `NOT_EVALUATED`, never hard-coded `SUFFICIENT`.

## Prediction readiness

Baseline prediction remains independently evaluable when enough deterministic market history exists, including when action is `NO_TRADE`. Full prediction requires baseline evaluability plus full technical readiness and the named research-coverage contract. The output distinguishes `BASELINE_EVALUABLE`, `DEGRADED_BASELINE`, `FULL_READY`, `PARTIAL`, and `INSUFFICIENT`.

## Degradation taxonomy

- `STRUCTURAL_DEGRADATION`: canonical architecture contradicts its own admitted data.
- `CONSUMER_DISCONNECTED`: normalized provider evidence is lost downstream.
- `PROVIDER_FAILURE`: a required provider failed.
- `EXPECTED_SOURCE_GAP`: known unconfigured or unavailable category.
- `OPTIONAL_SOURCE_UNAVAILABLE`: optional contextual feed absent.
- `INSUFFICIENT_DATA`: data exists but cannot satisfy lookback/quality.
- `NOT_APPLICABLE`: the evidence category does not apply.

Complete quotes plus partial optional research is a truthful gap, not automatically a structural incident. Provider evidence present but absent from its consumer is high-severity degradation.

## TW session freshness

Daily-history admission compares the latest bar with the expected latest completed TW trading session for the window. Pre-open and intraday windows expect the previous completed session; post-close may admit the target session. Weekends are deterministic and repository/runtime holiday dates can be supplied. Unknown future exchange holidays remain an explicit limitation; the contract does not widen an arbitrary calendar-day tolerance. A bar after the eligible session is `FUTURE_DATA`.

## No-lookahead timestamp provenance

Outcome timestamps use this hierarchy:

1. `ACTUAL_EVIDENCE`
2. `BAR_TIMESTAMP`
3. `SESSION_FALLBACK`

Fallback is explicit with a reason code. All timestamps are timezone-aware and must satisfy input cutoff, outcome observation, outcome cutoff, review time, and effective-trading-date ordering. Malformed, naive, future, later-intraday, post-close-in-preopen, or wrong-session inputs fail closed.

## Instrument master invariant

The formal TW universe is versioned in `formal_instrument_universe_v1.json` and must be a subset of the canonical instrument master. Company metadata requires sector, industry, and peer group. ETF company-only evidence is `NOT_APPLICABLE`; ADR evidence applies only to explicit mappings. Missing metadata fails the invariant rather than being fabricated.

## Validator lifecycle and quality

`validator_registry_v1.json` assigns every registered validator one lifecycle:

- `ACTIVE`: must execute successfully when its scope applies; exception is failure.
- `SUPERSEDED`: names an active replacement.
- `DEPRECATED`: retains a reason.
- `HISTORICAL_ONLY`: cannot be current product-health evidence.

Production-shape fixtures identify their raw schema/version and exercise raw provider shape through the production normalizer into semantic output. Tautologies, key-only checks, idealized consumer-only shapes, swallowed exceptions, and assertion-count inflation are prohibited. Fixture and replay success never count as natural production verification.

## Natural verification

After deterministic gates pass, inspect a complete TW 07:00→13:05→13:35→15:00 and US 20:00→23:00→06:30 lifecycle. Confirm ratios, baseline/full prediction, Decision readiness, actual timestamp method, degradation categories, instrument coverage, Operations semantics, and channel identities. This confirms runtime behavior; it does not excuse known deterministic defects or prove predictive accuracy.
