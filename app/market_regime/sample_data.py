from __future__ import annotations
from copy import deepcopy

SAMPLE_INPUT = {
    "schema_version": "market_regime_input_v1",
    "as_of_date": "2026-07-03",
    "market": "TWSE",
    "sample_size": 20,
    "source_kind": "offline_sample",
    "metrics": {
        "index_return_5d": 0.032,
        "index_return_20d": 0.081,
        "realized_volatility_20d": 0.17,
        "advance_decline_ratio": 1.42,
        "new_high_new_low_ratio": 1.31,
        "max_drawdown_20d": -0.028,
        "above_ma20_ratio": 0.64,
    },
    "advisory_only": True,
}

def offline_sample_input() -> dict:
    return deepcopy(SAMPLE_INPUT)
