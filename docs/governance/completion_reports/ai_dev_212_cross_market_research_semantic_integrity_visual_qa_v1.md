# AI-DEV-212 Cross-Market Research Semantic Integrity & Visual QA V1

Task ID: AI-DEV-212

Status: `IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`

## Repository

- Starting main: `e2ce74b1b16ed3cc8baf12f0d77eb8a85a1b16cb`
- Branch: `ai-dev/212-cross-market-research-semantic-integrity-v1`
- Issue: [#272](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/issues/272)
- Implementation commits / PR / CI / merge main: recorded in the final post-merge handoff.
- Starting main/origin-main: `0/0`; open PRs `0`.
- Existing runtime/generated dirty entries: 182, fingerprint `a317b750071ed62a46a1f027ae006dc609dbf3706ddfed12aeb6937535ca833e`; preserved and not staged.

## Root-cause audit

1. `research_intelligence_v2._role_lists()` admitted SPY/QQQ/SOXX bullish/bearish context into the same company-direction balance as substantive evidence. Market context could therefore create a bullish company stance while all selected company news was directionless.
2. Hypothesis, trigger, invalidation and risk were generated from a shared template with ticker/headline substitution. Event-family semantics were not owned explicitly.
3. Yahoo attribution accepted any target alias in title plus summary. It did not distinguish the primary headline subject, summary-only co-mentions or explicit provider related-ticker metadata.
4. `dashboard_card()` and `build_premarket_card()` were created before bounded RRE selection. The finalized institutional funnel was attached later, but the card compatibility field retained provider-stage RRE/rendered zeros.
5. GCP had no `zh-TW` fontconfig coverage. DOM/text evidence existed, but Chromium rendered Traditional Chinese as tofu in PNG and PDF.

## Implementation

Implemented company-direction evidence ownership, deterministic event-family narrative, entity-attribution V2, finalized funnel compatibility projection, governed user-scoped CJK font runtime, actual glyph diagnostics and executable AI-DEV-212 governance registration.

## Architecture and before/after semantics

`research_direction_ownership_v1` marks company substantive evidence separately from contextual confirmation. Market/sector/ETF/technical/price/volume/ADR evidence can confirm an existing thesis but cannot establish company Research direction. Directionless news remains selectable and visible with directional contribution `0/0`; market-only fixtures resolve to `insufficient_evidence` with no research score.

`deterministic_company_event_narrative_v1` derives hypothesis, confirmation, invalidation and risk from the actual headline and event family: earnings/guidance, regulatory/legal, product/demand, capex/supply-chain, contract/partnership, management/capital allocation, filing/disclosure or material company news. Price confirmation is secondary.

`us_entity_attribution_v2` accepts explicit provider related-ticker metadata or an unambiguous title entity. Summary-only co-mentions and competing primary-title subjects fail with provenance. The ABT-primary/GOOGL-context fixture is rejected; an explicit GOOGL related-ticker counterpart passes.

The premarket compatibility card now consumes the post-selection finalized funnel and canonical selected item. A mutation that claims selected/rendered while retaining rendered=0 is detected.

The CJK runtime uses pinned SIL-OFL `NotoSansCJKtc-Regular.otf` in `~/.cache/stock-ai-fonts`, SHA-256 `dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4`. No privileged/system package mutation occurs. Chromium receives a private fontconfig and must pass an actual 12-glyph pixel-signature gate before capture. Missing coverage produces non-blocking `CJK_FONT_UNAVAILABLE` Visual Evidence failure.

## User-visible Outcome

Dashboard/Email/rendered-text research now distinguishes company evidence from market context, presents event-specific hypothesis/confirmation/invalidation/risk text, retains qualified directionless news without inventing direction, and produces PM-readable Traditional Chinese PNG/PDF evidence when the governed runtime is ready.

## Evidence

The validator proves the ABT-primary/GOOGL-context rejection and explicit related-ticker recall pair, market-only direction rejection, regulatory-versus-earnings narrative differentiation, finalized-funnel mutation rejection, six-symbol replay shape, twelve distinct Traditional Chinese glyph rasters and PNG/PDF/manifest hash parity.

## Quality Gate

Dedicated AI-DEV-212 cases PASS:

- regulatory versus earnings family-specific narrative;
- market-only direction rejection;
- directionless qualified news visibility without direction;
- ABT/GOOGL negative attribution and explicit-related-ticker positive recall;
- finalized funnel parity and contradiction mutation;
- six-symbol AAPL/NVDA/TSLA/GOOGL/SPCX/TSM narrative shape;
- real Chromium CJK visual gate;
- PNG/PDF/manifest hashes and published-DOM immutability;
- Decision boundary unchanged.

Real visual fixture: PNG `1440x1200`, 31,104 bytes; PDF one page, 78,469 bytes. Chromium reported `font_loaded=true`, 12 glyphs and 12 unique raster signatures. Exact ephemeral hashes vary with Chromium metadata and are reported by the validator on every run.

AI-DEV-201, AI-DEV-208, AI-DEV-209, H2, H3, AI-DEV-210 and AI-DEV-211 targeted regressions pass. Full executable registry, CI and post-merge counts are recorded in the final handoff.

## Regression

Relevant TW/US research, AI-DEV-201/202/207/208/209/H2/H3/210/211, seven-window cross-feature, admission/public-latest, notification provenance, landing, source inventory and governance validators pass. The executable branch and post-merge registry closure results are reported after their governed runs.

## Production Usability

Implementation is production-safe and downstream compatible, but the task remains pending natural verification. Visual capture remains non-blocking to the market batch; a missing CJK runtime produces explicit Visual Evidence failure rather than unreadable success.

## Known Limitations

Headline/metadata attribution cannot infer relationships that providers do not expose; ambiguous co-mentions are intentionally rejected. AI-DEV-211 still lacks an approved external authenticated ChatGPT connector.

## Deferred Enhancements

No new source acquisition, LLM narrative generation, visual AI grading, transport connector, trading model change or broad Dashboard redesign is included.

## Safety

- Trading/strategy/scoring/prediction/ranking/eligibility/action/entry/stop/target/sizing: unchanged.
- Production pipeline/publish/LINE/Email/trading: not executed.
- Scheduler/cron/systemd/nginx/firewall: unchanged.
- Secrets accessed: false.
- Production DB written: false.
- Immutable history rewritten: false.
- Existing runtime/generated artifacts cleaned/staged: false.
- AI-DEV-211 transport boundary remains `DIRECT_CHATGPT_TRANSPORT_PENDING_EXTERNAL_CAPABILITY`.

## Natural Verification

The immutable Issue #271 revision remains pre-fix evidence and was not rewritten. The next eligible TW four-window and US three-window scheduled lifecycles must confirm entity attribution provenance, company-direction ownership, event-specific narratives, one finalized funnel across channels, readable Traditional Chinese PNG/PDF, coverage parity and unchanged Decision outputs.

## Phase Contribution

This closes deterministic Research Intelligence Quality & Explainability defects between admitted evidence, company thesis ownership, PM presentation and Visual Evidence review while leaving Prediction and Decision authority unchanged.

## Final Status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION`
