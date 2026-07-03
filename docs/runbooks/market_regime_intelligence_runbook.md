# Market Regime Intelligence Runbook

## Generate an offline artifact
```bash
python scripts/orchestrator/build_market_regime_artifact.py --pretty
```

## Use an explicit input artifact
```bash
python scripts/orchestrator/build_market_regime_artifact.py --pretty --input templates/market_regime_input.example.json
```

## Validate schema and classifier behavior
```bash
python scripts/orchestrator/validate_market_regime_intelligence_v1.py --pretty
```

## Interpret regimes
`trend_up` and `trend_down` represent directional market movement. `range_bound` means weak trend and lower volatility. `high_volatility` means volatility exceeds the configured threshold. `risk_on` and `risk_off` combine trend, breadth, and drawdown context. `insufficient_data` means the sample or metrics are not enough to classify.

## Operational limits
Do not connect this V1 directly to production scheduler, delivery, dashboard publish, confidence mutation, factor-weight mutation, or trading. Treat outputs as advisory research artifacts.

## Follow-up integration checklist
Confirm enough retained history exists, validate effect on rolling prediction/factor evaluation, add report/dashboard display in a separate PR, and keep production mutations disabled until explicitly approved.
