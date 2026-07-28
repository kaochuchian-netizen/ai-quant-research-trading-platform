# Product Quality Gate V1

Each dimension is rated `PASS`, `CONDITIONAL_PASS` or `FAIL`. Evidence is mandatory. A Conditional Pass includes a bounded limitation, owner and follow-up condition.

| Dimension | Pass standard | Conditional Pass | Fail | Evidence required |
| --- | --- | --- | --- | --- |
| Correctness | Canonical facts and decisions agree | Non-core uncertainty safely unavailable | Contradictory or unsupported claim | Deterministic cases and representative payload |
| Completeness | All decision-critical fields present | Optional fields missing and disclosed | Core contract is an empty shell | Schema/count/missing-field evidence |
| Consistency | Same semantics across cards and summaries | Presentation differs without semantic drift | Counts or categories conflict | Aggregate comparison |
| Explainability | Decision, confidence and outcome reasons readable | Some optional detail deferred | Raw enum or unexplained result | Rendered examples |
| Source Quality | Sources classified and appropriate | Lower-tier source clearly bounded | Untraceable or fabricated source | Source metadata and tier |
| Freshness | Time and timezone meet window contract | Approved stale/reference data labeled | Stale data presented as current | Source/as-of/freshness fields |
| Truthfulness | Claims match evidence resolution | Uncertainty explicitly stated | Inference presented as fact | Evidence-to-claim mapping |
| Readability | Mobile-oriented concise primary content | Detail remains long but collapsible | Repeated placeholders or unusable density | DOM/text repetition scan |
| Localization | User-facing enums and instructions localized | Approved financial abbreviations remain | Internal wording leaks | Visible-text scan |
| Continuity | Source plan and lifecycle identities connect | Optional transition unavailable and disclosed | Cross-window promotion or identity break | Per-symbol identity chain |
| Parity | Channels share counts and source identity | A non-delivery channel explicitly unavailable | Channel-local recomputation mismatch | Snapshot/revision/hash/count matrix |
| Production Usability | Daily report supports a safe decision | Research usable with declared constraint | User cannot understand current action | User-value scenario |

## Decision rule

- Any Fail in Correctness, Truthfulness, Continuity, Parity or Production Usability blocks merge.
- Conditional Pass is permitted only when it does not create an unsupported action claim.
- Product evidence must come from deterministic fixtures plus natural evidence when required.
