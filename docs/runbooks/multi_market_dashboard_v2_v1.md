# AI-DEV-170 Multi-Market Dashboard V2 Runbook

## Purpose
AI-DEV-170 separates Taiwan and US Dashboard routes after the US 20:00 reminder correctly ran but linked to the Taiwan four-window page. The fix is a multi-market Dashboard architecture, not a one-line URL patch.

## Public URLs
- Landing: http://35.201.242.167/stock-ai-dashboard/index.html
- Taiwan Dashboard: http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html
- US Dashboard: http://35.201.242.167/stock-ai-dashboard/dashboard/us/index.html
- Old compatible Taiwan route: http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html

## Route Policy
The landing page links to both markets. The Taiwan route renders only TW windows: 07:00, 13:05, 13:35, and 15:00. The US route renders only US windows: 20:00, 23:00, and 06:30. The old four-window URL remains a Taiwan-compatible route because historically it was the Taiwan Dashboard.

## Artifact Isolation
US Dashboard rendering reads only US runtime artifacts under `artifacts/runtime/us_stock/` or the US offline fixture during safe build validation. It never falls back to Taiwan runtime data. Taiwan Dashboard rendering uses the existing Taiwan four-window page and does not render US symbols. If an artifact has the wrong `market` field, the UI must show a PM-readable market mismatch state instead of rendering it as valid data.

## Notification Links
TW LINE and Email defaults point to the Taiwan route. US LINE and Email content points to the US route. LINE remains short reminder only; Email remains full report. Validators use dry-run/no-send previews only.

## Build and Publish
Build preview pages:

```bash
python3 scripts/orchestrator/build_multi_market_dashboard_v2.py --pretty
```

Validate market isolation and PM-readable Decision Intelligence UX:

```bash
python3 scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty
python3 scripts/orchestrator/validate_decision_intelligence_ux_v1.py --pretty
python3 scripts/orchestrator/validate_decision_presentation_v2.py --pretty
```

The UX validator rebuilds the preview, inspects visible page text outside
`script`/`style`, and fails if the main Dashboard surface exposes raw JSON-like
fragments or raw enum tokens such as `insufficient_data`, `no_trade`,
`entry_zone`, `reward_risk`, or `available_reference`.

AI-DEV-176 Decision Presentation V2 validation covers Dashboard, Email, and LINE
rendering together. It confirms TW/US Dashboard cards expose Decision Summary,
Daily Tactical, Prediction, Research, reasons, risks, and technical details
through human-readable labels, while Email and LINE use the same presentation
helpers instead of raw runtime dicts. LINE must include only one Dashboard URL.
AI-DEV-176A adds US Dashboard / Email parity checks for AAPL, NVDA, TSLA, and
GOOGL. If runtime has `entry_zone`, `stop_reference` / `invalidation_level`,
`target_zone_1`, or `reward_risk_ratio`, the presentation object, Email block,
and rendered Dashboard HTML must all preserve the value. This hotfix is
presentation-only; it does not change strategy engines, scores, confidence,
prediction, scheduler, runtime artifacts, data sources, LINE contract, or Email
contract.

Publish pages after merge from `main`:

```bash
python3 scripts/orchestrator/publish_multi_market_dashboard_v2.py --apply --pretty
```

The publisher writes a timestamped rollback backup under `/var/www/stock-ai-dashboard/.ai_dev_170_rollback/` and updates:
- `/var/www/stock-ai-dashboard/index.html`
- `/var/www/stock-ai-dashboard/dashboard/tw/index.html`
- `/var/www/stock-ai-dashboard/dashboard/us/index.html`
- `/var/www/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html`

## Rollback
Use the rollback command returned by the publish manifest. If needed, restore the four HTML files from the latest `.ai_dev_170_rollback` backup. Rollback does not change scheduler, formulas, or notification credentials.

## Public Marker Verification
Check that the US page contains `美股 AI 決策儀表板`, `美股盤前`, `美股盤中`, and `美股檢討`, and does not contain Taiwan-only 9/9 stock-count wording. Check that the TW page contains `台股 AI 決策儀表板` and the TW window times.

For AI-DEV-175 Decision Intelligence UX, also confirm the user-facing TW/US
pages show PM-readable labels for trend, setup, data availability, confidence,
risk, and review state. Raw runtime keys may remain only inside JavaScript API
payload construction or backend artifacts, not in visible Dashboard copy.

For AI-DEV-176, also confirm Email and LINE previews do not expose raw dicts,
raw JSON, or raw enum keys. US Email should show `Research`, `Daily Tactical`,
and `Prediction` blocks per stock. TW pre-open Email should include `Decision
Presentation V2` and `Research / Daily Tactical / Prediction` sections.

## Diagnosis: US Page Shows TW Content
1. Confirm LINE/Email link points to `/dashboard/us/index.html`.
2. Run `validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty`.
3. Inspect the public US HTML for TW markers.
4. Verify US runtime artifact `market=US`.
5. Republish via `publish_multi_market_dashboard_v2.py --apply --pretty` from merged `main`.

## Safety Boundaries
This task does not run `python3 main.py`, does not send unscheduled LINE/Email, does not run manual rerun, does not trade, does not read secrets, does not alter Taiwan or US formulas, and does not change scheduler times.

Post-merge validation should run the same validators from merged `main`, then
perform controlled Dashboard publish with `publish_multi_market_dashboard_v2.py
--apply --pretty`. After publishing, rerun the market isolation validator with
`--require-public` and the UX validator. Do not publish from an unmerged feature
branch unless a human explicitly approves that emergency path.
