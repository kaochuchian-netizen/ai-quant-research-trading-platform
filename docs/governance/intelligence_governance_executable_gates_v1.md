# Intelligence Governance and Executable Gates V1

## Purpose

AI-DEV-205 makes intelligence status and validator policy executable contracts. A registry entry marked ACTIVE and required for a gate is no longer documentation: the gate must select it, execute it, retain its result and fail closed when execution is missing or unsuccessful.

## Validator registry execution

`config/governance/validator_registry_v1.json` is the sole policy source. Each entry declares lifecycle status, execution role and gate applicability.

- `leaf` validators are executable checks.
- `orchestrator` validators coordinate a gate and must not be invoked recursively by themselves.
- ACTIVE required leaf validators must exist and return exit code zero without a machine-readable semantic failure.
- Missing files, exceptions, non-zero exits and semantic `FAIL` results fail the gate.
- Selection order is deterministic by validator ID.
- A gate report lists selected, executed, passed, failed and recursion-guarded IDs. Any unexplained selected validator is a failure.
- SUPERSEDED, DEPRECATED and HISTORICAL_ONLY validators remain governed by their declared lifecycle and are not silently treated as current evidence.

The branch and post-merge orchestrators call one shared registry executor. The caller orchestrator is the only selected item that may be skipped, and its skip is explicitly recorded as `SKIPPED_RECURSION_GUARD`.

## Readiness applicability

Every intelligence dimension owns its denominator. `ready_symbols` is always bounded by `total_applicable_symbols`.

- applicable 1, ready 1: COMPLETE or the dimension-specific ready state.
- applicable 1, ready 0: NONE, INSUFFICIENT or the dimension-specific unavailable state.
- applicable 0, ready 0: NOT_APPLICABLE or NOT_EVALUATED, according to declared scope.
- An out-of-scope dimension does not lower overall intelligence readiness.
- An applicable but missing dimension still lowers readiness and retains explicit reasons.

Reason text may not contradict the denominator. An out-of-scope dimension cannot claim missing, stale or failed evidence.

## Prediction and health consistency

Legacy health summaries are compatibility projections of canonical readiness. Prediction cannot be AVAILABLE when both baseline and full prediction are NOT_EVALUATED or unavailable. A reusable consistency validator rejects contradictory research, prediction and Decision health summaries.

Runtime success, rendering, archive creation and preview generation never promote intelligence readiness.

## Decision ownership

The Decision Layer exports a minimal read-only required-input contract. Health evaluates this declaration and records its contract ID and provenance. This changes readiness reporting only; it does not alter action, eligibility, ranking, scoring, entry, stop, target or execution.

## Research readiness

Research readiness retains separate fields for coverage score, required-category readiness and optional gaps. Numeric coverage alone does not claim universal completeness. Mandatory categories are minimal and instrument/consumer appropriate; unsupported optional sources remain explicit gaps rather than structural failures.

## Verification boundary

Deterministic fixtures and registry runs prove contract behavior. They do not prove natural production behavior or predictive quality. TW 07:00→13:05→13:35→15:00 and US 20:00→23:00→06:30 remain required natural evidence.
