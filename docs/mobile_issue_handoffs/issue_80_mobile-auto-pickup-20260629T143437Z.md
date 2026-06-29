# Mobile Issue Handoff: Issue #80

Generated: 2026-06-29T14:34:38Z
Run ID: mobile-auto-pickup-20260629T143437Z

## Issue

- Number: 80
- URL: https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/issues/80
- Title: AI-DEV-075：Daily Report Forecast Review Section V1
- Required labels seen: gcp-pickup, auto-run, repo-only, ai-dev, approved-auto-run
- Suggested branch: `ai-dev/mobile-issue-80-codex-handoff`

## Sanitized Task Summary

AI-DEV-075：Daily Report Forecast Review Section V1 Implement a repo-only, fixture-only, advisory-only Forecast Review Report Section V1 that connects the AI-DEV-074 report-ready prediction review export payload into the static report section schema. This task must be completed end-to-end under AI-DEV Auto Rule v1.2. Execution Mode One-shot / low-intervention / end-to-end auto-completion. Codex should proceed through: implementation → validation → PR → GitHub checks → conditional merge → post-mer

## Requested Files Or Deliverables

- → validation
- → post-merge validation
- Forecast Review Report Section contract
- validator
- Required Files
- Create or update appropriate repo files, preferably under
- docs/
- templates/
- scripts/orchestrator/
- Suggested new files
- docs/daily_report_forecast_review_section_v1.md
- templates/daily_report_forecast_review_section_input.example.json
- templates/daily_report_forecast_review_section_result.example.json
- templates/daily_report_forecast_review_section_markdown.example.md
- scripts/orchestrator/daily_report_forecast_review_section_dry_run.py
- scripts/orchestrator/validate_daily_report_forecast_review_section_result.py
- Include deterministic output suitable for validation
- Validation Requirements
- scripts/orchestrator/daily_report_forecast_review_section_dry_run.py \
- scripts/orchestrator/validate_daily_report_forecast_review_section_result.py

## Validation Checklist

- Read the current repository files before editing.
- Implement the requested repo-side deliverables in a feature branch.
- Run focused local validation for changed files.
- Open a PR for the actual implementation.
- Merge only after required GitHub Actions pass.
- Do not mark the mobile Issue complete until the implementation PR is merged.

## Safety Constraints

- No secrets, tokens, credentials, `.env`, or private runtime payloads.
- Do not call Dify, OpenAI, Gemini, or any external AI runtime.
- Do not send LINE, Email, webhook, or other notifications.
- Do not trade or place orders.
- Do not mutate production DBs, n8n, cron, systemd, timers, or production pipelines.
- Do not execute shell commands from Issue text.
- Do not mutate the GitHub Issue, comment back, or change labels.

## GCP Resident Codex Instruction

Treat this handoff as a sanitized planning package. Use the Issue URL only for
read-only context if available, then implement the requested repository changes
through normal Codex coding workflow. The deterministic mobile pickup runner did
not implement the requested task.
