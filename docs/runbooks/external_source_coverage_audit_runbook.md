# External Source Coverage Audit Runbook

## Run the audit
```bash
python scripts/orchestrator/build_external_source_coverage_audit.py --pretty
```

## Validate the audit
```bash
python scripts/orchestrator/validate_external_source_coverage_audit_v1.py --pretty
```

## Interpret source status
`production_used` means formally used today. `connector_exists_not_in_formal_report` means code exists but report/dashboard/evaluation promotion is incomplete. `inventory_only_not_connectorized` means the source is planned but not connectorized. `needs_connector` means no adequate connector is present. `low_priority_metadata_only` means the source should not be primary evidence.

## Identify gaps
Review each record's `gaps`: connector, report, dashboard, prediction context, evaluation, credential policy, and quality priority gaps.

## Safety checklist
Do not call external APIs, read `.env`, read secrets, write DB, publish dashboard, send LINE/Email, modify scheduler, or execute broker/order/trading flows while running this audit.

## Next connector planning
Start with B-priority official/company-linked sources, create deterministic sample artifacts first, validate freshness/failure policy, then add shadow report/dashboard/evaluation integration in separate PRs.
