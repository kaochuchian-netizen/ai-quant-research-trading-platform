# US Scheduled Runtime Provenance Classification V1

## Purpose

AI-DEV-181A fixes a persistence-boundary defect that allowed a US validator dry-run artifact to overwrite the shared formal runtime. It does not relax Dashboard or archive isolation.

## Provenance flow and root cause

The formal flow is:

`cron --production-approved` → `approved_us_stock_delivery.py` → `build_live_runtime_artifact(production_runtime=True)` → formal runtime persistence → snapshot admission → Dashboard / Operations Center.

The scheduler already supplied `--production-approved`, and the live runtime builder already produced the complete production tuple (`artifact_mode=production_runtime`, `data_source_mode=live`, `fixture=false`, `validation_only=false`). The defect was in `approved_us_stock_delivery.py`: every invocation wrote to the shared `WINDOW_OUTPUTS`, legacy latest output, and shared status files before admission was evaluated. Consequently, `validate_production_scheduler_dashboard_url_contract_v1.py --dry-run` replaced a valid scheduled runtime with validation-only fixture data. Dashboard correctly rejected that overwritten artifact.

The hotfix classifies provenance before any shared persistence. Only admitted formal provenance may update shared runtime/status, archive, or public Dashboard output.

## Provenance enum

- `scheduled_production`: scheduled formal production invocation.
- `manual_rerun`: authorized no-send manual revision of an effective trading date.
- `controlled_no_send`: live controlled verification without formal admission.
- `preview`: generated preview only.
- `fixture`: deterministic or synthetic fixture.
- `validator`: validator-owned artifact.
- `dry_run`: runner dry-run.
- `unclassified`: insufficient or contradictory provenance.

Unsafe flags and modes take precedence over an explicit provenance string. A payload cannot claim `scheduled_production` while retaining fixture, validator, preview, dry-run, controlled-no-send, or validation-only evidence.

## Admission and persistence

Only `scheduled_production` and `manual_rerun` are admitted. Fixture, validator, preview, dry-run, controlled-no-send, and unclassified artifacts are rejected.

Admission is evaluated before writes to:

- the three US window latest runtime files;
- legacy US latest files;
- shared delivery status files;
- snapshot archive;
- Dashboard publish.

Rejected runs may return an in-memory/result payload or an explicitly requested temporary output, but never overwrite shared formal latest state.

## Archive and resolver

Every new snapshot records:

- `runtime_provenance`;
- `admission_reason`;
- `admitted`.

Archive loading re-evaluates these fields. Resolver inputs must be admitted, successful, complete, non-fixture, and non-validator. Latest / Previous and manual revision semantics remain unchanged.

## Dashboard and Operations Center

The US Dashboard still requires the complete production tuple plus admitted provenance. It never uses `allow all runtime` behavior. Unsafe runtime continues to render the safe empty state.

Operations Center displays `Runtime Provenance` per window. Unsafe provenance is labelled `Validation Only`; it is not represented as production success.

## Controlled verification

`validate_runtime_provenance_classification_v1.py` creates only temporary artifacts. It verifies:

- scheduled production is admitted by Dashboard and archive;
- manual rerun increments Latest while Previous stays on the preceding trading date;
- fixture, validator, preview, dry-run, and controlled-no-send are rejected;
- dry-run leaves hashes of all shared formal runtime/status files unchanged;
- Operations Center distinguishes scheduled production from validation-only state;
- the temporary directory is removed.

No fixture is written to the production archive or treated as formal Operations data.

## Rollback

Revert the implementation commit and republish static pages from the pre-publish backup. Do not delete or rewrite production runtime/archive data during rollback. If the current runtime is validation-only, retain the safe empty state until the next successful scheduled production batch creates an admitted formal runtime.

## Operational expectations

The first successful scheduled US batch after deployment writes an admitted formal runtime and snapshot, then the US Dashboard and Operations Center show `scheduled_production`. Manual reruns remain no-send revisions and update only the matching window Latest route. Scheduler cadence, notification approval, trading logic, and delivery policy are unchanged.
