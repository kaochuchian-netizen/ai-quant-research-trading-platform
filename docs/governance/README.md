# Platform Governance V1

This directory is the versioned source of truth for platform roadmap, product quality and AI-DEV completion governance. It complements, and does not override, repository safety and authorization rules in `AGENTS.md`.

## Governance flow

1. Start from `ai_dev_task_template.md` and identify the current phase in `config/governance/platform_phase_status.json`.
2. Define measurable Engineering, Product, Operational and User Value outcomes.
3. Apply `product_quality_gate.md`; every gate needs evidence and a Pass, Conditional Pass or Fail result.
4. If natural production evidence is required, register it under `pending_natural_verification.json` and apply `natural_verification_policy.md`.
5. Produce a completion report from `completion_report_template.md`.
6. Run all validators in `scripts/governance/` before PR merge and after merge.

## Versioning and precedence

- Governance documents and JSON registries are reviewed through branch → PR → CI → merge.
- `AGENTS.md` remains authoritative for authorization and safety.
- An active AI-DEV task may tighten these standards but may not silently weaken them.
- Changes to phase status or health scores require dated evidence and a PR.

## Canonical artifacts

| Artifact | Purpose |
| --- | --- |
| `platform_roadmap.md` | Phase objectives and exit sequence |
| `ai_dev_task_template.md` | Required future task-package structure |
| `definition_of_done_v2.md` | Four-level measurable completion |
| `product_quality_gate.md` | Product acceptance dimensions |
| `natural_verification_policy.md` | Bounded production verification |
| `phase_completion_standard.md` | Phase-close classification and decision |
| `completion_report_template.md` | Honest completion disclosure |
| `platform_health_score.md` | Health measurement interpretation |
| `config/governance/*.json` | Machine-readable phase, health and pending state |

## Status vocabulary

- `OPEN`: implementation is not complete.
- `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`: engineering gates passed but required natural evidence is pending.
- `CLOSED`: all required gates, including natural verification when applicable, passed.
- Governance-only tasks without natural-batch dependency may close after CI and post-merge validation.

## Validation commands

```bash
python3 -m py_compile scripts/governance/*.py
python3 scripts/governance/run_governance_validation.py --pretty
python3 scripts/governance/validate_ai_dev_task_package_v2.py \
  --input docs/governance/examples/ai_dev_new_feature.md --pretty
python3 scripts/governance/validate_completion_report.py \
  --input docs/governance/examples/completion_report_closed.md --pretty
python3 scripts/governance/validate_phase_registry.py --pretty
python3 scripts/governance/validate_platform_health_score.py --pretty
python3 scripts/governance/inspect_pending_natural_verification.py --pretty
```

The bundle runs positive and negative deterministic cases and performs semantic
JSON-contract validation without writing repository or production artifacts.
