# AI-DEV-212 H3 Entity Subject Attribution & Event Reasoning Closure V3

## Status

IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION

## Repository

- Starting main: `74866ae6bd815d173b94db6990a6b06a458d9edb`
- Feature branch: `ai-dev/212-h3-semantic-integrity-closure-v3`
- Implementation commit: `80ad889238680dac1c9f830f05fed1fa7176a7b3`
- Pull request: `#276`
- Initial implementation CI: GitHub Actions `31683687686` — PASS
- Merge/current main: assigned by GitHub after the final required CI; recorded in the post-merge handoff

## Confirmed Root Causes

- Entity attribution V3 treated a title match as primary ownership before resolving macro, roundup, comparative, and competing-entity framing.
- Competing-entity recognition depended too heavily on the static entity/watchlist map and missed structured related tickers and uppercase ticker tokens.
- `material_news()` did not carry `entity_attribution`, so final RRE selection and `finalized_current_news_projection_v2` lost provenance.
- Event-family matching treated `customer` as generic product demand and lacked explicit customer-concentration and joint-venture mechanisms.
- Manual-rerun audit reused the pre-run latest archive date as `effective_trading_date`, even after a new canonical snapshot resolved another date.

## Architecture

- `us_entity_subject_resolution_v4` resolves headline framing before company ownership and records target, subject, competing entities, relationship, framing and reason.
- `finalized_current_news_projection_v3` preserves selected-item attribution provenance and remains the sole source for compatibility surfaces.
- Absence states remain derived from authoritative funnel counts and rejection reasons; stale-only requires an actual `STALE` rejection.
- Event-mechanism reasoning adds customer-concentration and joint-venture contracts and strengthens supply-chain/capex reasoning.
- Manual rerun now separates `requested_effective_date` from `resolved_effective_trading_date`; the legacy `effective_trading_date` field means the resolved canonical date.

## Deterministic QA

The dedicated ACTIVE leaf validator covers TSLA macro reaction, SPCX roundup, comparative SpaceX references, GOOGL primary events, NVDA/Verizon and TSM/ASML recall, NVDA concentration reasoning, TSM JV/supplier reasoning, finalized attribution, all absence states, mutation rejection, surface parity, manual-date provenance and Decision safety.

The executable branch registry selected 29 required validators, executed 28 leaves, recursion-guarded only the branch orchestrator, and reported 28 passed leaves, zero failures and zero unexplained skips.

## Safety

- Production pipeline executed: false
- Trading/orders: false
- LINE/Email sent: false
- Scheduler/systemd/nginx changed: false
- Secrets accessed: false
- Production DB written: false
- Immutable archive rewritten: false
- Strategy/scoring/prediction/ranking/eligibility/action changed: false

## Remaining Verification

A new PM-authorized US `us_pre_market_2000` manual rerun is required after merge. The immutable pre-H3 revision remains failure evidence and is not rewritten or claimed as post-H3 proof. Natural verification remains pending after controlled verification.
