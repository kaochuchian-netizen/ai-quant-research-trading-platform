# Natural Verification Policy V1

## Purpose

Natural verification proves that merged code works in the scheduled production lifecycle. Controlled fixtures cannot be presented as natural evidence.

## SLA

- Standard window-dependent task: observe the next eligible batch and close within 2–5 trading days.
- Cross-window task: observe the complete required sequence within the same bounded window.
- If no eligible trading day occurs, the SLA clock records the market-calendar exception.

## Registry

Every pending task records task ID, implementation date, required windows, owner, acceptance criteria, deadline policy, evidence links and current state in `config/governance/pending_natural_verification.json`.

## States

- `VERIFIED`: required natural evidence passed.
- `PENDING`: within SLA and waiting for an eligible batch or review.
- `ACCEPTED`: bounded residual limitation approved with evidence, owner and monitoring; not equivalent to verified.
- `DEFERRED`: intentionally moved to a future phase with rationale and owner; cannot hide a current must-fix defect.

## Bounded acceptance

Acceptance is allowed only when user safety and truthfulness remain intact, the limitation is measurable, monitoring exists and the phase owner records the decision. Unsupported trading or delivery claims can never be accepted.

## Historical replay

Historical replay may validate deterministic logic and migration compatibility. It must be labeled replay, remain read-only and never replace the next required natural batch.

## Residual monitoring

Pending and accepted items define a monitored signal, expected range, failure condition and escalation owner. The pending inspector reports overdue and incomplete records without mutating them.
