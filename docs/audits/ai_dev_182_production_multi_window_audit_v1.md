# AI-DEV-182 Production Multi-Window Audit V1

This audit is a read-only production-readiness assessment. It does not call a
pipeline, writer, publisher, notification sender, scheduler, trading module, or
`main.py`.

## Truth hierarchy

Evidence is classified independently as Scheduler Trigger → Entrypoint Start →
Runtime Artifact → Snapshot Admission → Archive Renderer → Public Publish →
Notification Formatter → Delivery Attempt → Recipient Receipt. A formatter
preview is never reported as a send, HTTP 200 is never reported as content
correctness, and missing evidence is recorded as `NOT_OBSERVABLE`.

## Evidence and privacy

Only paths, hashes, normalized counts, bounded findings, and delivery state are
stored under `artifacts/audit/ai_dev_182`. Recipient addresses, credentials,
tokens, raw message headers, and raw production payloads are excluded. Existing
runtime and immutable snapshot files are opened read-only.

## Windows and dates

TW covers pre-open 07:00, intraday 13:05, pre-close 13:35, and post-close 15:00
for 2026-07-15 through 2026-07-17. US covers pre-market 20:00, intraday 23:00,
and review 06:30 for the most recent evidence across 2026-07-14 through
2026-07-16. Missing evidence is classified, not coerced to zero.

## Scoring

The 100-point score is evidence-mapped across consistency (20), completeness
(20), decision quality (20), freshness (15), UX/readability (15), and
operational reliability (10). The detailed component evidence is generated in
`production_readiness_scorecard.json`.

## Public UX evidence

The audit inspects Landing, TW/US dashboards, and all 14 fixed archive routes at
the DOM level. The in-app browser screenshot command timed out repeatedly on the
long production page. The report therefore explicitly records screenshot QA as
`NOT_OBSERVABLE` and retains DOM, responsive CSS, duplicate-ID, marker, link and
overflow-oriented evidence; it does not claim pixel-level screenshot QA.

## Known production evidence gaps

TW approved wrappers prove completed or timed-out delivery decisions, but do not
persist the exact sent Email/LINE body with snapshot identity. Recipient receipt
is unavailable for both markets. These are observability findings, not assumed
delivery failures.

## Rollback

The implementation adds only audit scripts, this document, and dedicated audit
outputs. Rollback is removal of those audit-only files; no production rollback
or archive mutation is involved.
