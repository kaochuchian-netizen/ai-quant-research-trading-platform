# Definition of Done V2

An AI-DEV is done only when all applicable levels pass. “PR merged,” “CI passed” and “validator passed” are evidence, not the complete definition.

## Level 1 — Engineering

- implementation matches scope and non-goals;
- deterministic positive and negative tests pass;
- changed Python compiles and repository diff checks pass;
- regression and branch governance gates pass;
- no unrelated files, secrets or production artifacts are committed;
- rollback path is documented.

Measurement: commands, results, changed-file inventory and CI check identity.

## Level 2 — Product

- user-visible correctness, completeness, consistency and explainability are demonstrated;
- source quality, freshness and missing-data semantics are truthful;
- localization and readability pass representative rendering checks;
- channel counts and source identity match;
- known limitations are visible and bounded.

Measurement: Product Quality Gate result with evidence for every dimension.

## Level 3 — Operational

- admission, archive, resolver, provenance and operational status remain safe;
- controlled verification does not mutate formal evidence or send notifications;
- post-merge repository state is governance-safe;
- natural verification is either complete or formally registered with SLA and owner;
- monitoring and failure classification are documented.

Measurement: operational validators, artifact hashes, inspector result and pending registry state.

## Level 4 — User Value

The completion report must answer:

1. What concrete daily platform use improved?
2. What does a user now see, understand or decide that was previously missing or misleading?
3. What evidence demonstrates that improvement?
4. What remains limited, and how does the product disclose it safely?

Measurement: a specific before/after outcome. Generic statements such as “quality improved” do not pass.

## Closure rule

- All applicable levels pass: `CLOSED`.
- Engineering complete but required natural evidence pending: `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`.
- Any must-fix gate fails: `OPEN`.
