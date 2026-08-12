# AI-DEV-209 H2 Qualified News RRE Selection & Rendering Hardening V2

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`

## Repository

- Starting main: `e34a35141643c2c8a46bc65c0bd1d010c12bcdc3`
- Branch: `ai-dev/209-qualified-news-rre-rendering-hardening-v2`
- Issue: [#263](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/issues/263)
- Implementation commit: `4bd2499` (full SHA recorded by Git/GitHub)
- PR / CI / merge: reconciled in the governed final handoff after GitHub gates complete.

## Root-cause audit

The 2026-08-12 natural US 23:00 artifact proved acquisition and admission worked: 60 per-symbol observations normalized, 22 current qualified items admitted, and no parser/retrieval/stale contamination. The failure occurred later. `build_live_runtime_artifact()` built a current `fresh_research_bundle`, then replaced it with the inherited 20:00 institutional bundle. The current card retained `material_news.items`, while the inherited bundle retained an empty `news_intelligence_v2`. `evolve_intraday()` only evolved price/volume state and never bridged current admitted news. Consequently all six symbols reported `NEWS_ADMITTED_NOT_SELECTED`, `RRE_USED=0`, and `RENDERED=0`.

The initial RRE hypothesis/trigger/invalidation text was also stance-template based. Shared SPY/QQQ/SOXX evidence was rendered while no selected-news provenance or primary symbol-specific risk field existed.

## Architecture and fixes

- Later windows preserve the immutable origin research identity but append selected current news through `us_current_news_bridge_v1`.
- Selection is bounded to two items per symbol and ranks official confirmation, materiality, relevance, freshness and event uniqueness.
- Unselected admitted items carry `SELECTION_LIMIT_LOWER_PRIORITY_SOURCE`; stale/invalid items cannot be selected.
- Directionless news is represented as non-directional substantive context with zero bullish/bearish contribution.
- Selected evidence updates the canonical news coverage category, removes the false complete-news gap, and carries headline, publisher, timestamp and source class.
- Research hypothesis, trigger, invalidation and primary risk cite symbol-specific selected evidence. The Dashboard renders current-news provenance before generic directional/market evidence.
- Scoring, prediction, strategy and Decision objects are built before this read-only bridge and are not modified.

## Deterministic validation

The ACTIVE leaf H2 validator mirrors the natural six-symbol admitted partition `4/3/8/4/2/1`, checks non-zero RRE/rendered counts, bounded-selection reasons, official-source preference, stale exclusion, zero directional contribution, differentiated hypothesis/risk/trigger/invalidation, news coverage availability, provenance rendering, unchanged Decision output, AI-DEV-210 regression and registry closure.

Targeted PASS: AI-DEV-198, 201, 202, 207, 208, 209, 210, cross-feature, admission/public parity, notification provenance, production landing integrity, source inventory, Python compile and `git diff --check`.

The executable branch registry selected 24 validators, executed all 23 required leaves, recursion-guarded only the branch orchestrator, passed 23/23 leaves, failed 0 and had 0 unexplained skips. Exact CI and post-merge identities are reported in the final Codex handoff.

## Safety

- Production pipeline / publish / notifications / trading: not executed
- Strategy/scoring/prediction/ranking/eligibility/action/entry/stop/target/sizing: unchanged
- Scheduler/cron/systemd/nginx/firewall: unchanged
- Secrets accessed: false
- Production DB written: false
- Immutable natural artifacts rewritten: false
- Existing runtime/generated artifacts cleaned or staged: false

## Natural verification

The 2026-08-12 US 23:00 artifact remains immutable pre-H2 root-cause evidence. The next eligible post-merge US lifecycle must show qualified current news advancing `ADMITTED → RRE_USED → RENDERED`, explicit selection-limit reasons, headline/source/time visibility, evidence-derived per-symbol narratives, directionless safety, coverage parity and unchanged Decision behavior.
