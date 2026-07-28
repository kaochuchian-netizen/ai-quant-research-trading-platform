# Phase Completion Standard V1

## Required classifications

Every phase exit item is exactly one of:

### Must Fix Before Close

A defect affecting correctness, truthfulness, evidence, continuity, parity, production safety or the phase objective. Any open item blocks phase closure.

### Acceptable Limitation

A bounded limitation that does not mislead users or weaken safety. It requires evidence, owner, monitoring and an explicit acceptance decision.

### Deferred Enhancement

Useful future capability that is not required for the current phase objective. It requires a target phase and rationale.

## Exit evidence

- all must-fix items closed;
- phase-level Product Quality Gate has no blocking Fail;
- health score meets the phase target or an approved bounded exception exists;
- pending natural verification is verified or explicitly prevents closure;
- technical debt and deferred work have owners;
- completion report states daily user-value improvement.

## Close authority

Phase closure is a versioned registry change reviewed through PR. A task, PR, deployment or date cannot implicitly close a phase.
