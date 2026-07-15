# Seven-Window Decision Intelligence V4

Task: AI-DEV-181
Schema: `seven_window_decision_intelligence_v4`

## Goal

Provide a deterministic, source-backed decision projection for all seven formal TW/US windows while preserving Dashboard, Email, LINE, immutable archive, manual revision, Operations Center, URL isolation, scheduler and delivery safety contracts.

The projection classifies only fields already present in the selected window payload. Missing fields remain empty/unknown; it never invents values and never reads another market/window as fallback.

## Impact inventory

| Component | TW 07:00 | TW 13:05 | TW 13:35 | TW 15:00 | US 20:00 | US 23:00 | US 06:30 |
|---|---|---|---|---|---|---|---|
| Window contract | pre-open decision | intraday change | pre-close snapshot | post-close review | premarket | intraday change | post-close review |
| Dashboard renderer | TW tactical + V4 | compact + V4 | compact + V4 | review + V4 | premarket + V4 | compact + V4 | review + V4 |
| Email formatter | shared TW formatter | shared TW formatter | shared TW formatter | shared TW formatter | approved US formatter | approved US formatter | approved US formatter |
| LINE scope | counts + link | counts + link | counts + link | review counts + link | counts + link | counts + link | review counts + link |
| Archive routes | latest/previous | latest/previous | latest/previous | latest/previous | latest/previous | latest/previous | latest/previous |
| Manual rerun | latest only | latest only | latest only | latest only | latest only | latest only | latest only |
| Snapshot resolver | same market/window/date | same | same | same | same | same | same |
| Operations Center | date/revision/status | same | same | same | same | same | same |
| URL registry | TW URL | TW URL | TW URL | TW URL | US URL | US URL | US URL |
| Static publish | controlled route | controlled route | controlled route | controlled route | controlled route | controlled route | controlled route |

Generated contract:

- `templates/multi_market_dashboard_v2/index.html`, `manifest.json`, and `dashboard/**` are repository-controlled generated public templates.
- The implementation commit may include a deterministic rebuild only when required by the repository validators.
- Publish timestamps, rollback copies, validator fixtures, `/tmp` staging, runtime status and production artifacts are not implementation source and must not be staged merely because a validator/publish touched them.

## Seven-window content contract

| Window | Before section inventory | V4 decision fields | Suppressed |
|---|---|---|---|
| TW 07:00 | pre-open highlights, market, watch/risk, research, tactical, range, plan, news, completeness | top opportunities, no-trade, chase-risk, entry readiness, confidence distribution, same-window change | intraday trigger, future outcome, runtime metadata |
| TW 13:05 | intraday change, pre-open delta, trigger state, proximity, volume, risk | triggered/invalidated/actionable counts, target/stop rankings, price-volume confirmation, new risk | long research/financial/SEC and outcome cards |
| TW 13:35 | snapshot, late risk, avoid chase, proximity, setup, next watch | hold/avoid lists, elevated late risk, watchlist add/remove, same-window change | full 07:00 plan, long research, full technical detail |
| TW 15:00 | review, predicted/actual, entry/target/stop, result, false breakout, 7-day, next watch | outcome distribution, direction hit, trigger/target/stop effectiveness, calibration, 7-day trend | new entry/target plan and full tactical/research/news/SEC |
| US 20:00 | premarket/gap, index/sector, setup, plan, events/news, volatility | movers, gap risk, event ranking, sector-relative strength, entry readiness, same-window change | outcome and 06:30 review |
| US 23:00 | open change, gap/volume, trigger, proximity, events, adjustment | confirmed setups, failed gaps, volume-confirmed moves, actionable/chase counts, 20:00 deviation | full 20:00 research/financial/SEC and 06:30 review |
| US 06:30 | review, prediction, entry/stop/target outcome, result, events, next watch | review distribution, direction hit, setup/gap quality, calibration, same-window change | new premarket plan and full 20:00 card |

