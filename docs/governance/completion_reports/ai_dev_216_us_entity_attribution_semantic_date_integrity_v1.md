# AI-DEV-216 US Entity Attribution Semantic Closure, Multi-Company Relationship Guard & Canonical Delivery Date Integrity V1

## Status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`

## Repository identity

- Starting main: `fc5d88ad4658829a689c17ff0071ca945d237e25`
- Branch: `ai-dev/216-us-semantic-date-closure`
- Implementation commit: `3200392`
- Pull request: pending
- CI: pending
- Merge/current main: pending post-merge reconciliation

## Root causes

The AI-DEV-215 controlled recovery proved the runtime, provenance, admission, publish, visual and notification paths, then exposed two semantic attribution defects and one delivery-date identity defect.

1. SPCX comparative-valuation headlines could pass the primary-subject fallback because Anthropic was absent from competing-entity recognition and valuation comparisons such as “would top SpaceX” were not modeled.
2. AAPL editorial lists could be promoted to a material relationship because the bare word `investment` was treated as a relationship marker, “feature highlights / investment ideas” were not roundup frames, and Microsoft was not recognized as a competing entity.
3. Email subject/header used `generated_at[:10]`, so an after-midnight execution date replaced the canonical US effective trading date.

## Implementation

- Entity subject resolution V5 adds deterministic comparative-valuation, editorial roundup and broader structured competing-entity signals before primary-subject fallback.
- Material relationships now require a bounded relationship pattern and mechanism/party structure. Generic investment/editorial words are not sufficient; structural forms such as `invests in`, `strategic investment in`, `equity stake in` remain accepted.
- Semantic mutation validation recomputes attribution from the source headline instead of accepting an internally consistent but wrong classification.
- The approved US delivery runner now stamps `effective_trading_date` once from the canonical New York session resolver and reuses it for snapshot identity, Email, delivery provenance and Operations provenance.
- Email subject/header derive from the canonical date. Execution time remains separately available as `generated_at`.
- Runtime date propagation is fail-closed through `validate_delivery_date_contract()` before admission.

## Natural-shaped deterministic evidence

- Exact SPCX fixture: rejected with `COMPARATIVE_REFERENCE_NOT_COMPANY_EVENT`.
- Exact AAPL fixture: rejected with `MARKET_ROUNDUP_NOT_COMPANY_EVIDENCE`.
- GOOGL Pixel/Gemini: retained as primary company evidence.
- NVDA/Verizon: retained as a material `teams_up` relationship.
- TSM/ASML: retained as a material supplier relationship.
- Legitimate `Apple makes a strategic investment in Anthropic`: retained as `strategic_investment`.
- Email fixture with generated time `2026-08-14T00:42:47+08:00` and canonical date `2026-08-13`: subject and visible header both use `2026-08-13`.

## Mutation coverage

The dedicated gate rejects:

- comparative-valuation evidence forced to PRIMARY;
- editorial investment wording forced to a material relationship;
- removal of competing-entity provenance;
- switching Email identity back to `generated_at`;
- removal of canonical effective-date propagation.

It also executes the production-shaped `material_news()` → `build_for_symbol()` → RRE → finalized projection path and verifies nested attribution continuity and mutation isolation.

## Changed files

- `app/research/news_evidence_funnel.py` — subject resolution V5, relationship patterns and executable semantic parity checker.
- `scripts/orchestrator/approved_us_stock_delivery.py` — canonical delivery-date propagation and Email date parity.
- `scripts/orchestrator/validate_ai_dev_212_h3_semantic_integrity_closure_v3.py` — V5 provenance regression expectation.
- `scripts/orchestrator/validate_ai_dev_216_us_entity_attribution_delivery_date_v1.py` — dedicated natural-shaped, mutation and production-path gate.
- `config/governance/validator_registry_v1.json` — ACTIVE required branch/post-merge leaf registration.
- This completion report.

## Validation

Final command matrix and registry selected/executed counts are populated by the PR and post-merge completion evidence. The dedicated AI-DEV-216, AI-DEV-214, hardened H3 and H2 gates pass before PR. Real Chromium CJK/PDF regression completed through H2 without renderer changes.

## Safety

- Strategy/scoring/prediction/ranking/eligibility/action: no change.
- Entry/Stop/Target/sizing/execution: no change.
- Production rerun: false.
- LINE/Email sent: false.
- Scheduler/cron/systemd/nginx changed: false.
- Services restarted: false.
- Secrets accessed or changed: false.
- Production DB written: false.
- Immutable archives rewritten: false.
- Existing runtime/generated artifacts were preserved and excluded from the task commit.

## Remaining verification

A second PM-authorized controlled US 20:00 verification must confirm semantic behavior on a new immutable revision. This implementation does not claim controlled or natural verification.
