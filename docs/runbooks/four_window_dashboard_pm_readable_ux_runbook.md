# Four-Window Dashboard PM-Readable UX Runbook

## Purpose

Use this runbook when updating the controlled four-window Dashboard preview so a PM can understand it without reading runtime keys, validators, schemas, artifacts, or route contracts.

## Required UX Checks

1. The first screen must show `四時段 AI 決策儀表板`.
2. The preview status must be obvious: `預覽版 / 尚未接正式即時資料`.
3. The main view must present four cards before technical/debug details.
4. The 13:35 card must say `收盤快照 / Close Snapshot`.
5. The 13:35 card must not present full prediction review.
6. Full Prediction Review belongs to the 15:00 card.
7. Debug flags must be in `技術檢查 / Debug` after the main content.
8. Do not embed the old static preview in an iframe.
9. Do not use deterministic placeholder wording as user-facing text.
10. Keep mobile layout cards-first and stacked.

## Publish Flow

After merge, republish the controlled static preview using:

```bash
./venv/bin/python scripts/orchestrator/publish_four_window_dashboard_preview_v1.py --pretty
```

Then validate the public page:

```bash
./venv/bin/python scripts/orchestrator/validate_four_window_dashboard_pm_readable_ux_v1.py --pretty --published
./venv/bin/python scripts/orchestrator/validate_four_window_dashboard_preview_publish_v1.py --pretty --published
```

## Rollback

Use the rollback command recorded by the AI-DEV-145 publish manifest if the PM-readable preview must be reverted.

## Safety

- no LINE / Email / notification
- no scheduler change
- no DB write
- no production pipeline
- no trading
- no rating/action/confidence/weight mutation
- no formal delivery behavior change
