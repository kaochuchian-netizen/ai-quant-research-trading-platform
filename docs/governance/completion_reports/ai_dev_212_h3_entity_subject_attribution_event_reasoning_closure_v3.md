# AI-DEV-212 H3 Entity Subject Attribution & Event Reasoning Closure V3

Task ID: AI-DEV-212

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

## Implementation

Implemented framing-first Entity Subject Resolution V4, competing-entity detection independent of the watchlist, finalized projection V3 attribution provenance, customer-concentration/JV/capex reasoning contracts, fail-closed semantic mutations, and requested-versus-resolved manual-date provenance.

## User-visible Outcome

Macro reactions, multi-ticker roundups and comparative SpaceX references can no longer present as company-primary research. Qualified company and material-relationship news retains explainable attribution, while counter arguments now describe the actual economic mechanism rather than unrelated demand boilerplate.

## Evidence

The immutable pre-H3 controlled revision reproduces the TSLA/SPCX attribution false positives, missing finalized provenance, NVDA/TSM mechanism mismatch and date ambiguity. Deterministic fixtures reproduce those shapes without rewriting the archived revision.

## Quality Gate

Dedicated H3: 24/24 PASS. Executable branch registry: selected 29, executed 28 leaves, one orchestrator recursion guard, 28 passed, zero failures and zero unexplained skips. GitHub Actions runs `31683687686` and `31683931668` passed. Post-merge registry and platform inspector passed on merge main `df6634b46086e0a6f0a48b95214c7a7ed7ac5112`.

## Regression

AI-DEV-212 H2/V1, AI-DEV-209 core/H2/H3, AI-DEV-210, AI-DEV-211, AI-DEV-207, AI-DEV-202, US Research, TW RRE, seven-window cross-feature, admission/public parity, notification provenance, landing integrity, source inventory, workspace governance, Python compilation and diff checks all pass.

## Production Usability

The deterministic implementation is production-compatible and read-only with respect to Decision/trading ownership. It is not yet controlled-product verified; PM must create a new post-H3 US 20:00 manual rerun.

## Known Limitations

Headline/metadata subject resolution cannot safely infer relationships absent from provider evidence; ambiguous cases intentionally fail closed. Controlled and natural evidence remain pending.

## Deferred Enhancements

Desktop information density remains P3 UX debt. No LLM reasoning, new provider, scheduler, public transport, or trading behavior is introduced.

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

## Natural Verification

After controlled verification passes, eligible TW four-window and US three-window scheduled batches must confirm attribution provenance, absence semantics, event-mechanism narratives, channel parity, visual readability and unchanged Decision outputs.

## Phase Contribution

Closes deterministic Research Evidence Semantic Integrity defects between source attribution, finalized RRE provenance, PM-facing reasoning and manual-run identity without transferring authority to Research.

## Final Status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`