Every section has projection provenance: the function argument, explicit card tactical/review fields, no cross-window fallback, and `invented_values=false`.

## Dashboard / Email / LINE responsibilities

- Dashboard renders the complete V4 section inventory, decision counts/lists and existing window-specific detail cards.
- Email uses the same projection and a medium-length summary plus its window contract. It may include per-stock detail appropriate to that window.
- LINE uses only the same projection's counts and the market-correct Dashboard link. Semantic parity means counts come from the identical projection; it does not require full Dashboard parity.
- All controlled validators set `notification_sent=false`; validation never invokes send functions.

## Latest / previous and archive rendering

- Resolver selection remains `market + window + latest effective_trading_date + highest revision`.
- Previous remains `market + window + previous effective_trading_date + highest revision`, never `revision - 1`.
- Both routes use the same V4 schema and the resolver-selected immutable `snapshot["payload"]`.
- Archive rendering does not load mutable global latest runtime and does not expose raw JSON.
- Comparison remains same-market/same-window across different effective trading dates. With no previous snapshot, the explicit empty state is valid and not an Operations failure.

## Manual revision policy

- A manual rerun increments the revision for the same effective trading date.
- Only the selected market/window latest route is rebuilt/published.
- Previous content hash and the other 13 route hashes must remain unchanged.
- The next effective trading date advances previous to the prior day's highest revision.
- Operations Center reads the archive result and displays latest date/revision and previous date; V4 does not alter those semantics.

## Operations Center compatibility

The Landing Operations table keeps the archive resolver as its date/revision source and presents Scheduler, Pipeline, Dashboard, Archive, LINE, Email and Overall columns. No snapshot is shown as “waiting for first formal data,” not failure. Dry-run/no-send output is never treated as scheduled production delivery success.

## Cross-feature regression matrix

Run:

```bash
python scripts/orchestrator/validate_cross_feature_regression_matrix_v1.py --pretty
```

The merge gate creates a temporary deterministic archive and validates:

- seven distinct contracts and expected card types;
- Dashboard/Email/LINE semantic parity;
- fourteen latest/previous routes and immutable payload rendering;
- same-market/same-window source identity and schema parity;
- fixture/validator/incomplete admission rejection;
- manual revision +1, unchanged previous hash, and unchanged other 13 route hashes;
- seven Operations rows, revision/date/status, market URL isolation;
- forbidden public/debug tokens and compact/review generic-card suppression;
- exact pre/post `git status --short` equality.

## Fixture policy

Fixtures live only inside `TemporaryDirectory`. Their payload records `artifact_mode=controlled_no_send` and `verification_scope=temporary_non_production_archive`; they are not written to the production archive or public production routes and are never consumed by Operations Center. The temporary directory is deleted before the validator returns. Explicit fixture/validator/incomplete artifacts are separately asserted to fail admission.

## Controlled verification and publish

Pre-merge verification renders seven Dashboard payloads, seven Email previews, seven LINE previews and fourteen archive routes in temporary paths. It verifies no-send flags and never executes production-approved delivery.

Post-merge static publish may publish Landing, TW, US, fourteen archive routes and Operations Center only. It must create a timestamped rollback backup, then validate public URLs. Static publish does not send LINE/Email, trade, change scheduler, or execute `main.py`.

## Rollback

1. Stop static publication if any merge gate fails.
2. Revert the AI-DEV-181 merge commit through a new PR; do not rewrite shared history.
3. Restore the static files from the controlled publish backup recorded in the publish result.
4. Re-run archive navigation, manual revision, health, URL isolation and post-merge validators.
5. Do not change or delete immutable archive snapshots as part of presentation rollback.

## Known limitations

- Rankings and outcome metrics remain empty when the selected payload lacks explicit tactical/review evidence; no generic fallback is used.
- Same-window “change” is limited to values supported by current and previous immutable payloads.
- Production archive content accumulates only through admitted formal successful batches; deterministic fixtures never backfill it.
