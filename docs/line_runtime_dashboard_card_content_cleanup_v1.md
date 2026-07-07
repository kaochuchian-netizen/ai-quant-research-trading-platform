# AI-DEV-157 LINE Runtime Notification & Dashboard Card Content Cleanup V1

AI-DEV-157 defines the product split between LINE and Dashboard.
LINE is a short notification entry point. Dashboard is the detailed decision surface.
Email may keep fuller report content in a separate contract.

## LINE contract

Each four-window LINE message contains only a title, one status sentence, the four-window Dashboard URL, and research-only / no-trading wording. It must not include per-stock cards, forecast values, review details, pipeline state, raw artifact keys, or the legacy `/stock-ai-dashboard/index.html` URL.

## Dashboard card cleanup

Formal prediction stock cards render as PM-readable decision cards:

- Prediction summary
- Risk and data-quality summary
- Major news block

Raw artifact details such as `source_evidence`, paths, read mode, source type, missing fields, and local analysis context stay out of the main card surface. If no safe local news headline artifact exists, the card says `重大新聞資料待接` and does not invent headlines.

## Legacy scheduler page

The legacy dashboard index is no longer a formal decision entry point. Controlled publish rewrites it as a legacy/debug landing page that links to the four-window Decision Intelligence Dashboard.

## Safety

This task does not send LINE or Email, does not modify scheduler, does not write DB, does not execute production pipeline or `python3 main.py`, does not trade, and does not mutate deterministic baseline or production scoring logic.
