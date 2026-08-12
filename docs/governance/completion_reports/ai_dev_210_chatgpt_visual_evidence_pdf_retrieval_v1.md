# AI-DEV-210 ChatGPT Visual Evidence Auto-PDF & Retrieval Access V1

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`

## Repository

- Starting main: `45eca6f6e98181cca7e016d526ecdd38af1327c6`
- Feature branch: `ai-dev/210-chatgpt-visual-evidence-pdf-retrieval-v1`
- Requested Issue: #262; GitHub CLI returned `Could not resolve`, so no Issue state is fabricated.
- Commits / PR / CI / merge: reconciled in the governed final handoff.

## PDF architecture

AI-DEV-210 extends the existing AI-DEV-208 browser transaction. The same Chromium page and DOM now produce `screenshot_full.png`, `rendered_page.html`, `rendered_text.md`, and a real `page.pdf()` result named `dashboard_full.pdf`. PDF uses print backgrounds, A4 pagination, and the same observed snapshot identity. It is not a screenshot-to-PDF conversion and never feeds Research, Prediction, Decision, delivery or trading.

`visual_evidence_manifest_v2` records PDF filename, size, SHA-256, renderer (`playwright-chromium-page-pdf`), print settings, status, reason and `same_browser_page_and_dom` identity source. Index records carry PDF path/hash. Every revision remains immutable.

PDF failure creates a durable `DEGRADED` attempt with `PDF_RENDER_FAILED` or `PDF_WRITE_FAILED`; `production_batch_continues=true`. Daily review preserves latest-valid/latest-attempt semantics. Legacy V1 manifests remain readable and PDF selection returns `NOT_AVAILABLE / PDF_NOT_CAPTURED`; no historical evidence is backfilled.

## Retrieval and security

`export_visual_evidence.py` accepts only canonical date, market, window, revision and artifact selectors. Selection resolves through index → manifest → filename allowlist → root containment/hash verification. It rejects traversal, absolute paths, symlink escape, unknown identity, `.env`, secrets, DB, source, logs and any non-allowlisted file.

Supported artifact types are PDF, PNG, text, HTML, manifest, canonical reference and deterministic daily ZIP. ZIP entries are sorted, timestamp-normalized, permission-normalized and limited to Visual Evidence review files. Export copies are written under the governed runtime export root and preserve source hashes. Export never mutates the canonical archive.

Examples:

```bash
python3 scripts/orchestrator/export_visual_evidence.py --date YYYY-MM-DD --market US --window us_pre_market_2000 --artifact pdf --pretty
python3 scripts/orchestrator/export_visual_evidence.py --date YYYY-MM-DD --artifact daily_bundle --pretty
```

## ChatGPT transport status

1. GCP archive automatically produces PDF after an eligible post-merge capture: implemented; natural verification pending.
2. Deterministic retrieval/export by canonical selector: implemented and deterministically validated.
3. Direct ChatGPT access to a GCP filesystem artifact: **not available in the current session/infrastructure**.
4. Missing external capability: an approved authenticated artifact connector or an explicit user-mediated upload/copy transport.

Canonical status: `DIRECT_CHATGPT_TRANSPORT_PENDING_EXTERNAL_CAPABILITY`. No unauthenticated web listing or public archive was introduced.

## Deterministic validation

The dedicated ACTIVE leaf validator exercises real Chromium PDF generation for TW and US, validates `%PDF`/EOF/page structure, all hashes, same-revision identity, immutable revisions, daily latest revision, PDF degradation isolation, legacy compatibility, selector export, deterministic allowlisted ZIP, traversal/absolute/symlink/secret/DB/source/log rejection, read-only archive behavior, temporary-root cleanup, seven-window registry reuse, AI-DEV-208 semantics and AI-DEV-209 regression.

Final command results, executable registry counts, PR/CI and post-merge identities are reconciled in the final Codex report.

## Storage impact

Fixture PDFs are approximately 10–20 KB for simple pages; production dashboards will be larger and scale with rendered content. V1 performs no destructive retention. Future cold-storage/retention policy remains a separate governed decision.

## Safety

- Production pipeline / publish / notifications / trading: not executed
- Strategy/scoring/prediction/ranking/eligibility/action/entry/stop/target/sizing: unchanged
- Scheduler/cron/systemd/nginx/firewall: unchanged
- Secrets accessed: false
- Production DB written: false
- Immutable history rewritten or backfilled: false
- Existing runtime/generated artifacts cleaned or staged: false

## Natural verification

The first eligible post-merge natural batch must prove automatic PDF creation, same-snapshot identity/hash, index/daily-review inclusion, selector export and archive/export hash parity. The pre-AI-DEV-210 2026-08-12 US 20:00 evidence cannot be used as auto-PDF verification and must not be backfilled.
