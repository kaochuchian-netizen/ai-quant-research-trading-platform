# LINE Runtime Dashboard Card Content Cleanup Runbook

1. Build the four-window dashboard route preview.
2. Validate LINE link-only messages with `validate_line_and_dashboard_card_content_cleanup_v1.py`.
3. Validate AI-DEV-150 through AI-DEV-156 regression guards.
4. Publish the controlled static Dashboard preview only after validators pass.
5. Do not send LINE or Email during this workflow.
6. Keep raw artifact fields in Debug/validator surfaces only, not stock card main content.
7. If local news headlines are unavailable, show `重大新聞資料待接` and do not fabricate headlines.
