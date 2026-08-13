# AI-DEV-209 H3 User-Visible Research Presentation Closure

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`

## Repository

- Starting main: `b848e164fccc32366f4c59083f539445d005b68a`
- Branch: `ai-dev/209-h3-user-visible-research-presentation-closure`
- Issue: [#266](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/issues/266)
- Implementation commit / PR / CI / merge: recorded by the governed final handoff after GitHub gates complete.
- Starting workspace: main/origin-main `0/0`; 174 preserved runtime/generated paths, zero unknown dirty paths.

## Root-cause audit

Issue #265 natural evidence proved the H2 acquisition and research contracts were healthy: 60 observations were discovered/retrieved/normalized, 29 were admitted, and 10 qualified current items reached both `RRE_USED` and the institutional-research DOM. Directionless and stale-evidence safeguards also passed.

The remaining defect was downstream presentation divergence. The US 06:30 Dashboard main card and Email read inherited `source_trade_plan.news_evidence` from the 20:00 plan, so its legacy no-news value overrode the later-window canonical `institutional_research.news_intelligence_v2`. The expandable institutional-research section contained selected provenance and differentiated narratives, but Visual Evidence captured visible text and PDF while the `<details>` elements were closed. Thus HTML source contained the correct evidence while the PM-facing main card, Email, rendered text and PDF could omit it.

## Architecture and changed components

- `app/us_stock/research_presentation.py` is the single presentation-only current-news projection. It consumes canonical selected items and preserves distinct `AVAILABLE`, `NO_RELEVANT`, `RETRIEVAL_FAILED`, `STALE_ONLY`, `ADMITTED_NOT_SELECTED` and `SELECTED_NOT_RENDERED` states.
- `app/dashboard/multi_market_dashboard.py` uses that projection in all three US window cards. A legacy source-plan absence can no longer overwrite qualified current news. Research details carry an explicit visual-review allowlist marker.
- `scripts/orchestrator/approved_us_stock_delivery.py` uses the same projection for Email and includes hypothesis, trigger, invalidation and primary risk without changing delivery or Decision semantics.
- `app/dashboard/visual_evidence_archive.py` archives the original collapsed HTML, then expands only allowlisted PM research details in the in-memory Chromium DOM used for rendered text, screenshot and PDF. Manifest metadata records the selector, expansion count and that the published DOM was not modified.
- `requirements-validation.txt` pins `pypdf` so CI performs real PDF text extraction.
- The H3 validator, executable registry and pending-natural-verification contract close deterministic and governance enforcement.

## Before / after

- Before: canonical current news could be `RRE_USED` and present in hidden HTML while the 06:30 main card and Email said no news.
- After: Dashboard and Email show the same canonical compact headline/source/time/source-class state.
- Before: screenshot/text/PDF represented collapsed research details.
- After: interactive published HTML remains collapsed, while review screenshot/text/PDF expand only explicitly allowlisted research details and expose selected provenance plus per-symbol hypothesis/risk narratives.
- No selected news remains truthful: retrieval failure, no relevant news and stale-only are separate states. Directionless qualified news is visible but retains zero bullish/bearish contribution.

## Deterministic validation

The ACTIVE H3 leaf validator uses six natural-shaped US symbols, deliberately injects a contradictory legacy no-news field, and proves canonical news wins in Dashboard and Email. It verifies six differentiated narratives, three no-selected states, directionless safety and immutable Decision context. A real Playwright Chromium capture produces a 16-page PDF; `pypdf` confirms all six selected evidence fingerprints and the expanded Hypothesis / Trigger / Invalidation / Main Risk sections. The archived HTML remains collapsed. H2 and AI-DEV-210 validators execute from the H3 gate and pass.

Final exact targeted, registry, CI and post-merge execution counts are reported in the final Codex handoff. No required validator is skipped or weakened.

## Safety

- Production pipeline / publish / LINE / Email / trading: not executed
- Strategy/scoring/prediction/ranking/eligibility/action/entry/stop/target/sizing: unchanged
- Scheduler/cron/systemd/nginx/firewall: unchanged
- Secrets accessed: false
- Production DB written: false
- Immutable natural artifacts rewritten: false
- Existing runtime/generated artifacts cleaned or staged: false

## Natural verification

The Issue #265 artifact is immutable pre-H3 evidence and is not post-fix verification. The next eligible natural US lifecycle, especially 06:30, must prove canonical selected news and differentiated hypothesis/trigger/invalidation/risk appear consistently in Dashboard main cards, Email preview, rendered text and Visual Evidence PDF while no-news states remain truthful and Decision ownership remains unchanged.
