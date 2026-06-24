# Automation Infrastructure Inventory

## Purpose

This document records the current read-only inventory for Dify and n8n
automation infrastructure planning. It is documentation-only and does not
authorize any production change, workflow creation, credential access, or
service operation.

## Scope

- Read-only inventory of repository-visible automation infrastructure clues.
- No Dify or n8n configuration changes.
- No production pipeline changes.
- No database writes.
- No cron, systemd, or timer changes.
- No notification, trading, or order execution.

## Observed Infrastructure

Repository search found no dedicated Dify deployment manifest, no n8n workflow
export, no Docker Compose file for either tool, no Nginx site config, and no
systemd unit files that appear to belong to Dify or n8n.

Observed repository items related to the automation program are limited to:

- `scripts/orchestrator/inspect_ai_platform_status.py`
- `scripts/orchestrator/validate_post_merge_status.py`
- `scripts/orchestrator/archive_completed_ai_task.py`
- `scripts/orchestrator/run_ai_dev_validation_bundle.py`
- `scripts/orchestrator/source_inventory_registry_loader.py`
- `scripts/orchestrator/audit_source_inventory_registry.py`
- `docs/source_inventory_registry.md`
- `docs/roadmap_v6_reconciliation.md`

The repository also contains general application code for market data, analysis,
reporting, and notifications, but no repository-managed Dify or n8n runtime
definition was found.

## Dify Status

- No Dify app manifest or deployment file was observed in this repository.
- No Dify app, knowledge base, or model setting file was observed in this
  repository.
- No evidence of repository-managed Dify runtime control was found in the
  current codebase.
- Any future Dify integration should be treated as a separately governed
  automation-control-plane task.

## n8n Status

- No n8n workflow export was observed in this repository.
- No n8n credential file, workflow definition, or deployment file was observed
  in this repository.
- No evidence of repository-managed n8n runtime control was found in the current
  codebase.
- Any future n8n integration should remain read-only during inventory and design
  phases.

## Network / Port Exposure Summary

No repository file in the current checkout defines Dify or n8n ports, ingress
rules, or service bindings.

Repository search did not surface a dedicated automation-service port map.
Therefore, network exposure for Dify and n8n is not established by the repo and
must be confirmed through host-level inspection before any future automation
work.

## Reverse Proxy / Nginx Summary

No Nginx site configuration or reverse-proxy definition for Dify or n8n was
found in the repository.

If Dify or n8n are exposed on the VM, that exposure is not documented in this
codebase and should be treated as external operational state that requires a
separate read-only inventory before any integration is attempted.

## Credential Safety Notes

- Do not read `.env`, secret files, or credential stores as part of this
  inventory task.
- Do not print API keys, tokens, passwords, service-account JSON, or session
  cookies.
- Do not infer credential validity from hidden configuration.
- Do not create new automation credentials as part of inventory work.

## Risk Assessment

Current risk is low for documentation work and high for any future runtime
automation because the repository does not currently expose a documented Dify or
n8n control surface.

Key risks for future work include:

- accidental workflow execution
- accidental notification delivery
- accidental repository mutation by automation
- untracked ingress exposure
- credential sprawl
- overlap with production pipeline logic

## Recommended Automation Phases

1. Read-only inventory of existing Dify / n8n runtime state on the target VM.
2. Draft-only workflow and control-plane design.
3. Checklist-only operational validation for the planned automation flows.
4. Limited dry-run execution against example data only.
5. Explicit human-reviewed rollout of any automation that can mutate repo,
   notifications, or production state.

## Prohibited Automation Actions

- Start, stop, or restart Dify or n8n without an explicit operator decision.
- Create or modify n8n workflows during inventory work.
- Modify Dify app configuration or knowledge base during inventory work.
- Send LINE, email, or other notifications from automation during inventory
  work.
- Execute trading or order-placement actions through automation.
- Modify production pipeline logic, cron, systemd, or timer jobs.
- Read or modify secrets, `.env`, tokens, credentials, or API keys.
- Enable automatic PR merge or automatic repository mutation by Dify or n8n.

## AI-DEV-029 Acceptance Criteria

AI-DEV-029 is complete when:

- `docs/automation_infrastructure_inventory.md` exists.
- The document clearly states that no dedicated Dify or n8n deployment manifest
  was observed in the repository.
- The document records the current repository-visible automation context.
- Network / port exposure is described as not established by repo evidence.
- Reverse proxy / Nginx exposure is described as not established by repo
  evidence.
- Credential safety guidance is explicit.
- The automation phases remain read-only at the inventory stage.
- The prohibited actions list blocks workflow creation, notification delivery,
  trading, and production mutation.

