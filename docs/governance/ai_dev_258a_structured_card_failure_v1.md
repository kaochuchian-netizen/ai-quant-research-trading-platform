# AI-DEV-258A — Structured card diagnostics and truthful fallback

Status: IMPLEMENTED_PENDING_NATURAL_VERIFICATION.
Production baseline: `76f55ae796ce35487e14903bfdd4bc401fe0a26d`.
No deployment, production rerun, notification, database or scheduler change.

## Incident evidence and confidence

2026-10-02 scheduled pre_open_0700, run
`approved-pre_open_0700-delivery-20261002-070001`:
- 07:00:09–07:00:19 historical update: 10 successes, no failures/fallbacks.
- 2330 / 009816 / 2337 each had 123 daily bars, 2026-04-07 through 2026-10-01,
  Shioaji kbars, VALID historical admission, minimum 20 bars.
- 2330 textual report existed (close 2510, technical 強多趨勢, momentum 小幅偏多).
- 07:03:43 NEWS_EVIDENCE_DONE; STRUCTURED_CARD_BUILD then failed in 0.123s with ValueError.
- Archived 2330 fallback: `analysis_failed:ValueError`, `market_data`.
- Existing unavailable_card unconditionally appended market_data regardless of cause.
  This downstream misclassification is proven with high confidence.

Sources: production logs/daily.log; artifacts/runtime/pre_open_stage_timing_latest.json;
artifacts/archive/window_snapshots/tw/pre_open_0700/2026-10-02/revision-0001.json;
data/historical/{symbol}_daily.csv. SHA-256 references are in the regression fixture.
No original archive or CSV is committed.

## Precise original exception is NOT recoverable from retained evidence

The old handler discarded exception message/traceback and did not persist the failed
2330 in-memory news bundle, analysis object or complete intermediate card.
The news collector cache is batch-transient. The existing tactical_latest artifact
was dated July 12 and was excluded as evidence for this October 2 run.
The formal prediction archive generated at 07:10:42 is downstream, not the
07:00:19 tactical input, and was not misrepresented as that input.

Pure offline reconstruction uses saved 123-bar CSVs and the unchanged deterministic
technical/tactical functions. All ten cards pass with news omitted; nine successful
stocks' factors, reasons and directions match their saved cards exactly.
2330 MA5=2488, MA10=2464.5, tactical=no_trade, reason=追高風險過高，等待拉回.
009816 MA5=16.53, MA10=16.38, tactical=bullish.
2337 MA5=119.6, MA10=119.25, tactical=neutral.
This isolates no reproducible historical/technical validation failure.

This is PARTIAL_RECONSTRUCTION_NOT_EXACT_INCIDENT_REPLAY.
It does NOT establish a specific failing production validation, field or value.
News-funnel, semantic-conflict or other validations must not be blamed without
their original input. No validation condition is relaxed and no symbol exception
or speculative root-cause repair is introduced.
The exact original root-cause acceptance item remains unresolved.

## Error semantics

`structured_card_failure_v1` diagnostics record stable reason codes, category,
stage/substage, known validation fields/allowlisted numeric or enum values, safe
exception message, source frame file/function/line and a diagnostic digest.
ValueError-compatible CardValidationError retains existing rejection messages
for known validators. Validation predicates, ranges, thresholds and models stay unchanged.
Contexts identify NEWS_EVIDENCE, TACTICAL_UPGRADE, RESEARCH_PREDICTION,
PREDICTION_PROJECTION and PRODUCT_PROJECTION. The outer pipeline also distinguishes
historical indicators, ADR/news/chip/analysis, persistence and report operations.

Unknown exceptions never serialize args, repr, locals, source lines, chained
exception messages or arbitrary payload values. Known error messages are from a
closed registry; field values accept finite numbers, booleans, None or approved
enum constants. Full raw traceback text is deliberately not logged.
Debug diagnostics are stderr/log-only, not attached to delivery cards.
A future natural failure will retain the failing function/line and, for governed
validators, exact safe field values. No live rerun is authorized for this PR.

Fallback categories:
- market_data_missing: explicitly missing data/file; may mark market_data missing.
- historical_data_invalid: historical admission/indicator invalid; retain known
  historical reason codes, without asserting that no prices exist.
- structured_card_validation_failed: card validator rejects supplied evidence.
- analysis_failed: non-validation analysis/runtime failure, including timeout.
- news_evidence_insufficient: explicit news-only deficiency, never price absence.

Cards carry safe category/reason metadata and Traditional Chinese failure text.
Unknown historical or arbitrary messages are not copied into public fields.
The existing news admission path and codes remain intact. News absence is not
used to infer historical-data absence. All unavailable cards remain non-actionable.

## Offline validation / replay

`python scripts/orchestrator/validate_ai_dev_258a_structured_card_failure_v1.py`
runs the fixture reconstruction plus strict rejection, safe diagnostic, fallback,
ten-stock, deterministic replay and isolated real-handler tests.
Tests block sockets during build_card. The real pipeline exception handler is
compiled in isolation from its AST with in-memory stores; no pipeline is imported
or run by that test.

`python -m unittest discover -s tests -p 'test*mobile*presentation.py'`
and the AI-DEV-257 validator protect presentation and observed-data behavior.
The 258A gate is registered in both branch and post-merge registry execution.
No raw production news body, credentials, database or historical row payload is
part of the fixture; it contains derived tactical aggregates and provenance hashes.

Merge readiness must distinguish diagnostics/semantics readiness from unresolved
original incident reconstruction. Natural verification remains pending; this PR
does not establish that the lost October 2 input would successfully build a card.
