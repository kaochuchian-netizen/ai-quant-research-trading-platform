# Platform Health Score V1

The platform health score is a governance signal, not a trading score. Its machine-readable baseline is `config/governance/platform_health_score.json`.

## Dimensions

Product Quality, Decision Explainability, Data Truthfulness, Evidence Traceability, Cross-window Continuity, Cross-channel Parity, Natural Verification, Regression Risk, Technical Debt and Phase Completion are scored from 0 to 100.

Each dimension includes description, measurement method, accountable role, target, trend, weight and dated evidence. Missing evidence is scored conservatively; it is never silently treated as 100.

## Interpretation

- 85–100: healthy and phase-ready in that dimension.
- 70–84: usable with tracked improvement.
- 50–69: material weakness; phase exit normally blocked.
- 0–49: critical governance attention required.

For Regression Risk and Technical Debt, a higher score means lower residual risk/debt and better health.

## Update policy

- update after material governance, product baseline or natural-verification changes;
- preserve the measurement and evidence behind every score;
- trend is one of `improving`, `stable`, `declining`;
- overall score is the weighted mean and is validator-checked;
- a high overall score cannot mask a blocking must-fix item.
